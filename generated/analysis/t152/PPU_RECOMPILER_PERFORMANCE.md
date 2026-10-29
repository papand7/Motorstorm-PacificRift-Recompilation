# T152: PPU main-thread and recompiler performance

Labels: VERIFIED (measured or read in code), PARTIAL (offline or single run), HYPOTHESIS (inferred), BLOCKED (needs a game run).

- **Not done:** no game launch, no push, no merge, and no change to physics, simulation, timing or guest instructions.
- **Built:** one exe (authorized), not launched.
- **Companion report:** `PPU_HOTSPOT_BREAKDOWN.md` (baseline, methodology, top 25, guest vs overhead, generated code).

## 0. Answer in brief

1. **Most of the 56 ms is waiting, not compute (VERIFIED from T149's own trace).**
   - Of the frame thread's 55.98 ms of running time per P1 frame, **33.66 ms (60%)** is the guest's frame-end busy-spin `0x50C818` on the SPU Wws job counters.
   - About **22 ms** is guest code. The spin ends when the SPU jobs end; those jobs run in the SPU interpreter in every `port/` build.
   - T106 measured the Wws job AOT in game (spin 12.5 → 0.3 ms, emit 21 → 6, PRE 54 → 40). It was never in `port/`; T152 adds it as a build option, and the T152 exe has it built in (`PS3_SPU_WWS_AOT=1`).
2. **The ≈ 22 ms of guest code carries real recompiler overhead (VERIFIED offline on real lifted functions).** Three opt-in fixes are implemented, each with differential tests:
   - **Indirect calls** (`PS3_ICALL_FAST=1`): 15.2 → 5.9 ns per hot call (2.6×), 35 → 27 ns with cold targets.
   - **One-load page gates for inline loads:** 5–13% fewer instructions and 23–39% fewer branches in real lifted functions. Default-equivalent: the gate admits a subset of the old inline set.
   - **Inline guest stores** (`MSPR_PPU_INLINE_STORES` + `PS3_VM_STORE_INLINE=1`): −31% on a real store-heavy lifted function; +3–5% with the switch off.
3. **Not attempted (largest remaining overhead):** guest registers live in `ctx` memory and every compare materializes CR. Fixing those needs register caching and CR/XER liveness in the lifter, plus a full re-lift (§9).
4. **Game FPS: unknown.** Every gain above is offline. §12 lists the A/B arms; it needs authorization.

## 1. Baseline

ps3recomp `80fe5de` (T146 unified tip; T153 published no newer baseline). Root repo `main` `4bdeed3`. Lift: `generated/ppu-hooked-staging`. Details: `PPU_HOTSPOT_BREAKDOWN.md` §1.

## 2–5. Profiling, top 25, overhead split, generated code

See `PPU_HOTSPOT_BREAKDOWN.md` §2–5.

## 6. Implemented optimizations

| # | Change | Where | Default | Commit |
|---|---|---|---|---|
| O1 | **Wws job AOT build option** `MSPR_WWS_AOT` (the T106 / `port-t70` block). All 35 units (31 modules, the register TU and 3 runtime TUs) compile against the T152 tree (`tools/aot_compile_check.cmd`). | root `port/CMakeLists.txt` | OFF (configure); run time `PS3_SPU_WWS_AOT=1` | `9cd7ef2` |
| O2 | **`PS3_ICALL_FAST=1`**: a registered, non-null indirect target is dispatched through a 256-entry per-thread direct-mapped cache.<br>Entries are tagged with a registry generation that every `ppu_register_function` bumps.<br>It engages only when none of the 20 probe switches of the full path is set.<br>Null, unregistered (OPD-swap, garbage-vcall, unresolved) and depth-capped calls fall through untouched. | `ppu_loader.cpp` | off | `aca2ebd` |
| O3 | **Page gates**: `vm_ld_page[ea>>16]` replaces the 4-global inline-load test.<br>The runtime fills the tables once, at the first out-of-line access after mapping, only where the old test admitted the whole page; all gates are closed before that.<br>Accesses that would cross a page go out of line. | lifter header template, `ppu_loader.cpp` | on (code shape only; same results) | `dcd62dc` |
| O4 | **Inline stores**: `vm_write*_inl`, used by TUs built with `PPU_INLINE_STORES`.<br>They take the inline path only with `PS3_VM_STORE_INLINE=1` and no store probe set or armable.<br>`vm_st_page` closes the first page, the raw-SPU windows and every page with an SPU-reserved line. `spu_coh_reserve` clears the page **before** marking the line, and the fill holds the lock-line lock. | header, `ppu_loader.cpp`, `spu_coherency.c`; root `port/CMakeLists.txt` | off twice (configure `MSPR_PPU_INLINE_STORES`, run time) | `dcd62dc`, root `20c3123` |
| O5 | **Profiler**: `PS3_SAMPLE_TOP=<n>` ranks up to 64 guest functions per `[samp]` report, each report being one interval. Used with the existing `PS3_SAMPLE=<ms>` and `PS3_SAMPLE_MAIN=1`. | `ppu_loader.cpp` | off | `9e393ce` |

**Applying O3/O4 to the existing lift without re-lifting:**
- `tools/make_t152_lift.py` copies the staging sources unchanged into `generated/ppu-t152-staging/`.
- It replaces exactly one verified block of `ppu_recomp.h` with the lifter's new block.

**Considered and not done:**
- **PUT-store drain wake (brief §8).** Feasible: close the gcm control page in `vm_st_page` and signal the frame clock's kick event from `vm_write32` on the PUT word.
  - Not done, because T151's `PS3_FRAME_CLOCK_KICK` already wakes on the guest's ref poll and T153 owns that integration.
  - T151 measured the drain-side wake at 8 µs vs 1.7 ms. The extra benefit of waking on PUT as well is unmeasured.
- **Plain (non-atomic) loads:** ≤ 1.5% instructions (§5 of the breakdown). The single-copy-atomic semantics stay.
- **Hardware `-mfma`/MOVBE:** changes the CPU baseline (an AVX2/FMA requirement) and was not measured here.

## 7. Correctness evidence

| Test | What | Result |
|---|---|---|
| `tools/test_icall_fast.py` (new) | Real `ppu_loader.cpp`; transcripts of the full and fast paths over 13 scenarios: 20,000 calls over 512 targets (cache eviction), explicit `ps3_indirect_call_to` target, null target, garbage vcall, OPD-swap, trampoline chain, re-registration after caching, nested depth/vcall stack, depth cap, consumed explicit target. A probe switch keeps the full path. | identical; 0 failures (VERIFIED) |
| `tools/test_vm_page_gates.py` (new) | Real loader + `spu_coherency.c`, 4 processes:<br>• load-gate rule;<br>• store gates off by default and with a probe (refusal reason printed);<br>• rwatch closes all loads;<br>• reservations before and after the fill close their pages;<br>• an inline-site store to a reserved line raises the SPU lost-reservation event;<br>• the first-page drop, the raw-SPU and ref-poll side effects, unaligned and 64 KiB-crossing accesses;<br>• **300,000 random loads/stores, inline vs out of line on twin regions with twin reservations**: same memory, same values, same lost-reservation events. | 31 checks, 0 failures (VERIFIED) |
| `bench_lifted` state hash | Real lifted functions `func_002D0D94` and `func_0096B648` on synthetic memory, under the staging header, page gates, and page gates + inline stores (switch off/on) | identical final guest state in every variant (VERIFIED) |
| `test_vm_store_fast`, `check_ppu_scaffold`, `test_ppu_trace` | T140 store differential (89 checks), scaffold, tracer, with the new header | pass (VERIFIED) |
| root `test_port_wws_aot_option.py`, `test_port_inline_stores_option.py` (new) | build options default OFF, fail closed | pass |
| Full suite (`tools/run_all_t152.cmd`, T146/T151 runner) | every `tools/test_*.py` plus the C tests | §7a |

**§7a. Suite (VERIFIED, `logs/suite_r1.txt`, `--jobs 3`, tree at `9e393ce`):** 135 PASS / 43 SKIP / 2 FAIL. T151 had 133 PASS / 43 SKIP with the same two failures, and the two extra passes are the new `test_icall_fast` and `test_vm_page_gates`. The two failures, `test_rt_pool_srv_layout` and `test_vpc_watch`, were already failing on the T146 base `80fe5de` and in T151 (outside T152's code). The timing-sensitive tests (`test_spurs_kick_wake`, `test_spurs_event_sched`, `test_timer_usleep`) passed under `--jobs 3`, so they were not rerun alone. The suite rewrote `scratch/ppu_conformance*` with local paths; those files were restored, and the tree is clean.

**Memory-model notes (VERIFIED in code):**
- Inline stores use relaxed host atomics for aligned accesses, as the inline loads already did.
- Guest `sync`/`lwsync`/`eieio` stay `PPU_FENCE`.
- Reordering that the compiler may now do between relaxed accesses to *different* addresses is within the PPC weak model; same-address order is kept.
- No raw-store or reservation path changed. T131/T140's raw-store gap (R1) is unchanged; `PPU_RAW_STORE_COH` still needs a re-lift.

## 8. Synthetic performance results (offline, single thread pinned, medians)

**O2, `bench_icall` (real `ppu_loader.obj` of each tree; `logs/bench_icall.txt`, 2 rounds):**

| Scenario | T146 | T152, switch off | T152, `PS3_ICALL_FAST=1` |
|---|---|---|---|
| 1 hot target | 15.19 / 15.25 ns | 15.29 / 15.95 | **5.91 / 5.86** |
| 16 targets round-robin | 15.52 / 15.53 | 15.65 / 15.62 | **6.23 / 6.31** |
| 2048 targets random | 33.85 / 34.96 | 35.25 / 35.51 | **26.58 / 26.24** |
| 65536 targets random | 35.64 / 37.17 | 36.72 / 36.31 | **28.40 / 27.67** |

**O3/O4, `bench_lifted`:** real lifted functions on synthetic memory, ms per call (`logs/bench_lifted_r1.txt`, `_r2.txt`). Values affected by host-load spikes are left out.

| Function | A: staging header | F: page gates | E: + inline stores, switch off | E: switch on |
|---|---|---|---|---|
| `func_0096B648` (16/32-bit ld/st) | 152–157 | 154–156 | 160 | **101–107 (−31%)** |
| `func_002D0D94` (CR/branch heavy, memory walk) | 544–576 | 522–562 | 488–533 | 535–594 |

- `func_002D0D94` is memory-bound and noisy (min–max spans 30%), so it shows no reliable difference.
- **Static instruction counts:** −5 to −13% instructions with F (breakdown §5).
- **Memory and CPU:**
  - The tables add 128 KiB of BSS; the icall cache adds 4 KiB of TLS per thread.
  - Inline stores grow lifted code by an amount still to be read from the exe size.
  - Single-thread benches: CPU use equals wall time.

**In game (HYPOTHESIS):**
- **O1:** in T106's measurement, the Wws jobs leaving the interpreter removed most of the frame-end spin. Here it could take up to about 30 of the 33.7 ms spin from the frame thread's running time. The frame then gates on whatever comes next (RSX, PRE).
- **O2–O4:** −1 to −4 ms of the ≈ 22 ms of guest code, depending on the store/load/indirect-call mix, which the profile run measures.

## 9. Remaining architectural bottlenecks (ranked)

1. **SPU-side Wws job time**, through the guest spin `0x50C818`: 33.7 ms of frame-thread running time.
   - O1 is the measured lever. After it, the SPU lanes' own throughput: T136 SSE4.1 is in; `PORT_SPU_AVX2` is OFF.
2. **Register caching in the lifter.**
   - Keep guest GPRs, FPRs, CR and XER in locals within a function. Write back at calls, trampolines, syscalls, indirect branches and returns; reload after them.
   - This removes rows 12–14 of the top 25 (about 3 memory ops per lifted statement) and most CR/XER work.
   - It needs a full re-lift (about 3.7 GB of output) and a lifter-wide differential test (the `test_ppu_lift` conformance set plus randomized blocks). Highest-value PPU item. Not attempted here because it cannot be validated without a game run and a re-lift.
3. **CR/XER liveness:** emit the branch on the compare directly when the CR field is dead after it (4.65 M compare sites, 1.77 M CA sites). It is part of 2, or a cheaper lifter pass on its own.
4. **Tail-call trampolines through TLS** (3.53 M sites): direct `return func_X(ctx)` tail calls where the target is in the same image, with the trampoline kept for the cross-image and unknown cases.
5. **`fmadd` via CRT `fma()`:** an inline FMA3 path behind a CPU check, or `-mfma` for an AVX2 baseline exe variant.
6. **Raw-store coherence and `stwcx.` design** (T140): correctness first; frequency unmeasured.

## 10. Integration-ready commits (handoff to T153)

| Repo / branch | Commit | Base | Files | Switch | Benefit (offline) | Tests | Conflicts / risks |
|---|---|---|---|---|---|---|---|
| ps3recomp `agent/t152-ppu-recompiler-performance` | `aca2ebd` | `80fe5de` | `runtime/ppu/ppu_loader.cpp`, `runtime/ppu/tests/test_icall_fast.cpp`, `tools/test_icall_fast.py` | `PS3_ICALL_FAST=1` | 2.6× per hot indirect call | test_icall_fast | **Risk:** a new probe added to the full path must also join `k_icall_probe_env` (the test pins this). **Overlap:** T150/T151 do not touch `ppu_loader.cpp`. |
| same | `dcd62dc` | `aca2ebd` | `tools/ppu_lifter.py`, `runtime/ppu/ppu_loader.cpp`, `runtime/spu/spu_coherency.c`, test pair | load gates always; stores `PS3_VM_STORE_INLINE=1` + build flag | loads −5–13% instr; stores −31% | test_vm_page_gates, test_vm_store_fast | **Lift:** takes effect only with the regenerated header (`make_t152_lift.py`) and a recompile of the lifted TUs. **Risk:** any future store probe must close the gates (documented in the header). |
| same | `9e393ce` | `dcd62dc` | `runtime/ppu/ppu_loader.cpp` | `PS3_SAMPLE_TOP` | profiler | compile | none |
| root `agent/t152-ppu-recompiler-performance` | `9cd7ef2` | `main` `4bdeed3` | `port/CMakeLists.txt`, `tools/test_port_wws_aot_option.py` | `-DMSPR_WWS_AOT=ON`, `PS3_SPU_WWS_AOT=1` | measured in game by T106 | pin + 35/35 compile | **Overlap:** T151's root branch touches `port/main.cpp` only; T150's `port-t150` is not in git. **Input:** uses private `generated/spu_raw/wws_reloc_t81c`. |
| same | `20c3123` | `9cd7ef2` | `port/CMakeLists.txt`, `tools/test_port_inline_stores_option.py` | `-DMSPR_PPU_INLINE_STORES=ON` | enables O4 | pin | **Dependency:** needs a header with the page gates. |

## 11. Runtime switches (all default off)

| Switch | Effect | Needs |
|---|---|---|
| `PS3_SPU_WWS_AOT=1` | Wws job modules run their AOT translation instead of the interpreter (T106/T109; refusals stay interpreted) | exe built with `MSPR_WWS_AOT=ON` (the T152 exe is) |
| `PS3_ICALL_FAST=1` | indirect-call fast path; ignored (with a log line) if any of its 20 probe switches is set | — |
| `PS3_VM_STORE_INLINE=1` | inline guest stores; ignored (with the reason) if a store probe is set | exe built with `MSPR_PPU_INLINE_STORES=ON` and the T152 header (the T152 exe is) |
| `PS3_SAMPLE=<ms>` `PS3_SAMPLE_MAIN=1` `PS3_SAMPLE_TOP=25` | frame-thread sampler with a top 25 of guest functions | — |
| (load page gates) | always on in a lift with the T152 header; no switch (same results by construction) | — |

## 12. Proposed game A/B validation (needs authorization; not run)

**Exe:** `build/motorstorm-t152/MotorStormPacificRiftRecomp.exe` (§12a).

**Runner:** T149's `t149/ab/run_t149ab.py`, same race, P1 preset. Accounting `RSX_FRAME_PERF=12,1,100000` + `PS3_CRITICAL_PATH_TRACE`. Two runs per arm, interleaved.

| Arm | Exe / switches on top of P1 | Question |
|---|---|---|
| S0 | T152 exe, no T152 switch | Default-equivalence. Same FPS and frame-thread running time as the T146 exe P1 (T149: 7.29 FPS, 55.98 ms). Also shows the page-gate effect and the inline-store off-cost together. |
| S1 | + `PS3_SPU_WWS_AOT=1` | Frame-end spin `0x50C818` (33.7 ms) and emit. T106 D reference. Watch for 0 NOSYS, 21 jobs per frame, and any AOT refusals in the log. |
| S2 | + `PS3_ICALL_FAST=1` | frame-thread running time outside the sites |
| S3 | + `PS3_VM_STORE_INLINE=1` | same; check the `[vm-gates]` banner page count |
| S4 | S1 + S2 + S3 | combined; FPS, frame p50/p95 |
| P | S0 with `PS3_SAMPLE=2 PS3_SAMPLE_MAIN=1 PS3_SAMPLE_TOP=25` (one run, not timed) | the first per-function top 25 of the frame thread, to rank the lifter work in §9 |

**Correctness per run:** same race progress and frame content as S0 (draw-gated captures), no `[ppu]` unresolved or garbage-vcall lines beyond S0's, and no `[spu-coh]` aborts.

**§12a. Exe (VERIFIED, NOT launched):** `build/motorstorm-t152/MotorStormPacificRiftRecomp.exe`, 411,887,104 bytes, SHA-256 `a7bcdfeefdcba7b731d6efb7d471448b577acb4890ab467783ceac3ac8d1d115`. It was built by `tools/build_t152.cmd` (log `logs/build_t152.txt`, 312/312 steps, rc 0, warnings only). The exe is 9,359,872 bytes (+2.3%) larger than T151's (402,527,232), from the inline-store code plus the 31 Wws AOT modules. With no T152 env set, the only change from T146 is the one-load page gate for inline loads, which accepts the same pages the old 4-global gate did (§7). Inline stores, the indirect-call fast path and the Wws AOT are all off until `PS3_VM_STORE_INLINE=1`, `PS3_ICALL_FAST=1` and `PS3_SPU_WWS_AOT=1` respectively.
