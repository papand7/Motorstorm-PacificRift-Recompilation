# Backend recording thread (RSX_BE_THREAD) and float VMX fast paths (PS3_VMX_FAST)

2026-11-04. Vulkan game build (`ps3recomp-vkgame`, `port-vkgame`), race A/Bs through
`ab2/run_vk.py` (K arm: race entry + 75 s; `[eng-ab]` flips the switch every 24 presents
and times each side in the same run). Nothing committed.

## 1. RSX_BE_THREAD: the draw engine's backend calls on a recording thread

`libs/video/rsx_be_thread.{h,c}` wraps `rsx_draw_backend`. Calls that return nothing
are copied into a ring, with the bytes they point at, and made on a recording thread in
order; calls that return something wait for the ring and run on the caller's thread.
Guest labels are queued when `RSX_VK_LAZY_SYNC=1`. Off by default; `RSX_BE_THREAD=1|ab`.
Wired in `rsx_vulkan_backend.c` (wrap at init, sync before the split present and in
the ZPASS hook, stop at shutdown).

Test: `libs/video/tests/test_rsx_be_thread.c` (`tools/build_be_thread_test.cmd`),
26 checks. Same call log with and without the thread, with buffers overwritten after
each call. It also checks:
- ring wrap and ring-full waits;
- large calls made directly;
- labels queued or waited;
- a declined `draw_columns` decoded on the recording thread;
- "ab" switches;
- vertex-constant rows;
- no overlapping backend calls.

Mutation checks: dropping the vertex copy fails 4 checks, and queuing labels the backend
wants waited fails 1. The third mutation (removing the drain on an ab switch) is
equivalent: every direct call drains first.

| run | exe | change | ms a present on / off | RSX thread Mcycles on / off |
|---|---|---|---|---|
| Kk23 | 5ee39ea9 | 64 MB ring | 36.34 / 35.05 | 85.5 / 89.9 |
| Kk24 | 70a9077a | 4 MB ring, vertex-constant rows, bytes by call | 40.00 / 38.49 | 109.3 / 94.6 |
| Kk25 | 4c22cb5e | shared words on own cache lines, head/tail every 16/32 calls | 46.85 / 42.25 | 104.4 / 89.5 |
| Kk27 | 5a70e3f8 | constant rows compared inline | 37.20 / 36.41 | 88.6 / 94.5 |

VERIFIED: the thread is stable (no crash or hang in 5 race runs), but it is not faster
in any of the 4 in-run A/Bs (frames +0.8 to +4.6 ms with it on).

PARTIAL, from Kk26's profile (`ab2/sample_k26.json`, thread on throughout):
- The recording thread's own Vulkan work is small. 27% of its samples wait in the
  backend for a GPU fence, and most of the rest spin waiting for work. So most of the
  "record" time measured before was GPU waiting, not CPU work.
- The walker still waits on GPU readbacks each frame (`s_rtrb` 4.7%).
- In Kk24-26 the wrapper's own cost was about 15% of the walker. The vertex-constant
  row diff called memcmp once per 16-byte row on about 3,700 binds a frame; fixed in Kk27.

HYPOTHESIS: with 6 cores / 12 threads already busy (an SPU thread at 84%, the game
thread at 77%), a further busy thread costs the game's own threads more than the
walker gains.

Status: kept, off by default. Candidate for removal if no other use appears.

## 2. PS3_VMX_FAST: x86 fast paths for vmaddfp, vnmsubfp, vaddfp, vsubfp

`runtime/ppu/ppu_vmx.h`: the per-lane helpers stay (`*_lane`). Each fast path does one
SSSE3 byte swap per operand, then FMA3 / `addps` / `subps`, with the same NJ flush and
NaN rules. It is taken when `g_vmx_fast` is set (`ppu_loader.cpp`, default 0;
`PS3_VMX_FAST=1|ab` in `port-vkgame/main.cpp`) and the CPU has SSSE3, FMA3 and AVX
state enabled.

Why it is exact:
- `fmaf` and the FMA instruction are both the IEEE fused multiply-add with one rounding.
- `vnmsubfp` is `-(x*z - y)`, not `-(x*z) + y`; the latter differs in the sign of an
  exact zero.
- NaN results are normalised in both versions, so host payloads never show.
- Nothing in the runtime changes MXCSR, so there is no DAZ/FTZ and rounding is to nearest.

Test: `runtime/ppu/tests/test_vmx_float_fast.c` (`tools/build_vmx_fast_test.cmd`).
VERIFIED: 0 mismatches against the per-lane code (which calls ucrt `fmaf`, as lifted
code does) in 160,000,000 comparisons (4 ops x 2 VSCR, 640,000,000 lanes). Inputs were
random bits, ordinary floats, special values, cancelling products, denormal products and
exact zeros, plus aliasing. Mutation checks are all caught: fnmadd for vnmsubfp, no
result flush, NaN precedence swapped.
The existing `tools/test_ppu_vmx_lanes.py` and `test_vmx_alias_contract.c` pass.

Profile before (Kk26, game thread): vmaddfp 5.5%, vaddfp 1.3%, vnmsubfp 0.4%,
vsubfp 0.3%. The old helper was compiled for baseline x86-64: about 25 shuffles per
operand for the byte swap, eight XMM registers saved, and four out-of-line ucrt `fmaf`
calls.

Race A/Bs, exe 84ee1a83, `PS3_VMX_FAST=ab`, recording thread off:

| run | race windows | ms a present, fast paths on / off | note |
|---|---|---|---|
| Kk28 | 5 (600 presents a side) | 50.20 / 51.28 (-1.08) | PC under load all run |
| Kk29 | 3 | 95.53 / 72.86 | heavy outside load (73-95 ms frames); not usable |
| Kk30 | 8 (960 presents a side) | 36.81 / 38.00 (-1.19) | normal load |

VERIFIED (Kk28, Kk30): about 1.1-1.2 ms a present faster (3%) with the fast paths on;
the same bits by test.

Default: on since 2026-11-04 (user approved). `port-vkgame/main.cpp` sets
`g_vmx_fast` unless `PS3_VMX_FAST=0`. The exe is `f71034a0` (built, not yet launched).
RSX_BE_THREAD stays as an opt-in (user decision).

## Where the frame goes now (Kk26 profile, Kk30 stats)

- Frame p50 37.7 ms. GPU work is about 3.5 ms a frame (`gpu_ms`), present waits
  about 1.8 ms, and the RSX walker idles 22%. So the CPU side sets the frame.
- Game thread (busy about 75%):
  - lifted PPU code about 46%;
  - guest store and load helpers 11%;
  - VMX helpers 8% (now on fast paths);
  - trace hooks 5%: the runner's `nav_sites.cfg` route trace turns these on, so a
    player run doesn't pay them;
  - waiting 25% (usleep polls 10%, event wait 5%, lwmutex 3%).
- Busiest SPU thread (image cbf1b1a1):
  - lifted SPU code 63%;
  - `spu_drain_call` trampoline loop 13.5%;
  - waiting 19%.
- The lifted PPU code keeps every guest register, CR and XER in `ctx` memory. Each
  compare rewrites `ctx->cr` and reads `ctx->xer`. Stores call out-of-line `vm_write*`,
  so the compiler must reload registers after every store (`func_0050C818`,
  `generated/ppu-t173-staging/ppu_recomp_010.cpp`).
- HYPOTHESIS: the largest remaining lever is the lifter's code generation:
  - guest registers held in C locals inside a function;
  - CR fields computed only where they are read;
  - inline store fast path.
  All game-thread code would get faster at once.

## 3. Next lever? PPU code generation measured, and where the frame goes (2026-11-05)

Exe `f71034a0` (PS3_VMX_FAST on by default; `[vmx-fast] PS3_VMX_FAST=(default 1)` seen in Kk31-Kk35, every
run reached the race and stopped normally).

PPU code-generation levers, none faster on real game code:

| Lever | Test | Result |
|---|---|---|
| Inline guest stores (`PS3_VM_STORE_INLINE=1`, built in) | Kk31, in-run A/B, 7 race windows | 42.00 / 41.99 ms: no gain (VERIFIED; Kk15 also none) |
| `-march=x86-64-v3 -ffp-contract=off` on lifted code (MOVBE, BMI2, LZCNT) | `tools/bench_march.cmd` + `run_bench_march.py`, T189 real functions + real runtime, 11 rounds | A/V 0.96-0.98x (min), same final state: no gain (VERIFIED offline, noisy PC) |
| Guest-register promotion (`ppu_regpromo.py`) | T189 | D/B 0.96-1.03x on real functions: no gain |

So the earlier HYPOTHESIS (codegen as the largest lever) is refuted for the PPU side.

Critical path, Kk32 (`PS3_CRITICAL_PATH_TRACE=60:20`, `tools/cpath_threads.py`):
- frames 42.8 ms mean (with trace overhead);
- main thread running 30.7 ms, blocked 12.1 ms; running is the largest share in all 466 frames;
- host CPU per frame: main 28.5 ms, JobBatchHandler 25.8 (mostly usleep spin), rsx-drain 23.7, five SPURS workers 15-17 each.

Inclusive guest profile of the main thread, Kk34/Kk35 (`tools/thread_sampler_incl.py`, x64 unwinding from
.pdata; `tools/incl_report.py`; 14 broken walks in 7,559 samples):

| Running time (62% of samples) | share |
|---|---|
| `World::Update` 0x216008 (simulation) | 53-56% |
| of which `ms2Physics::Update` / Havok step | 23-25% / 18-19% |
| render preparation (RenderCommandExecutor 0x4E6FF8, post effects 0x34CDE8, views, visibility kick, EndFrame/Present) | ~30% |
| `vm_write*` self | 13-14% |
| trace hooks (`ppu_trace_enter/ret`, `thread_for`: the runner's nav_sites.cfg only) | ~9% |
| Wws busy-wait 0x50C818 self | 5-6% |

| Waiting (38% of samples), by guest caller | share of waits |
|---|---|
| Havok step 0x30B710 (Havok SPU jobs) | 27% |
| `DisplayATG::Present` → `GcKernel::Present` (RSX/flip) | 21% |
| `JobBatchInternal::Wait` 0x4AACA0 (JobBatchHandler) | 16% |
| not under the main loop (walk from a DLL wait did not reach it) | 33% |

Other threads:
- The busiest SPU-side host thread (67-82% CPU) is image `cbf1b1a1` = 482286362, the FIOS SPU decompressor
  (STATUS.md). It decodes a bit stream (0x8440 -> 0x8448 -> 0x84C0 loop) during the whole race.
- Its blocks hop through the drain loop: `spu_drain_call` is 17.6% of its running samples.
- It is not lifted with `--chain-chunks`; the four Havok images are (T158, +6.1% light-scene FPS).
- No main-thread wait was attributed to it.

Conclusions:
- VERIFIED: the main thread's game code (simulation 55%, render preparation 30%) sets the frame. It is spread
  over hundreds of functions and does not respond to PPU code-generation changes.
- HYPOTHESIS: the remaining levers are each a few percent:
  - Havok SPU speed (SPU register caching in `--chain-chunks` groups, T158 §4): part of the ~4 ms Havok wait;
  - the RSX walker (Present wait, ~3 ms);
  - `--chain-chunks` for the decompressor image: frees CPU, not on the frame path.
- Player runs have no nav trace, so they are about 9% of main-thread running time faster than these test runs.

## 4. Scheduling the main thread (2026-11-05)

| Run | Exe | Switch (by turns) | ms a present on / off | Verdict |
|---|---|---|---|---|
| Kk36 | a727f497 | `PS3_MAIN_CORE=ab`: main thread pinned to logical 10, every other thread off core 0xC00 | 39.16 / 37.71 | REFUTED (+1.45 ms): taking a core from the other threads costs more |
| Kk37 | c693e2cb | `PS3_MAIN_PRIO=ab`: main thread at THREAD_PRIORITY_HIGHEST | 32.50 / 32.88 | inconclusive (-0.4 ms, one run, about noise) |

- `PS3_MAIN_CORE` was removed again; `PS3_MAIN_PRIO=1|ab` stays in `port-vkgame/main.cpp`, off by default.
- Kk37 ran at 30.4-30.8 fps in the race with less outside load on the PC (Kk4's exact-usleep side: 30.0 fps).
- SPU register caching (option 1) was not started:
  - the same design failed its first gate on Bink (whole-group caching -18%: 70-80 live 128-bit values
    spill; `docs/BINK_PERFORMANCE_BACKLOG.md`);
  - T158 calls the Havok register traffic structural.

## 5. Main-thread priority repeat, and the FIOS background cache build (2026-11-05)

`PS3_MAIN_PRIO=ab`:
- Kk38 (heavy outside load, 59-61 ms frames): 61.46 vs 58.83 ms, slower with it on. Kk37 was -0.4 ms.
- No win; the code was removed from `port-vkgame/main.cpp`.
- The pinned exe stays `c693e2cb`: switch off by default; source = the `f71034a0` state.

What the SPU decompressor does (VERIFIED):
- Kk39/Kk40 (`tools/io_rate.py`): during the race the game reads 30-50 MB/s (about 2,000 reads/s) and
  writes 17-26 MB/s.
- Kk41 (`FS_READ_ALL=1`, `PS3_FSLOG_READS=5`, `tools/fs_reads_race.py`), race window:
  - ms2.psarc (fd 5): 18.7 MB/s, 1.4 GB, 94% of 64 KB blocks read once;
  - FIOS `cache.dat` (fd 4): 18.4 MB/s.
- From boot, 99.7% of psarc reads are in rising offset order (0 MB at boot ... 1,782 MB at 110 s). FIOS
  copies the whole 4.8 GB archive into its HDD cache in the background.
- The game itself calls `cellSysCacheMount` then `cellSysCacheClear()` at boot (stdout.log). So the cache is
  rebuilt every session, as on a PS3, where the disc limits the copy to a few MB/s. Here it runs at about
  20 MB/s.
- Kk42 (long race, `RUN_VK_RACE_S=300`, runner `cpu.jsonl`):
  - the busiest SPU-side thread (0.7-0.8 CPU-s/s, the decompressor image cbf1b1a1) stops at about 130 s
    after launch;
  - the archive reads stop at the same time, about 100-105 s after race entry.
  So the decompressor load is this cache build, the first ~2 minutes of each session.
- Every race benchmark here (race entry + 0..75 s) falls inside the build.
- Kk42 could not measure its frame cost:
  - the runner's 209 s hard session cap ended it;
  - fps fell from ~25 to ~11 at about 155 s with unchanged draw counts and no busier game thread, most
    likely outside load.

`--chain-chunks` for the decompressor image (`tools/decomp_lift_pair.py` + T158 `hvk_build.py`, `hvkdiff`):
- 0 mismatches and equal step counts in 3 seeds;
- the covered leaf functions are 5-16% faster;
- but random states reach only 7 of 33 call targets (~20,000 SPU instructions), never the hot decode loop
  (0x8240 -> 0x8440-0x8C58).
- Not enabled: verifying it needs a replay of real captured SPU states.

## 6. Toward 60 fps: the real per-frame cost (2026-11-05)

Kk43 (exe c693e2cb, `MSPR_PATCH=vfps` = variable frame rate, long race `RUN_VK_RACE_S=300`; the runner's
hard cap now follows that override):

| race s | 0-60 | 60-105 | 105-180 | 180-255 | 255-285 |
|---|---|---|---|---|---|
| fps | 26-33 | 30-35 | 26-30 | 15-22 (outside load on the PC) | 26-31 |
| FIOS background read MB/s | 34-48 | 8 -> 0 | 0 | 0 | 0 |

- VERIFIED: uncapped, the game runs 25-35 fps (29-39 ms a frame). The 30 fps lock hides almost nothing.
- 60 fps needs about half the per-frame cost.
- The background cache build has no visible effect on fps.

Per-frame budgets at 60 fps (16.7 ms) against what was measured:
- main thread running ~25 ms (Kk32/Kk35);
- RSX walker 85-96 Mcycles ≈ 16-18 ms CPU (eng-ab lines);
- Havok SPU wait ~4 ms.
Every one of these must shrink.

Checked and excluded:
- texture write-watch resets as a hidden store cost: the Vulkan path never calls GetWriteWatch (only the
  D3D12 backend does), so `MEM_WRITE_WATCH` costs nothing here.

Not testable without the user:
- large pages (2 MB) for guest memory, against TLB misses. The profile's 13% in guest stores did not respond
  to inlining, which suggests memory-access cost.
- It needs the "Lock pages in memory" right (SeLockMemoryPrivilege) for the Windows user and a new login.
- Hardware counter tracing (`wpr`, PMC sources available: TotalCycles, InstructionRetired, DcacheMisses; no
  TLB counter) needs an elevated session.
