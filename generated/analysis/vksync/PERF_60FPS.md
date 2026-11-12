# Toward 60 fps (2026-11-05)

Earlier work (`BE_THREAD_AND_VMX_FAST.md`, sections 3-6): uncapped (`MSPR_PATCH=vfps`, Kk43), the race runs
25-35 fps. The main thread runs about 25 ms of game code a frame, the RSX walker 16-18 ms, and the main
thread waits about 4 ms on Havok SPU work.

## Measuring: PS3_MAIN_CYCLES=1

- `port-vkgame/main.cpp` logs, every 5 s: `[main-cyc] <flips> flips, <x> Mcycles a flip on the guest main
  thread` (QueryThreadCycleTime per guest flip).
- It does not count waiting or descheduled time, so it compares builds better than frame times on this
  shared PC. It still moves with cache and SMT contention: the same exe gave 127.3 (Kk51, outside load)
  and 117.9 (Kk53, quiet).

## Hot-code link order: no gain (VERIFIED)

- **Profile:** Kk50, exe c131cfd4, `tools/thread_sampler_incl.py` on the 8 busiest threads,
  `incl_all`/`self_all`.
  - 2,587 functions were seen running (2,280 lifted); 21.4 MB of code spread over the whole 408 MB
    `.text` in 106 2 MB regions.
- **Order file and relink:** `tools/make_order.py` -> `ab2/order_k50.txt`, then
  `tools/relink_order.cmd` (lld-link /ORDER on the same objects).
  - Result: exe b90ac86e, the hot code in 13 2 MB regions.
- **A/B:** the base exe 8c01ef18 against the ordered one, alternating (`tools/add_arm_k51.py`,
  `tools/set_pin.py`). Main thread Mcycles a flip over the race (median of 14 windows):

| Run | Exe | Mcycles/flip | frame p50 (ms) |
|---|---|---|---|
| Kk51 | base | 127.3 | 40-46 (outside load) |
| Kk52 | ordered | 119.9 | 33-37 |
| Kk53 | base | 117.9 | 31-33 |
| Kk54 | ordered | 119.6 | 33-35 |

- In the quiet pair (Kk53/Kk54) the ordered build is not faster (+1.4 %). Function-level code locality
  is not what limits the main thread.

## Profile-guided optimisation (PARTIAL: about -12 % main-thread cycles, not yet measured cleanly)

**Build and training:**
- Instrumented build: `tools/build_pgo.cmd gen` -> `build/motorstorm-vkgame-pgogen` (848 MB exe), every
  source with `-fprofile-generate` and `PORT_PGO_GEN`.
- Training race Kk55 (RSX_RES_SCALE=1.5, drs; `RUN_VK_RACE_S=100`):
  - `PS3_PGO_WINDOW=60000:140000`, race entry at 51 s;
  - `build/pgo/ms2-22320.profraw` 137 MB -> `llvm-profdata merge` -> `build/pgo/ms2.profdata`
    (74,073 functions).
- Optimised build: `tools/build_pgo.cmd use build/pgo/ms2.profdata` -> `build/motorstorm-vkgame-pgouse`
  (444 MB exe, exe 653b134c). It ran three races cleanly (only the usual loose-file lines).

**A/B Kk56-Kk59** (base 8c01ef18 vs PGO, alternating). Median of the race windows with a normal flip
rate (>= 120 flips in 5 s):

| Run | Exe | windows | Mcycles/flip | frame p50 (ms) |
|---|---|---|---|---|
| Kk56 | base | - | - | stopped before the race: `GcKernel::Present() Timeout` |
| Kk57 | PGO | - | - | race stalled (frames 41-58 ms, windows with 18-24 flips) |
| Kk58 | base | 5 | 122.1 | 30-68 |
| Kk59 | PGO | 7 | 106.8 | 32-60 |

- **PARTIAL:** PGO about -12 % main-thread cycles a frame (Kk58/Kk59; quiet base runs earlier: 117.9-127.3).
- **Why only partial:**
  - all four ran under heavy outside load (SSX Tricky and two Nightfire processes, 68-84 % CPU with no
    MotorStorm running);
  - the stalls also inflate `[main-cyc]`, because the game spins while it waits.
- **Next:** repeat the A/B on a quiet PC.

**A/B Kk71-Kk74** (2026-11-05; base 9531e520 vs PGO 8df22c49, same tree and the Kk55 profile; Kk70's
configuration: `drs,vfps` uncapped, RSX_RES_SCALE=1.5, texture pack). The PGO arms get their own SPIR-V cache
(`ab2/spirv_cache_pgo`, rewarmed by `tools/build_spirv_rewarm_pgo.cmd`; `tools/add_arm_k72_cache.py`): the PGO
build changes the cache stamp, which is what stopped Kk56 and stalled Kk57. Median of the race windows
(`/tmp/abcmp.py`-style: frame-hist windows with > 500 draws, main-cyc windows with >= 60 flips):

| Run | Exe | Mcycles/flip | frame p50 (ms) | present wait (ms/frame) |
|---|---|---|---|---|
| Kk70 (earlier) | 2759935a base, plus probe_fps.cfg trace | 117.4 | 35.5 | 4.1 |
| Kk71 | base | 173.3 | 61.8 | 30.8: GPU shared (BF1943 running), discarded |
| Kk72 | PGO | 105.7 | 31.9 (27.2-41.4) | 5.3 |
| Kk73 | base | 117.4 | 36.7 | 12.3 |
| Kk74 | PGO | 138.4 | 56.6 | 19.1: SSX Tricky at 100 % of a core, discarded |
| Kk75 | PGO | 113.3 | 33.7 | 6.3 (BF1943, SSX, Nightfire open) |
| Kk76 | base | 133.8 | 40.8 | 11.8 (same outside load as Kk75) |

- **PARTIAL:** PGO -10 % main-thread cycles and -13 % frame time (Kk72 vs Kk70/Kk73); several race windows
  under 30 ms. Second pair Kk75/Kk76 (both under the same outside load): PGO -15 % cycles, -17 % frame
  time. Both pairs favour PGO; neither run is fully quiet.
- The present-wait column flags contaminated runs: clean races wait 4-5 ms a frame.

**PGO + ISA, Kk77** (2026-11-05): `tools/build_pgo.cmd isa build/pgo/ms2.profdata` ->
`build/motorstorm-vkgame-pgoisa`, exe 1a5c5a60 (`.keep-1a5c5a60`): the PGO build plus AVX2, BMI1/2, LZCNT,
MOVBE, POPCNT and `-mtune=znver5`, with `-ffp-contract=off` and no `-mfma`, so float results don't change.
Own SPIR-V cache `ab2/spirv_cache_isa` (`set REWARM_BD=build\motorstorm-vkgame-pgoisa`, then
`tools/build_spirv_rewarm_pgo.cmd <dir>`: 296 of 296 translated); arm from `tools/add_arm_k77.py`.

| Run | Exe | Mcycles/flip | frame p50 (ms) | present wait (ms/frame) |
|---|---|---|---|---|
| Kk77 | PGO + ISA | 150.1 | 48.8 | 11.6 (NightfireDriving and bf1943_stageB started during the run) |

- **HYPOTHESIS (no gain):** under outside load like Kk76's (present wait 11.8), Kk77 is +12 % cycles on base
  Kk76 and +32 % on PGO Kk75. One contaminated run, but nothing in it argues for keeping the ISA flags. No
  unlifted SPU calls interpreted. Pin restored to base 9531e520.

## SPU: two overlay entries ran in the interpreter (2026-11-05, offline)

- **Finding (VERIFIED from logs):** in every race, SPU image 283218738 calls LS 0x37110 (lr 0x03CF8) and
  0x37170 (lr 0x045E0) through its table. Both lie in DMA-loaded overlay variant 2 (sha256 7ddb23d4...,
  the bytes printed in the Kk67 log match it). Its lift had never decoded them, so with
  `SPU_INTERP_UNLIFTED=1` each call went through the dispatcher's miss path and the SPU interpreter.
  They are short "get pc" prologues (`brsl` to the next word) that continue into code already lifted.
- **Fix:** `tools/build_port.cmd` / `tools/build_spu_overlay.py` re-lift of variant 2 with
  `--extra-funcs ...,0x37110,0x37170` (68 functions, none unsupported). Old lift in
  `generated/overlays/spu38790/variant2/lift.bak-20261105`. Exe 333a6369 (kept as `.keep-333a6369`).
- **Test (VERIFIED):** `tools/build_ovl_entries_test.cmd` (private: links the lifted overlay and loads the
  captured bytes). Each new entry against `spu_interp.c` from the same random state: 0 of 4,000 trials
  differ in registers, local store or next pc, for both. Mutation (link register off by 4): 4,000 of
  4,000 fail.
- **Cost per call (bench mode):** interpreted 37.4 / 27.9 ns, lifted 2.3 / 2.7 ns, not counting the
  dispatcher's miss path before the interpreter.
- **HYPOTHESIS (gain):** Kk50's profile put 9-12 % of that SPU worker in the interpreter, but that
  profile's names came from a map that may not match its exe (it shows `cellGcmInit` on an SPU thread).
  Rerun `tools/relink_map.cmd` for the pinned exe before the next `sample_race.py`.
- **VERIFIED in races (2026-11-06, from existing logs, no new run):** every exe from 544c6e86 on carries the
  re-lift. Kk69-Kk80 (12 races) log 0 `interpreting unlifted` lines; Kk66-Kk68 (2c9357fe) log 10 each for
  0x37110/0x37170. The gain is still unmeasured (HYPOTHESIS above).

**Quiet PGO A/B queued (2026-11-06):** Kk81/Kk83 base 9531e520, Kk82/Kk84 PGO 8df22c49, Kk71's configuration;
`tools/add_arm_k81.py`, all queued runs `tools/run_queue_k81.py` (Kk81-Kk86). Not run: `run_vk.py` refuses a
Remote Desktop session (`query session` must show `>console`). Run the queue at the PC.

**Quiet A/B Kk81-Kk84** (2026-11-06, at the console, EA background service stopped; `tools/run_queue_k81.py`;
`/tmp/abcmp.py`-style medians):

| Run | Exe | Mcycles/flip | frame p50 (ms) | present wait (ms/frame) |
|---|---|---|---|---|
| Kk81 | base 9531e520 | 110.1 | 31.7 | 3.5 |
| Kk82 | PGO 8df22c49 | 112.4 | 32.8 | 4.8 (claude.exe 5 %) |
| Kk83 | base | 116.7 | 36.2 | 3.6 |
| Kk84 | PGO | 110.5 | 32.7 | 4.9 (bf1943.exe 11 %, started during the run) |

- **VERIFIED (no meaningful gain):** on a quiet PC PGO is -1.7 % main-thread cycles (111.5 vs 113.4 mean), inside
  the run-to-run spread (base 110.1-116.7). The earlier -10..-15 % came from runs under outside load. Keep the
  base build as default.
