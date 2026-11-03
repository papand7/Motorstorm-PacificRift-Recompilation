# T187: MFC de-serialization (`PS3_SPU_MFC_FAST`), offline results

T186 item 1. Branch `agent/t187-spu-mfc-fast` in `ps3recomp-t187`, from T183 code `766d3575`; code commit `34954d66`.
Local only: not pushed or merged. No game launch was made.

## Change

The switch is `PS3_SPU_MFC_FAST`. It is read once; any value other than exactly `1` means off.
**Off (the default) keeps the original path**: one global lock-line TTAS lock and the global SRW lock in `mfc_for()`.
The only additions on that path are one mode check and one extra call layer.

When on:

1. **Striped lock-line locks.** There are 16 cache-line-padded stripes, hashed as `l=ea>>7; (l^(l>>4)^(l>>8))&15`.
   The SPU's own single-line transactions (GETLLAR, PUTLLC, PUTLLUC, WrEventAck) take only their line's stripe.
2. **Exclusive global lock.** `spu_lockline_lock()` sets an exclusive flag and waits for all stripes to drain
   (a Dekker pair with seq_cst operations; a stripe holder that sees the flag backs off).
   Every other caller keeps the old global guarantee: PPU coherent stores, cellSpurs, DMA PUT/SDCRZ, workload and registration.
   The only new concurrency is between SPU transactions on different stripes.
3. **Per-thread MFC engine cache** for `mfc_for()`. A TLS entry holds (ctx, engine, generation).
   The generation is bumped before every engine release or forget, so a freed or reused engine is never returned.
4. **Per-thread PUTLLC counter**, added to the global count in batches of 64.

What a stripe holder touches, checked for concurrent safety:
- The coherency bitmap is now set with an atomic OR.
- The reserver list is read-only under a stripe. A new registration falls back to the exclusive lock.
- The notify walk can at worst drop a reservation spuriously, which the architecture allows.
- `ppu_resv_break_line` and the coherency line hook are unaffected by concurrency.
- `spu_taskset_lfq_register` gets its own small spinlock in fast mode.
- EventAck takes the stripe of the context's own `resv_ea`.

Statistics are printed to stderr: a one-time `[spu-mfc-fast] on: …` line, then
`[spu-mfc-fast] stripe= backoff= excl= excl_spin= mfc_hit= mfc_miss=` every 2^22 stripe acquisitions.

Guest code was not relifted, and nothing outside the MFC and lock-line path was changed.

## Offline results

| Test | Result | Label |
|---|---|---|
| New `test_spu_mfc_fast`, semantics (19 checks), switch off and on | PASS. A PUTLLC commit breaks the peer, whose PUTLLC then fails and writes nothing; a bystander on another line is unaffected; PUTLLUC breaks all holders; a PPU coherent store and a DMA PUT break holders, but the DMA issuer keeps its own; EventAck clears; the engine cache never returns a released engine | VERIFIED |
| Stress: 5 SPU threads on 24 lines (half on one line), PUTLLUC and DMA PUT on a marked line, a PPU thread under the global lock, a churn thread that reuses one ctx address | off and on: lost=0, torn=0, nonuniform=0, bad_stat=0 | VERIFIED |
| Soak: 5 runs × 2M rounds per mode, about 10.6M increments per run | 0 lost, 0 torn in both modes | VERIFIED |
| AddressSanitizer (clang 23), both modes | PASS | VERIFIED |
| ThreadSanitizer | not practical: clang's TSan is unsupported on Windows and this machine has no WSL | BLOCKED |
| Existing `test_spu_event_lr_race`, switch on | PASS (0 LR events lost) | VERIFIED |
| Full suite `run_all_t187.py ps3recomp-t187` | 161 PASS, 43 SKIP, 2 FAIL. `test_spurs_kick_wake` is a known flaky timing check that also fails on T183. `test_t170_perf` (RSX readback, not touched by T187) then passed 3/3 on both T187 and T183 when rerun | VERIFIED (no T187 regression) |
| Game exe `build/motorstorm-t187` (T183 recipe, port-t161) | rc=0, sha256 `8fb1e26f9cf3eb1e9e8034b1dd72795eff89e30d53a176a86cc44cc1f199faef` | VERIFIED |

The POSIX-only registry tests (`test_spu_lockline_peer`, `test_spu_coherency`, `test_spu_mfc_slots`) skip on Windows.

### Microbenchmark (O2, median of 3 runs, ns per op, log `logs/bench.txt`)

| Case | T183 base | T187 off | T187 on |
|---|---:|---:|---:|
| GETLLAR+PUTLLC, own line, 1 thread | 115.0 | 110.2 | 58.6 |
| GETLLAR+PUTLLC, own line, 5 threads | 1,318 | 1,303 | **181** |
| GETLLAR+PUTLLC, one shared line, 5 threads | 3,742 | 3,624 | 2,109 |
| MFC channel write, 1 thread | 12.3 | 11.7 | 3.8 |
| MFC channel write, 5 threads | 171.8 | 174.8 | **6.5** |

- With the switch off, T187 runs at the same speed as T183, within noise. VERIFIED
- With it on, the cost of contention between SPUs on different lines drops by about 7× for lock-line operations and about 27× for MFC writes. VERIFIED (microbenchmark only)
- What this means in game is not yet known. The 1–5 ms per frame estimate remains a HYPOTHESIS.

## Limitations

- **Same-line spinners gain nothing from striping.** The Havok solver's ticket lock at `0x1781C` is one example; that is T186 item 2, not done here. The shared-line row above only gains from the counter and engine cache.
- **Exclusive acquisitions cost more in fast mode**, because each one scans 16 stripes. These are PPU coherent stores to marked lines, DMA PUTs to marked lines, and cellSpurs. If they are frequent in game, they could cancel the gain. The `excl=` and `excl_spin=` counters are there to measure this.
- The lock favours writers without fairness, as before. The existing plain-int `resv_valid` races are unchanged.
- No offline test reproduces the game's real Havok and Wws access mix.

## Proposed A/B protocol (for approval; no launch made)

- **Runner:** `generated/analysis/t187/ab/run_t187.py`. It is prepared and its envcheck passed; the launch cap is 4.
- **Exe:** the same pinned exe `8fb1e26f…` for both arms.
- **Arm P:** T184 arm P's environment unchanged (arm S + `PS3_SPU_TASK_POOL=1`), with the switch off.
- **Arm F:** arm P + `PS3_SPU_MFC_FAST=1`. envcheck confirms this is the only difference.
- **Order:** P, F, P, F (minimum P, F).
- **Clean machine:** Godot, Ollama, llama-server, LeOffice, Epic and EA closed or suspended, with enough free VRAM.
- **Shader cache:** the warm T183/T184 cache, copied.
- **Metrics:** race frame time (mean and median) from `[rsx-frame-perf]` and the `[PT]` join. Also the Havok wait and the Wws guest phases, the `[hle-wait]` and `[sc-wait]` totals, and the `[spu-mfc-fast]` counters (`excl`, `excl_spin`, `backoff`, cache hit rate).
- **Arm P as a reference:** arm P on the T187 exe should match T184 arm P (68.51 ms, 14.60 fps) within noise. This checks the exe.
- **Accept arm F if** frame time falls by more than the P-to-P spread, the race is reached, and there are no hangs, LR stalls, `[spu-mfc-fast]` anomalies or visual regressions.
- **Reject or investigate if** the gain is within noise, or if `excl_spin` is high (exclusive contention).
- **Target:** 30 fps remains the evidence-supported target; 60 fps is not.
