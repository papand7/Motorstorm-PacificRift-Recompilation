# T158: profile of the translated Havok code (C0 standard lift, C1 `--chain-chunks`)

2026-10-29. Offline only; no game launch. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

## 1. Modules and entry points

| Image | Role (T136/T156) | ELF entry | functions (chunks) / call targets | code range | C0 / C1 `spu_recomp.c` SHA-256 |
|---|---|---|---|---|---|
| 341580667 `spu_45c1b7bf…` | wave 1, solver | `0x3080` | 959 / 109 | `0x3010`–`0x182E8` | `837dfac94ff539812fa66ce840bb6443edf8b5e063717924525dd2faa4ff337b` / `ec5eeebf57786c729622dbc3e088353ca6e01ecb7010d59777372068a3c19be4` |
| 491898574 `spu_d51c6ceb…` | wave 2, collide | (task entry) | 1,766 / 160 | `0x3010`–`0x25A60` | `8666947d76419d0e221c03dd168fe0561c20ccfbb102370f7a1d92e040aff829` / `3c0d580ff58ea44ee8bf3e189079b50ca0f82676180fde0d189bd2546816f5f6` |
| 308733018 `spu_266e45a8…` | wave 3, raycast | | 1,582 / 139 | `0x3010`–`0x23680` | `868765fa467ceb9383588d4149d80057df405b4dd713e785d02e8758df908e3f` / `3ac9de21deef297a1883adb81f1c74011346eb313ce2ba9566b551905132347a` |
| 406081863 `spu_83451471…` | wave 4, animation | | 821 / 98 | `0x3010`–`0x14868` | `481586bb91badf3549a1dda8cb936d4578fda53a8624f6d235b0fcbe4f8a77bc` / `9c91cee4114c9cf38efacc2e369a6f568e4cc053e1439670b2bc71c90d3d8b1f` |

Static code properties (T156 census, `t156/logs/spu_census.txt`, and §3 of `SPU_CHAIN_CHUNKS_VALIDATION.md`):
- solver: 20,361 lifted statements, 83 MFC command sites, 56 tag waits, 16 atomic-status reads, 10 indirect branches, 255 calls;
- collide: 32,861 statements, 77 MFC sites, 118 indirect branches, 529 calls;
- registers live in `ctx->gpr[128]` in memory: every SPU instruction is a C statement `ctx->gpr[n] = spu_op(...)`;
- LS access is one masked load or store plus a 4 × bswap shuffle (`pshufb`).

## 2. Method

**Sampler.** `hvkdiff prof` runs the accepted harness cases of one image in a loop (cases ≥ 20,000 SPU instructions only, so per-run setup is excluded).
- A second thread suspends the running thread about every 25 µs while it is inside a lifted run and records its RIP.
- `tools/hvk_prof.py` symbolises each RIP from the PDB with inline frames.
- Each sample is attributed to the lifted C statement (`spu_recomp.c` line) it belongs to, and to the innermost inlined helper.
- Logs: `logs/hvk_prof.txt`; 61,000–590,000 samples per arm.

**Measured vs inferred.**
- The classes below are **measured** sample shares of host execution on synthetic states.
- The split of the "lifted body" class into register traffic versus address and branch glue is **inferred** from the x64 (§4).
- Nothing here is an in-game profile. The in-game DMA/atomic share is BLOCKED: it needs the T156 arm D (`PS3_SPU_TASK_STATS`).

The solver's long cases are three runs of a single tight search loop (`0x7C48`), an artefact of random inputs. Collide and animation (32 and 7 distinct long cases) are the representative rows.

## 3. Where the time goes

Share of samples (collide / animation; solver in brackets):

| Class | C0 (standard lift) | C1 (`--chain-chunks`) |
|---|---|---|
| Drain loop and hop runtime (`SPU_DRAIN`, `spu_drain_call`, `spu_task_step`) | 32.8 % / 23.4 % (46.0 %) | 1.0 % / 0.4 % (0.8 %) |
| `spu_pchist_tick`, a diagnostic hook called out of line on every hop (inactive unless `SPU_PCHIST`) | 14.4 % / 10.3 % (24.9 %) | ≈ 0 |
| `spu_tailret_enabled` (per hop) | 1.6 % / 1.3 % (2.2 %) | ≈ 0 |
| Block transfers inside lifted code (trampoline stores in C0; `SPU_CHAIN` guard, pc, step in C1) | 7.3 % / 9.2 % (8.1 %) | 11.8 % / 12.2 % (24.6 %) |
| Integer / shuffle / logic statements | 16.4 % / 15.7 % | 40.3 % / 34.8 % (45.5 %) |
| Float statements (inline exact SSE4.1 forms) | 7.0 % / 11.4 % | 15.9 % / 23.8 % |
| Exact float fallbacks out of line (`spu__x4_fma_fix`, `fa_fix`, `fm_fix`, `spu__sf_sum`) | 3.4 % / 10.7 % | 9.5 % / 21.9 % |
| Local-store access statements | 7.6 % / 2.5 % | 13.3 % / 5.3 % (18.9 %) |
| Conditional branch tests | 1.0 % / – | 2.5 % / – |
| Indirect-branch dispatch | < 0.3 % | < 0.6 % |
| Call brackets (host call, `spu_drain_call`, `spu_img_restore`) | not visible (< 0.1 %) | not visible |
| `getenv` from `spu_run_with_halt` (once per run: `SPU_ARGWATCH`) | 1.3 % / 0.2 % | 4.2 % / 0.6 % |

Reading the table:
- **Branch dispatch dominated C0.** 44–81 % of C0 samples are the hop, its hooks and the trampoline stores. C1 removes almost all of it; that is the C1 / C0 ≈ 0.65 of §5 in the validation report.
- **In C1 what remains is the SPU work and the code around it.** The innermost-frame view of collide C1: 41 % of samples sit in the lifted statement bodies themselves, outside any helper. Then LS reads 6.7 %, shuffle/rotate helpers about 9 %, the float emulation helpers about 16 % (`trunc0`, `fa`, `twosum` and the fixes), LS writes 1.7 %. Animation C1: 31 % in bodies, float about 30 %.
- **Float fallbacks are inflated by synthetic inputs.** One quadword in eight holds raw bits, so NaN, infinity, extended-range and denormal lanes are far more common than in physics data. Their share here is an upper bound.
- **Calls are invisible here.** The accepted cases are mostly leaf-heavy; the main task loops do DMA and are refused. The in-game call cost is unmeasured.
- **The `getenv` row is a harness artefact.** It runs once per task run, so it costs microseconds per 8 ms task in game.

## 4. Remaining overhead in C1, by mechanism (x64 of the hot loop `c1_solver_spu_grp_00007C48`, `scratch/grp7c48.s`)

One iteration of the 8-instruction search loop compiles to about 60 x64 instructions:

| Part | x64 instructions per iteration | Notes |
|---|---|---|
| Guest-state materialisation | ≈ 14 | every SPU result stored to `ctx->gpr` (`movdqa xmm, off(%rsi)`) and most operands reloaded |
| Two chained transfers | ≈ 26 (2 × 13) | 3 global loads (`g_spu_chain_on`, `g_yz_lockstep_on`, `g_pm_flow_ctx`), interrupt-enable and `event_status` test, `steps++` in memory, `pc` store, budget decrement |
| LS load | 4–5 | mask, unaligned load, `pshufb` |
| Arithmetic | ≈ 15 | `shli`, `a`, `rotqby` (shuffle-control generation), `clgt` (`pminud` / `pcmpeqd`) |

Two conclusions from this:
- **The chain guard looks expensive in instruction count but costs little in time.** T158 built and measured an opt-in `--chain-hoist` that reads the three globals once per group entry and after every runtime call instead of per transfer (`SPU_AOT_OPTIMIZATION.md` §3). It changed time by only −0.0 to −2.3 %: the loads hit L1 and the branches are perfectly predicted.
- **The largest remaining mechanism is register traffic through memory.** It is structural: no compiler can keep `ctx->gpr` in registers across the lifted statements' memory side effects and exits. It is the "lifted body" class of §3 (31–41 % of C1 samples).

## 5. Classes the brief asked for

| Brief class | Measured (offline share, C1 collide / animation) | Status |
|---|---|---|
| 1. SPU arithmetic | integer/shuffle 40 / 35 % + float 16 / 24 % + exact float fallbacks 10 / 22 % (synthetic upper bound) | PARTIAL (synthetic operands) |
| 2. Branch dispatch | C0: 44–81 %; C1: block transfers 12 % + drain 1 % + indirect < 1 % | VERIFIED offline |
| 3. Guest-state materialisation | included in the arithmetic and LS statement shares; ≈ 14 of 60 x64 instructions in the hot loop; 31–41 % of samples in statement bodies outside helpers | inferred (x64) |
| 4. LS access | 13 / 5 % (statements), 7–8 % in the inline LS helpers | VERIFIED offline |
| 5. Memory synchronisation (DMA, atomics) | not in the harness (channel cases refused) | BLOCKED offline; arm D in game |
| 6. Host function calls | call brackets < 0.1 % in these cases; `getenv` once per run | PARTIAL (leaf-heavy cases) |
| 7. Other generated-code overhead | hop hooks (`spu_pchist_tick`, `spu_tailret_enabled`) 12–27 % in C0, ≈ 0 in C1 | VERIFIED offline |
