# T140: PPU execution and memory-system performance

- **Date:** 2026-10-28.
- **Not done:** no game build, no launch, no merge, no push. No other agent's worktree was modified.
- **Labels:** VERIFIED (measured or read in code), PARTIAL, HYPOTHESIS (inferred, not measured), BLOCKED.
- **Paths:** relative to the workspace (`motorstorm/`).

## 0. Answer in brief

1. **What MotorStorm's lifted PPU code actually runs (VERIFIED, static).**
   - Loads are inline, behind one global flag.
   - Every scalar store is a call to the out-of-line `vm_write8/16/32/64`. There are about 3.9 million such call sites in the build's lifted source (`generated/ppu-hooked-staging`).
   - Raw stores are inline and unchecked: vector, byte-reversed and `dcbz`, about 99,000 sites.
   - `stwcx.`/`stdcx.` go to a runtime CAS behind a sharded spinlock.
   - Indirect calls go to `ps3_indirect_call`.
2. **The out-of-line store was 2.9–4.3 ns per store against 0.3 ns for the store itself (VERIFIED, real objects).**
   - It ran about a dozen diagnostic probes per store, then a cross-TU call to `spu_coh_is_reserved`.
   - **Implemented:** a single-gate fast path, on by default and with the same semantics. It brings the cost to **1.0–1.5 ns** (one noisy median 2.2 ns), 1.4–4.3× faster.
   - Whenever any probe is armed, the store takes the pre-T140 path unchanged. `PS3_VM_STORE_FAST=0` forces that path.
3. **Correctness gaps found.**
   - **VERIFIED:** raw stores bypass SPU lock-line coherence (T131's finding).
     - A synthetic race undid **179–772 of 300,000** raw stores with a racing lock-line read-modify-write.
     - **Implemented:** coherent raw stores, **opt-in** with `PPU_RAW_STORE_COH=1`. They need a re-lift and recompile of the lifted code. With them on: 0 lost.
   - **VERIFIED:** `PPU_RESV_STORE=1` never applied to lifted stores, only to `libs/`. **Fixed**; the switch is still opt-in.
4. **Real-game impact: unknown, probably small (HYPOTHESIS).**
   - The frame thread runs about 28 ms of a 129 ms frame in T106's best arm, and is not the current gate (the RSX is).
   - T25 found that inlining all loads moved main-thread busy time by an unmeasurable amount.
   - No run has ever counted stores per frame. **`PS3_VM_STATS=<ms>` (new, opt-in) does**; it is the first item of the A/B plan.

## 1. Baseline and setup

| Item | Value |
|---|---|
| Worktree / branch | `ps3recomp-t140` / `agent/t140-ppu-memory-performance` |
| Base | `b1ded1e`, the T134 tip. |
| Why this base | It is the only line that carries the PPU runtime together with all of these: the T121 usleep mode, T123/T123B SPURS scheduling, the guest maxContention, and the T134 critical-path profiler. That is the configuration the next race A/B needs (T134 §5). |
| T136 | Its SPU SSE4.1 commits touch no T140 file. Its other three commits on T140 files (`e48f279`, `4a1ee48`, `8f41c5c`) are already in T134 as cherry-picks. |
| T135 | No branch or report exists. T131's analysis (`Motorstorm01/generated/analysis/t131/RACIT_CROSS_PROJECT_ANALYSIS.md` §B.3) is the reservation reference used here. |
| Public push guard | `git -C ps3recomp remote get-url --push origin` → `DISABLED` (VERIFIED). |
| Build flags used for every measurement | Taken from `build/motorstorm-t122/build.ninja`: clang-cl 23.1.3, `/O2 /Ob2 -fno-strict-aliasing -fwrapv`, no LTO. |

## 2. Execution-path inventory (VERIFIED: code read, static counts over the staging source)

| Path | Implementation | Static sites in MotorStorm's lifted code | Per-op cost before (bench) |
|---|---|---|---|
| Scalar loads `lbz…ld`, `lfs/lfd` | inline `vm_read*_inl`: range test, aligned relaxed atomic load, bswap; out of line only with a read probe armed or for special words (null page, raw SPU, GCM ref poll) | 6.41 M (`vm_read32` 5.74 M) | 0.6–0.7 ns |
| Scalar stores `stb…std`, `stfs/stfd` (before T140) | **out-of-line call** `vm_write*` (`ppu_loader.cpp`): tracer hook, `PPU_WVAL`/`PPU_WWATCH` statics, Bink barrier watch, mapping and null-page guards, `PT`, a call to `spu_coh_is_reserved`, the store, raw-SPU register side effects | 3.94 M (`vm_write64` 2.16 M, `vm_write32` 1.22 M) | **2.9–4.3 ns** |
| Raw stores `stvx`, `stve*x`, `st*brx`, `stvlx/rx`, `dcbz` | inline `VM_RAW_ST`/`vm_raw_st16`/byte loop/`memset`; **no coherence** | ~99 k (`vm_raw_st16` 86.8 k, `VM_RAW_ST` 12.1 k) | 0.3–0.8 ns |
| `lwarx`/`ldarx` | inline load plus `ctx->reserve_*` | 1,442 | – |
| `stwcx.`/`stdcx.` | `ppu_stwcx32/64`: one of 1024 address-sharded spinlocks, re-check of the caller's reservation, seq_cst CAS, a scan of every registered context to break matching reservations, lock-line lock on SPU-reserved lines | 540 / 399 | 13.4 ns uncontended |
| Indirect calls (`bctrl`, vtables) | `ps3_indirect_call`: about 20 environment-gated probes, hash lookup, depth guard, trampoline loop | n/a | 7.0–7.3 ns |
| Guest address translation | `vm_base + (uint32_t)ea`: the whole 4 GiB is reserved, no page table, and `ppu_vm_size == 0` on Windows | everywhere | 0 (folded into the access) |
| Endianness | `__builtin_bswap*`; no MOVBE (no `-march`) | everywhere | <0.3 ns |
| Syscalls | `lv2_syscall` dispatch; mutex calls `sc102/104` cost 0.3–0.5 µs, at 70–760 per second per thread (T121) | – | not hot |
| Timer reads (`mftb`) | `ppu_timebase_now`: QPC plus a split multiply | – | QPC-bound; not measured here |
| Host waits | `sys_timer_usleep`: an HR waitable timer that fires on the host's 0.5 ms tick (T121); `PS3_USLEEP_SPIN=2` is opt-in | 1300–1500 calls/s on tid 1 | 520 µs per `usleep(250)` |
| PPU↔SPU coherence | `spu_coherency.c`: a 4 MiB bitmap with one bit per 128-byte line, **sticky** (set on GETLLAR, never cleared), and one global TTAS lock-line spinlock | – | 11.6 ns per store to a marked line; **260 ns/op with 4 threads** |
| MMIO | raw-SPU problem state at `0xE0000000 + n*0x100000 + 0x40000…`. Loads are out of line for the mailbox pop; `vm_write32` has register side effects | – | – |

Not used by MotorStorm's runtime path: the interpreter paths, the POSIX `ppu_vm_size` range check, and the `ppu_memory.h` inline accessors (HLE `libs/` only).

## 3. Ranked hotspots

Frame-level evidence (T106 arm D: five lanes plus the SPU job AOT, the best measured configuration): the frame is 129 ms. tid 1 spends 779 ms/s in `sys_timer_usleep`, so it runs **at most ~28 ms per frame**. The gate is the RSX `ref` wait, 82 ms (T134 §2).

| # | Item | Cost per op (VERIFIED, bench) | Frequency in the race | Critical path? |
|---|---|---|---|---|
| 1 | Frame-thread wake latency (`usleep` returns after 520 µs) | +270 µs per poll | 1300–1500 polls/s | **yes** (T121/T134; opt-in mode 2 exists) |
| 2 | Out-of-line scalar store | 2.9–4.3 ns → **1.0–1.5 ns** | unknown; 3.9 M static sites | only through the ≤28 ms of tid-1 running time, once the RSX gate goes (HYPOTHESIS) |
| 3 | Stores to sticky SPU-marked lines | 11.6 ns; 46–57 ns (2T); 256–269 ns (4T) | unknown (`st_coh` in `PS3_VM_STATS`) | unknown; the contention is with SPU lanes on the same global lock |
| 4 | `stwcx.` | 13.4 ns; 49–98 ns (2T); 175–585 ns (4T) | unknown (`sc_*` in `PS3_VM_STATS`) | unknown |
| 5 | `ps3_indirect_call` | 7.0–7.3 ns | unknown | not changed (see §9) |
| 6 | Syscall dispatch, lwmutex, lwcond | sub-µs | low | no (T121) |

Why the `stwcx.` contention is high even on separate words (VERIFIED, bench): each successful commit scans every registered context's `reserve_addr`, and the owners write that field on every `lwarx`, so the cache lines bounce. Two words 16 KiB apart also share one of the 1024 lock slots ("aliased lock slot": 300 vs 175 ns at 4T). The fix would be a different reservation design, not a shortcut, so it is not done (§5).

## 4. Memory-system architecture (VERIFIED, code)

```
lifted PPU code ──load──► vm_read*_inl (inline) ──[probe armed or special word]──► vm_read* (ppu_loader.cpp)
               ──store─► vm_write* (out of line) ──fast path (T140)──► bswap ─► line marked? ─no─► store
                                                    │                                      └─yes─► lock-line lock, store, notify SPUs, unlock
                                                    └─[any probe armed]──► vm_write*_full (pre-T140 path, unchanged)
               ──raw───► VM_RAW_ST / vm_raw_st16 / dcbz (inline) ──[PPU_RAW_STORE_COH and line marked]──► vm_raw_coh_begin/end
               ──atomic► lwarx inline; stwcx. ► ppu_stwcx32: slot lock, re-check, CAS, break the others' reservations
SPU GETLLAR ──► spu_coh_reserve: bitmap bit (sticky) + holder list;  PUTLLC / DMA PUT ──► lock-line lock
```

- **Translation:** `host = vm_base + (uint32_t)ea`. The 4 GiB is reserved up front, so there is no lookup, no TLB emulation and no bounds check on Windows. Translation is not a hotspot (T106 already found it inlined; confirmed here).
- **Visibility:** aligned accesses are single-copy atomic (relaxed host atomics). Barriers are host fences (`PPU_FENCE`). x86 TSO supplies the rest.
- **Reservations:** PPU reservations are per word (`reserve_addr`, with a value-CAS backstop) and broken by other threads' successful `stwcx.`. Plain stores break them only with `PPU_RESV_STORE=1`. The SPU reservation granule is the 128-byte line.

## 5. Implemented optimizations and fixes

| Commit | Change | Default | Behaviour change |
|---|---|---|---|
| `d27441d` | **Store fast path** (`ppu_loader.cpp`): `vm_write*` stores directly after one combined test. The test covers the environment-armed probes (`g_vm_store_slow`, read at the first store, the same first call at which the old statics read them), the run-time-armed ones (tracer window, barrier watch, null sweep, bounded mapping), the first page and raw-SPU registers. It then checks the SPU line inline. Everything else goes to `vm_write*_full`, which is the old body with the caller's return address passed through, so guest-function attribution is unchanged. The SPU bitmap is exported (`g_spu_coh_bitmap`, `g_spu_coh_armed`), with an unarmed default for fixtures that link the loader without the SPU runtime. Also **`PS3_VM_STATS=<ms>`**: per-interval rates of stores by width, stores to marked lines, `stwcx.` ok/lost/value-fail/on a marked line, and raw coherent stores. **`PS3_VM_STORE_FAST=0`** restores the old path. | **on** | none intended; the differential test shows identical memory and identical lost-reservation events |
| `32c1bd1` | **`PPU_RESV_STORE` on lifted stores**: `vm_write32/64_full` now break other threads' reservations on the stored word(s), as the HLE writers already did. Arming it routes stores to the full path. | off | only with `PPU_RESV_STORE=1` (the switch now does what it says) |
| `0ced9c5` | **Raw-store coherence** (lifter header plus emission, and the loader's `vm_raw_coh_begin/end`). `VM_RAW_ST`, `vm_raw_st16`, `stvlx/stvrx` and `dcbz` check the first and last byte's line. On a reserved line they store under the lock-line lock and raise the SPU's lost-reservation event (the same order as the scalar path: store, notify, unlock). The gate `g_ppu_raw_coh` is set from `PPU_RAW_STORE_COH=1` when the first line is reserved. `PPU_NO_RAW_STORE_COH` compiles the check out. **Takes effect only after a re-lift and recompile of the lifted code.** | **off** | only with the switch, after a re-lift |
| `e701fb7` | `runtime/ppu/tests/test_vm_store_fast.cpp` + `tools/test_vm_store_fast.py` | – | – |

Not done, deliberately:
- **Clearing sticky SPU bitmap bits:** a speculative reservation shortcut. It widens the existing first-reservation race to every reservation.
- **Lock-free `stwcx.`:** it needs a new reservation design, not an optimization of this one.
- **Inlining the stores into the lifted code:** it would need a full recompile of the proprietary lifted TUs. The out-of-line fast path takes most of the gain without one.

## 6. Reservation correctness findings

| # | Finding | Status |
|---|---|---|
| R1 | Raw stores (`stvx`, `stvebx/ehx/ewx`, `stvlx/rx`, `stwbrx/sthbrx/stdbrx`, `dcbz`) skip the lock-line lock and the SPU lost-reservation event. A racing PUTLLC-style read-modify-write of the line can then write a stale image over a PPU store. | **VERIFIED** in code (T131) and synthetically (179–772 of 300,000 lost, 3 runs). That MotorStorm hits it is **HYPOTHESIS**: it needs a raw store to a line an SPU holds, and no run has looked. Fix `0ced9c5` is opt-in. |
| R2 | `PPU_RESV_STORE=1` had no effect on lifted stores. | VERIFIED; fixed (`32c1bd1`). |
| R3 | The scalar coherence test reads only the line of the first byte, so an unaligned store that crosses into a reserved next line is not serialized (pre-existing). The raw path in `0ced9c5` checks both lines. The scalar path keeps the old rule so that `d27441d` stays behaviour-identical. | VERIFIED (code); not changed |
| R4 | The SPU bitmap is sticky: once an SPU has reserved a line, every PPU store to it takes the global lock forever. This is correct, but costs 11.6 ns, or 260 ns at 4 threads. | VERIFIED (bench); frequency is what `PS3_VM_STATS st_coh` measures |
| R5 | PPU reservations are per word, with the line only for SPU-originated breaks. Plain stores do not break them by default (the value-CAS remains the ABA backstop). | VERIFIED (code); unchanged |

## 7. Differential and correctness tests

`python tools/test_vm_store_fast.py` (CXX = clang-cl) builds the real `ppu_loader.cpp` and `spu_coherency.c` with the lifter's current header. **89 passed, 0 failed, in 3 of 3 runs** (`logs/test_vm_store_fast.txt`):

1. Byte order and width of every store form, unaligned, page-crossing, read back by lifted loads.
2. **Differential, fast vs full path:** 400,000 random stores (all widths, random alignment, line- and page-crossing, 32 SPU-reserved lines). Memory images and lost-reservation event counts are identical.
3. First-page stores are dropped in both modes. The raw-SPU register store keeps its side effect (32-bit only, as before); local-store addresses have none.
4. An SPU reservation is broken by every scalar width on its line, and not by a store to the next line.
5. The tracer window and the barrier watch, armed at run time, still see stores (the `[sync-write]` line is checked by the driver).
6. `PPU_RESV_STORE`: a plain `st32`/`st64` breaks another thread's reservation, and only on that word. Default: no break.
7. Raw stores, with coherence off and on: `stwbrx` form, `stvx` form, `dcbz`, and a line-crossing `st64` (both lines' holders). Data is checked too.
8. **Concurrency, lock-line race:** 300,000 scalar fast-path stores against a racing lock-line RMW: 0 undone. Raw stores with coherence on: 0. Off: 179–772 (R1).
9. **Concurrency, atomics:** 4 threads × 100,000 `lwarx/stwcx.` increments, plus 2 threads of plain 32/64-bit stores into the same lines. The counter is exact, neighbouring words are untouched, and the final plain values are exact.
10. The **lifter's emitted code** for `dcbz, stvx, stvlx, stvrx, stvewx, stwbrx, sthbrx, stdbrx`, lifted by the driver and compiled into the fixture: the event when armed, none when off, data stored.

Regression suites:
- On T140 and on the T134 base, identical results:
  - `test_ppu_lift`: 1533 conformance checks, 10 barrier checks, 0 failed;
  - `check_ppu_scaffold`: OK;
  - `test_ppu_trace`: PASS;
  - `test_cpath_trace`: 0 failures (T134 profiler compatibility);
  - `test_sc_wait_acct`: 0;
  - `test_timer_usleep`: PASS;
  - `test_spu_diag_tls`: PASS;
  - `test_spurs_wws_stress`: PASS;
  - `test_spurs_kick_wake`: 0 failures.
- `test_icall_watch` and `test_rt_vis_trace` fail on both trees with the same link error (`m.lib`, a POSIX `-lm` on Windows): pre-existing.
- Five loader fixtures skip on Windows (POSIX only).
- The `spu_coherency.h` users (`spurs_job.c`, `spurs_policy.c`, `spu_channels.c`, `spu_lifted_thread.c`, `cellGcmSys.c`) compile with the project flags.

## 8. Synthetic benchmarks (`bench/src/bench_mem.cpp`, `logs/bench_mem_ab.txt`)

- **Method:** linked against the real objects of each tree. 20 M ops × 7 repetitions, median. Single-thread cases are pinned to one core. Arms alternate base, new, base, new. Each cell below gives the two medians.

| Case | Base ns/op | T140 ns/op | Speed-up |
|---|---|---|---|
| `vm_write32`, coherence armed, plain line | 3.01 / 3.00 | 1.46 / 2.20 | 1.4–2.1× |
| `vm_write64`, armed | 4.17 / 4.25 | 1.25 / 1.49 | 2.9–3.3× |
| `vm_write8`, armed | 3.45 / 3.56 | 1.23 / 1.26 | 2.8× |
| `vm_write32` / `64` / `8` / `16`, unarmed | 3.12–3.25 / 4.20–4.32 / 3.30–3.36 / 2.92–2.94 | 1.25 / 1.00–1.01 / 0.96 / 1.14–1.35 | 2.2–4.3× |
| store to an SPU-marked line | 11.61 / 11.70 | 11.60 / 11.49 | = |
| 2T / 4T plain stores, own windows (total throughput) | 607–617 / 1084–1160 Mops/s | 948–1212 / 1621–2222 Mops/s | 1.5–2× |
| 2T stores to marked lines | 45.5–46.9 | 57.1–57.7 | **0.8× (regression, see below)** |
| 4T stores to marked lines | 256–264 | 263–269 | = |
| raw `st32` / `st128` / `dcbz`, gate off (new header) | 0.31 / 0.59 / 0.75 | 0.41 / 0.74 / 0.81 | +0.06–0.15 ns |
| same, `PPU_RAW_STORE_COH=1`, plain line | – | 0.67 / 1.12 / 0.86 | – |
| `vm_raw_st16` on a marked line, coherence on | – | 10.4 | – |
| `stwcx.` uncontended / indirect call | 13.4 / 7.0–7.3 | 13.8–13.9 / 7.4 | ≈ (+0.4 ns: the stats check) |

- **Regression:** two threads that do nothing but store to marked lines lose about 20% of throughput. The critical section is the same. The faster path leaves less time between acquisitions of the one global lock, so the threads collide more often. Single-thread and 4-thread costs are unchanged. This matters only if the game hammers SPU-marked lines from two PPU threads; `PS3_VM_STATS st_coh` shows whether it does.
- **Code size** (`tools/lifted_tu_size.py`, `logs/lifted_tu_size_010.txt`): one lifted TU, `ppu_recomp_010.cpp`, with 3,238 raw-store sites, compiled with the build's flags.
  - With the new header, `.text` goes from 7,390,738 to 7,597,229 bytes (+206 KB, +2.8%), about 64 bytes per site.
  - Over the ~99 k raw sites that is roughly +6 MB of lifted code (HYPOTHESIS: extrapolated).
  - This measurement swaps only the header; the `stvlx`/`dcbz` emission changes need a re-lift.
  - The store fast path changes no lifted code.

## 9. Expected real-game impact (HYPOTHESIS until the A/B)

- **Store fast path:** about 2–3 ns saved per scalar store on the PPU thread that issues it.
  - At 1 M stores per frame on tid 1 that is about 2–3 ms of the ≤28 ms tid-1 running time.
  - It shortens the frame only where tid 1's own running time is the gate: after T119/T122 remove the RSX `ref` wait (T134 §2: PRE + emit ≈ 46–49 ms).
  - T25's measurement argues for a small effect: inlining **all** loads (6.4 M sites) left main busy time within noise in the garage (47.8 vs 46–47 ms).
- **Other threads:** the SPURS lanes do not use `vm_write*` for SPU stores, so there is no effect there. HLE and `libs/` are unchanged.
- **Raw coherence:** a correctness fix; expected to have no FPS effect (+0.06–0.4 ns per raw store).
- **Indirect calls:** not changed. A single gate there could save about 4 ns per call, but there is no frequency evidence, and the path has many behaviours (OPD-swap fixup, depth guard, trampolines) that would all need re-proving. Left as a candidate.

## 10. Runtime A/B plan (needs build and launch authorization)

1. **Build:** one exe from `agent/t140-ppu-memory-performance`, using the T134 integration recipe (`port/`, the same lifted code). The fast path and the stats need only `ppu_loader.cpp` and `spu_coherency.c` rebuilt plus a relink.
   - The raw-coherence arm needs a re-lift (or at least the regenerated `ppu_recomp.h`) and a recompile of the 80 lifted TUs, which is a second exe.
2. **Frequency first** (one run; not for timing): `PS3_VM_STATS=1000`. Read `[vm-stats]` over race entry + 5…+75 s for `st8/16/32/64`, `st_coh`, `sc_ok`, `sc_lost`, `sc_value`, `sc_coh`.
   - If `st32 + st64` is below about 1 M/s, stop: the fast path cannot show at the frame level.
3. **Timing arms**, in the order A B B A, with T106's bounded race-entry workflow (entry + 90 s), `ab_fps.cfg`, and accounting `SPURS_BUSY_MS=1000 PS3_SC_WAIT_MS=1000 RSX_FRAME_PERF=12,1,100000`:
   - **A:** `PS3_VM_STORE_FAST=0`;
   - **B:** default.
4. **Metrics:**
   - FPS and frame p50/p95/p99 (`t122/ab/ana_t122.py`);
   - tid 1 CPU per frame (`performance.json`);
   - PRE/emit/spin (`t134/tools/phases_all.py`);
   - optionally `PS3_CRITICAL_PATH_TRACE` with `tools/cpath_report.py`, for tid-1 running vs waiting time.
   - Expected: tid 1 CPU per frame falls; FPS unchanged while the RSX gate remains (HYPOTHESIS).
5. **Correctness arm C** (second exe): `PPU_RAW_STORE_COH=1`. Watch `raw_coh` in `[vm-stats]`, the FPS, and whether any SPURS or Havok stalls or `[cas-fail]` lines appear.
   - Any `raw_coh` above 0 confirms that R1 occurs in the game.

## 11. Integration dependencies

- **Base:** T134 (`b1ded1e`). The commits apply to any line that has T134's `ppu_loader.cpp`.
- **Overlap with other branches:** since their merge bases, T137, T133, T132B, T131 and T122 have no commits to `ppu_loader.cpp`, `spu_coherency.c/h`, `ppu_lifter.py` or `test_ppu_lift.py`. T136's three commits on those files are already in T134 as cherry-picks.
- **`0ced9c5` and the lifted code:** it changes the lifter, so the generated `ppu_recomp.h` (and the `stvlx`/`dcbz` emission) changes at the next lift.
  - Until then, the existing lifted objects keep raw stores uncoherent, and `PPU_RAW_STORE_COH` has no effect on them.
  - The runtime keeps the symbols the new header needs (`g_ppu_raw_coh`, `g_spu_coh_bitmap`, `vm_raw_coh_begin/end`).
- **T131:** R1 is its item B.3. This implements the fix as an opt-in, with the stress tests it asked for: all widths, overlapping lines, the peer LR event. T131's generation-wake check has no dedicated test here; the existing kick-wake and WWS stress suites pass unchanged.
- **T121/T134:** the usleep mode-2 and kick-wake opt-ins remain the measured critical-path levers. T140 does not change any wait.
- **Not changed:** physics, simulation dt, timer progression, scheduling, guest synchronization, memory protection (the null-page drop and the raw-SPU side effects are preserved).

## 12. Commits (`agent/t140-ppu-memory-performance`, on `b1ded1e`)

| Commit | Subject |
|---|---|
| `d27441d` | PPU stores: single-gate fast path for lifted vm_write*; PS3_VM_STATS |
| `32c1bd1` | PPU_RESV_STORE: plain lifted stores break the other threads' reservations |
| `0ced9c5` | PPU raw stores: SPU lock-line coherence, opt-in (PPU_RAW_STORE_COH=1) |
| `e701fb7` | tests: guest store fast path and raw-store coherence (test_vm_store_fast) |

- `python ../tools/audit_public.py --staged` was run before each commit: the same 25 inherited items as base `2562ba8`, none in a T140 file.
- `docs/STATUS.md` has a T140 entry; it is not committed, as with T139's and T141's.

## 13. Files

- **Report and tools:** `generated/analysis/t140/`:
  - `tools/cc.py`: TU and bench builds with the project flags;
  - `tools/lifted_tu_size.py`;
  - the `tools/patch_*.py` edit scripts;
  - `tools/stage_split.py`: the commit split.
- **Benchmark sources:** `bench/src/`; objects are in `bench/obj/` (private, not committed).
- **Logs:** `logs/bench_mem_ab.txt`, `logs/test_vm_store_fast.txt`, `logs/regression_suites.txt`, `logs/lifted_tu_size_010.txt`.
