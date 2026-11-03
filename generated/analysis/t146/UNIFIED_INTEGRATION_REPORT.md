# T146 — Unified performance and visual integration

Branch `integration/t146-unified-runtime` (ps3recomp), worktree `ps3recomp-t146-integration`.
Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. No game launch, no push, no GitHub, no source branch modified.

Companion files: `INTEGRATION_STATUS.md` (one-line status per task), `RUNTIME_SWITCHES.md` (every switch),
`presets/` (four presets), `logs/` (suite, harness, build), `tools/` (runners, build script, conflict resolver).

## 1. Starting point

- 117 ps3recomp worktrees and ~150 branches inspected. Ancestry (`merge-base`, `git cherry` patch-ids), not reports, decided
  what was already integrated.
- **Base `07b453f` (T141 tip)**. It already contains, by ancestry or patch-id: T105, T107, T108, T110, T113, T114, T115
  (`4a74174`), T120, T133, T137, T141, and T102's two renderer commits (as `470785e`/`4d7e84c`). It is the newest
  renderer line with the most offline validation, and every later RSX task (T142, T143, T144, T145) forks from it.
- Two other lines had to be joined to it:
  - **Performance/SPU line, T140 tip `e701fb7`** (on T113 `2562ba8`): T122 → (T134's `-x` cherry-picks of T102–T109, T106
    maxContention default `b84ed80`, T123, T123B, T121) → T134 → T140. T134 had already rebased the SPU stack onto T122,
    so T122 necessarily enters with that line.
  - **Side branches on `e3b961d` / `2562ba8`**: T115B, T116 → T117, T119, T131, T132 → T132B, and T136 (3 commits on T123).
- Not ancestors of anything: T142, T143, T144 (RSX), T145 (contains T142), T118.

## 2. Integration ledger (source → integrated)

Stage A — core runtime correctness

| Integrated | Source | Change |
|---|---|---|
| `82c1480` | T131 `8208c94` | SPU overlay evidence tool |
| `d5edebc` | T131 `1784e41` | VMX compare/CR6 aliasing test |
| `482aa13` | T132 `f3f9376` | atomic pending-flip take |
| `63750dd` | T132B `8dff95e` | `PS3_SIM_PACE` (opt-in, off) |
| `1aeb09e`, `80fe5de` | T118 `8d244ec`, `c417517` | cellAudio honours initial port gain; opt-in SPU exit diag |

Stage B — SPU/SPURS/PPU (merges keep the original commits and attribution)

| Integrated | Source | Change |
|---|---|---|
| `b06e733` (merge) | T122 `2b639c2` | D3D12 submission/sync, tex-snapshot epoch (prerequisite of the rebased SPU line) |
| `752a3c5` (merge) | `ea0ba12` (T134 line) | T102–T106 SPU fixes, maxContention default, T109 AOT/READY_LEVEL/SC_WAIT, T123, T123B |
| `1cb4b5e` (merge) | T140 `e701fb7` | T121 usleep spin, T134 critical-path trace, T140 store fast path / RESV_STORE / RAW_STORE_COH |
| `0af0496`, `47e7538`, `28691bf` | T136 `6bec559`, `25b304c`, `78fcf2b` | SSE4.1 SPU paths |

Stage C — renderer foundations

| Integrated | Source | Change |
|---|---|---|
| `9796324`, `e5e523f`, `5c00c66`, `1ba4e71` | T119 `3c1dc21`, `a1875dd`, `be4f4e7`, `693169a` | draw split, getenv once, VS memo, `RSX_VP_COMPACT` |
| `4c4ee7d` | T115B `65d2695` | exact texture cache |
| `2f8f121`, `cf70862` | T116 `c8d8a0a`, `30b817b` | shader/PSO cache (**conflict resolved, key bug fixed**) |
| `92b5745` | T117 `fd97181` (partial) | FP refuse-without-END; fixed 16 KiB window superseded |

Stage D — visual fidelity

| Integrated | Source | Change |
|---|---|---|
| `deb9deb`, `8864547` | T142 `a5171d6`, `e9f3237` | only fetched units claim RT windows |
| `dd04a88`, `e8b9153`, `bde0dd4` | T145 `49fc83f`, `1dff0eb`, `f7f9366` | `RSX_SHADER_WINDOW` (**conflict resolved, key bug fixed**) |
| `345c083`, `e42e2c0` | T144 `121879f`, `c31aa83` | `RSX_STENCIL_EXACT` |

Stage E — D3D12 performance

| Integrated | Source | Change |
|---|---|---|
| `a0ed1c5`, `618981c` | T143 `e2f9435`, `efae357` | SRV reuse, bind dedup, GPU profile (**wrappers unified with T122**) |
| `8dba04c` | T146 | T122 end timestamp stays right before Close |
| `23751b8`, `e7ec0ae` | T146 | regression pins follow integrated behaviour; restore test-rewritten `scratch/ppu_conformance.*` |

All cherry-picks use `-x`; T146's own resolutions are described in each commit message.

## 3. Conflict resolutions (semantic, not just textual)

1. **T116 × T120/T137 — pipeline-key truncation (bug found and fixed).** T116's `vp_fp_remember_failure` took the FP
   pipeline's depth key as `u32`, written before T120 widened it to `u64`. T137 keeps the MSAA sample/coverage byte in the
   top bits, so with `RSX_SHADER_CACHE>=1` a remembered compile failure would have been stored under a truncated key: it
   never matches (silent recompiles) and its slot keeps a stale upper half. Fixed to `u64`.
2. **T116 × T145 — WPOS key missing from remembered failures (bug found and fixed).** T145 adds `wpos_key` to the FP cache
   entry and the lookup compares it; T116's failure memo did not set it, so a remembered failure would carry a stale
   `wpos_key` from the slot's previous occupant (a failure under one window could answer for another, or a success could be
   shadowed). The memo now takes and stores `wk`.
3. **T116 × T113** — colour-transfer unit masks read `fsz` (FP span), not 4096.
4. **T117 × T113** — both fixed the 4096-byte FP truncation. T113's END-based `RSX_FP_SPAN` (≤64 KiB) is runtime-VERIFIED
   (0x07200641 compiles, white sheet gone); T117's fixed 16 KiB `D3D_FP_UCODE_BYTES` would cap long programs again and
   conflicts in 15 walks. Kept T113's walks, took T117's decoder half (no END in the window → refuse, never emit a head).
   T117's pin now checks "no fixed 4096 walk, every walk reads `fsz`"; T113's `test_fp_span` now expects the old 4096 read
   to be refused. (T147, a parallel visuals integration, made the identical choice independently.) T142's fetched-unit rule
   and T145's surf program 0x07200641 therefore see the whole program.
5. **T122 × T143 — one wrapper implementation.** Single `ResourceBarrier` macro feeding T122's always-on `s_gsy_barriers`
   and T143's `GP_C_BARRIER`; T122's separate macro removed. `wait_for_gpu()` stays T122's `wait_for_gpu_at(__LINE__)`
   (per-site counts); `wait_for_gpu_at` is now T143's RSX_GPU_PROF timing shell around `wait_for_gpu_at_` (T122's body).
   Both timestamp sets kept (`gts_*` for RSX_GPU_SYNC, `gp_*` for RSX_GPU_PROF); T122's end timestamp moved after T143's
   resolve so it stays immediately before `Close`. `present_fence` keeps T122's `+1` fence semantics. Exactly one
   `#define ResourceBarrier` and one `#define wait_for_gpu()` remain (pinned).
6. **T143 × T144** — PSO/stencil-ref dedup keeps T144's "stencil test on the shared depth buffer" log after the
   (possibly skipped) `OMSetStencilRef`.
7. **T143 descriptor reuse vs lifetime** (re-checked on the integrated code): every resource creation in the backend and
   its headers goes through `CreateCommittedResource` (no placed/reserved/shared resources), which bumps `s_res_gen` and
   empties the window cache; T115B re-uploads in place (same resource → same views); T141 feedback snapshots and T120
   windows are distinct resources whose views carry the resource pointer; descriptors do not capture contents, so a shared
   window reads exactly what an identical new window would at execution time.
8. **Clean textual merges reviewed**: `cellGcmSys.c` (T132 atomic flip + T106 SPU-PUT lock), `render_frame` (T134 spans +
   T141 feedback + T122 fences), T115B uploader vs T120/T133 (no conflict).

## 4. Excluded / pending

| Item | Reason |
|---|---|
| T117 fixed 16 KiB window | superseded by T113 FP span (VERIFIED) |
| T144 SPURS `PS3_SPURS_LANE_HANDOFF` | uncommitted in `ps3recomp-t144s` (modified today 18:03–18:09, possibly an active agent); its own synthetic result is a net regression in default-like arms |
| misc-hle-features (5 commits) | real host file deletion in cellFs/savedata needs a separate review; not performance/visual |
| T111 mod framework | offline tooling only |
| WWS AOT exe variant | runtime code integrated; enabling needs the `MSPR_WWS_AOT` block (`port-t106aot`), a build decision outside ps3recomp |
| `PPU_RAW_STORE_COH` in the exe | needs a re-lift of the PPU code |

## 5. Tests (all on the integrated tree; logs in `logs/`)

**Suite** (`tools/run_all_t146.cmd`: every `tools/test_*.py` of the tree + 22 header/WARP C tests; `logs/suite_t146_r1.txt`):
126 PASS, 43 SKIP (POSIX-only / Metal fixtures), 8 FAIL in the first run. Resolution of the 8:

| Test | Cause | Action | Now |
|---|---|---|---|
| `c_fp_span`, `c_t133_image_quality` | runner did not link D3D libs | runner fixed | PASS |
| `test_fp_span` | T117 × T113: old 4096 read is now refused | expectation updated (`23751b8`) | PASS |
| `test_rt_pool_srv_layout` (window pin) | T143 binds `s_srvw_of[d]` | pin updated | that pin PASS |
| `test_present_progress` | T134 span declaration precedes `pp_note` (fails on T140 tip too) | pin updated | PASS |
| `test_cpath_trace`, `test_spurs_event_sched` | host contention during the parallel run | rerun alone on T146 and T140 | PASS both trees |
| `test_rt_pool_srv_layout` ("pool evicts only unused"), `test_vpc_watch` | **pre-existing** on the T141 and T140 tips (T110 RTPOOL_GF change; fixture lacks `<time.h>`) | none (not T146) | FAIL on base too |

Highlights passing: `test_ppu_lift` 1533/1533, `test_vm_store_fast`, `test_spurs_wws_stress` / `_concurrency`, `test_spurs_admit`,
`test_spu_fp_cache`, `test_spu_exec_sse`, `test_timer_usleep`, `test_ppu_vmx_lanes`, `test_spu_overlay_evidence`,
`tests/test_spu_reloc_job.py`, `tests/test_spu_switch_linkret.py`, `test_gpu_sync`, `test_tex_snapshot_epoch`, `test_bind_dedup`,
`test_d3d12_shader_cache` (incl. WARP PSO library), `test_t119_pins`, `test_t115b_pins`, `test_shader_window`, `test_stencil_exact`,
`test_blend_feedback`, `test_msaa`, `test_rt_window`, `test_t110_pins`; C: `t110/t115/t115b/t137/t141/t144/t145` WARP tests (debug layer),
T118 `test_audio_offline_win` 12373 checks and `test_spu_exit_diag` 9 checks.

**Real-backend D3D12 harnesses** (`logs/harness_summary.md`; debug layer + GBV arms): T137, T141, T142, T144, T145 — every
arm identical to the result the task recorded; 0 debug-layer errors except T141 `base_gbv` 7 (recorded by T141). T137's zeta
line differs from T137's own record but identically on the T141 tip (T141's exact depth24, documented) — pre-existing.
**T143 identity** (switches on vs off): 40 arms, byte-identical RSXI snapshots in every deterministic arm, now also across
T145/T142/T144 arms; T141 `f_base` differs as recorded (undefined self-read). Harnesses need
`tools/harness/common/gcm_epoch_stub.c` to link any tree containing T122 (harness-only; the exe links `cellGcmSys.c`).
T143 perf: relative render-CPU gain holds (−30…−55%), absolute numbers not quotable (host 96–100% busy with an
unrelated program during the run).

**Not run:** VMX/SPU interpreter fixtures that need POSIX toolchains (SKIP, unchanged from every source branch).

## 6. Build (authorised; `tools/build_t146.cmd`, logs `logs/build_t146*.txt`)

- `build/motorstorm-t146/MotorStormPacificRiftRecomp.exe`, built from `80fe5de` (incremental after T118), Release,
  clang-cl 23.1.3, Ninja, `port/` (standard; no `MSPR_WWS_AOT`), `PORT_ENABLE_SPU=ON`, `PORT_SPU_AVX2=OFF`, `-msse4.1`,
  lifted PPU `generated/ppu-hooked-staging` (79 sources), SPU inputs `generated/decrypted/EBOOT.elf`. Same cache options
  as the T113/T122/T145 builds.
- **SHA-256 `ef0d32c8890edfbca863bfa7731912a5249510b7dd04eda9a1a35b6248814682`**, 402,522,624 bytes, AMD64 (0x8664).
- rc=0, no link errors or undefined/duplicate symbols (only the existing `-Wtentative-definition-compat` warnings in
  `spu_context.h`). 27 lifted SPU sources and 121 objects, same as `motorstorm-t122c`.
- Imports: d3d12, dxgi, D3DCOMPILER_47, XINPUT1_4, winmm, ws2_32, ole32, bcrypt, VC runtime — no Vulkan, no debug DLLs.
- Renderer integration visible in the binary: `RSX_SRV_REUSE`, `RSX_BIND_DEDUP`, `RSX_GPU_SYNC`, `RSX_GPU_PROF`,
  `RSX_SHADER_WINDOW`, `RSX_STENCIL_EXACT`, `RSX_SHADER_CACHE`, `RSX_VP_COMPACT`, `RSX_TEX_CACHE`, the T117 "no END within"
  message; SPU/PPU: `PS3_SPURS_EVENT_SCHED`, `PS3_SPU_FP_CACHE`, `PS3_VM_STORE_FAST`, `PS3_SIM_PACE`, `PS3_USLEEP_SPIN`.
- Private inputs unchanged: `EBOOT.elf` SHA-256 `bbb7fe25…b287` and the lifted-source aggregate `76568cce…f3` identical
  before and after (`logs/inputs_before.txt`). Nothing proprietary is committed (public audit of all 136 changed files passed).
- Defaults: none changed by T146 (§7). **Not launched.**

## 7. Runtime switches and presets

`RUNTIME_SWITCHES.md`. No default was changed by T146. Default-on behaviour comes only from source tasks: T106
maxContention, T113 write-back + FP span, T117 refuse-without-END, T119 VS memo + getenv-once, T122 fence changes,
T123 FP cache, T132 atomic flip, T136 SSE4.1, T140 store fast path, T118 audio initial gain.
Presets set every switch explicitly; opt-in switches are unset (not `0`, because not every parser treats `0` as off).
`visual-test` excludes `RSX_COLOR_XFER` and `RSX_FP_PRECISION` (never run in game).

## 8. Dependency graph

```
2562ba8 (T113) ─┬─ T122 ── T134 line (SPU T102–T109, T106 maxcont, T123, T123B, T121) ── T134 ── T140 ─┐
                ├─ T119, T131, T132 ── T132B                                                       │
e3b961d (T110) ─┼─ T115 ── T115B ; T116 ── T117 (decoder half; window ⇐ T113 FP span)              │
                └─ T113 ── T120 ── T133(+T115) ── T137 ── T141 = 07b453f ── T142 ── T145           │
                                                              ├─ T143 (wrappers ⇄ T122)            │
                                                              └─ T144 RSX                          │
T123 ── T136 (SSE4.1)                                                                              │
07b453f + A(T131,T132,T132B,T118) + B(T122→SPU→T140, T136) + C(T119,T115B,T116,T117) + D(T142,T145,T144) + E(T143) = T146
Runtime couplings: RSX_MSAA ⇒ GUEST_SAMPLERS=15; RT_FEEDBACK ⇒ RT_WINDOW; TEX_MIPS ⇒ GUEST_SAMPLERS (else trilinear);
STENCIL_EXACT ignored with DEPTH_STATE; SHADER_CACHE key ⊇ depth(u64,MSAA byte)+wpos_key+cmask(u32)+xfer.
```

## 9. Proposed runtime matrix (needs separate authorisation)

Same save/track, race entry + 90 s window, `RSX_FRAME_PERF=12,1,100000`, `PS3_SPURS_SCHED_STATS=1000`,
`SPURS_BUSY_MS=1000`, `RSX_GPU_PROF=300`, `PS3_VM_STATS` only in a separate arm (it disables the fast path). Analyse with
`t122/ab/ana_t122.py` and `tools/cpath_report.py`. Order A B C D E, then repeat (two runs each).

| Arm | Exe | Preset | Purpose |
|---|---|---|---|
| A | last verified (T122 exe C, `build/motorstorm-t122c`) | its recorded env | reference |
| B | T146 | `baseline` | integration regressions (expect ≥ A: maxContention + T140 + T136 now present) |
| C | T146 | `performance-test` | epoch, compact, shader cache, SRV reuse, event scheduler |
| D | T146 | `visual-test` | visual verdict by the user (race surf, water dots, mirrored WPOS draws, MSAA edges) |
| E | T146 | `combined-test` | both |

Measure race FPS, frame-time p50/p95/p99, PPU (main-thread phases), SPU lane utilisation, RSX record time, GPU time
(RSX_GPU_PROF timestamps), host CPU (critical-path sampler), working set, RSXI frame diffs (A vs B must be identical in
default state), crashes/hangs. Game speed stays tied to the fixed 1/30 s step (PS3_SIM_PACE off): an FPS change is not
evidence of correct simulation timing.

## 10. Known regressions, remaining defects, bottlenecks, priorities

**Known regressions:** none found offline. Two integration bugs were found and fixed (T116 failure-memo key vs T120/T137
and vs T145). Pre-existing failures carried over: `test_rt_pool_srv_layout` eviction pin, `test_vpc_watch` fixture.

**Remaining visual defects (all HYPOTHESIS until a game run):** surf band and water dots (T141/T145 candidates only);
the scene's colour transfers (race asks sRGB output on 634/1582 draws, gamma on 769) are not applied by default
(`RSX_COLOR_XFER` unverified); `SRC2.abs` not decoded (T145, latent); two fetched sizes of one RT in one frame (T142);
stencil clear values unknown (T144); MSAA 0x1D7C never captured.

**Remaining bottlenecks:** the race is guest-bound (T122: ~200 ms frames, draw callbacks 41–102 ms). With five lanes
the next gate is RSX vertex expansion / record (T106, T134); T119 compact + T122 epoch address it (drain 77→15.6 ms on the
T122 line). SPU lanes 68% idle waiting on readiness (T144). PPU store path, SPU float and fingerprinting are now cheap.
None of these combinations has run in game.

**Next priorities:**
1. Authorise the §9 matrix (A vs B first: integration regression check in default state).
2. If B ≥ A: decide defaults for `PS3_TEX_SNAPSHOT_EPOCH` (after reviewing `gcm_epoch_pure()`), `RSX_VP_COMPACT`,
   `RSX_SRV_REUSE`/`RSX_BIND_DEDUP`, based on C.
3. User visual verdict on D; only then consider `RSX_COLOR_XFER` and `RSX_FP_PRECISION` arms.
4. AOT exe variant (`port-t106aot`, `MSPR_WWS_AOT`) as an extra arm; T140 `PPU_RAW_STORE_COH` needs a re-lift.
5. Review/land T144 SPURS handoff only if its EL/ELH arms beat T123B event mode; review misc-hle-features separately.
6. Reconcile with T147 (visual-only integration, subset of T146's RSX stage) to avoid two canonical branches.
