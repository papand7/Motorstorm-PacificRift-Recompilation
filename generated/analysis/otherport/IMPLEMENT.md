# otherport: the four items built (2026-11-23)

Follows `COMPARE.md`. All four are **our own implementations**: no code was copied from the MIT port, so
`THIRD_PARTY_LICENSES.md` is unchanged. Each item has an opt-in switch and is off by default. None is on by default
yet, because no race has been measured.

Labels: VERIFIED (shown offline here), HYPOTHESIS, BLOCKED (needs the queued races).

## Build

- One private exe carries all four switches: `build/otherport-link/MotorStormPacificRiftRecomp.exe`,
  sha256 `d3360b8ccc2edbd8392cc93b4b4e86a37c822b3b48255189bce94d9d1c3600d3`.
  - The queue copy is `generated/analysis/vksync/ab2/exe_ot/` (slot `ot`, `exe_ot.sha256`).
- Builder: `generated/analysis/otherport/tools/ot_link.py`, the shadow_link pattern.
  - It compiles 69 sources in parallel, at below-normal priority, with their own ninja command lines, then
    lld-links them against the untouched `build/motorstorm-vkgame-100-ppucc2` objects.
  - Recompiled: every TU whose deps include `spu_helpers.h` (63: all lifted SPU images, overlays, WWS reloc
    modules, `spu_channels.c`, `spu_interp.c`), plus `sys_timer.c`, `cellSpurs.c`, `port-vkgame/main.cpp`, and
    three lifted PPU TUs (below).
  - Log: `logs/build_otherport_link.txt`.
  - Command:
    `py -3 generated/analysis/otherport/tools/ot_link.py build/otherport-link --jobs 6 --deps-of spu_helpers.h --src ps3recomp-vkgame/runtime/syscalls/sys_timer.c --src ps3recomp-vkgame/libs/spurs/cellSpurs.c --src port-vkgame/main.cpp --ppu-override D:/motorstorm/ppucc2/ppu-v100-ppucc2/ppu_recomp_00{1,4,9}.cpp=D:/motorstorm/otherport-ppu/ppu_recomp_00{1,4,9}.cpp`
- Not touched: `launcher/dev/MotorStorm/play/...exe`, `build/motorstorm-vkgame-100-ppucc2`,
  `D:/motorstorm/ppucc2/ppu-v100-ppucc2` (the patched PPU copies are in `D:/motorstorm/otherport-ppu/`),
  `libs/video/*`, `texpack.py`, and the ps3recomp pin.
- Backups of the edited shared files from before my edits: `generated/analysis/otherport/backup/`.
- **Note for the other agents:** `spu_helpers.h` changed. Their next incremental build recompiles every lifted
  SPU TU. That takes minutes, not hours.

## 1. SPU float on the hardware: `PS3_SPU_HWFLOAT=1`

- **What I built:**
  - New header `runtime/spu/spu_hwfloat.h` with a TLS flag and the MXCSR value `0xFFC0` (round toward zero, FTZ,
    DAZ).
  - In `spu_helpers.h` (the AVX2 path), `fa`/`fs`/`fm`/`fma`/`fms`/`fnms` become a single inline-asm
    `vaddps`/`vsubps`/`vmulps`/`vfmadd213ps`, followed by a range check.
    - A result `>= FLT_MAX` (extended range, Inf/NaN, overflow) is redone exactly in integers.
    - An exponent-0 result becomes +0.
    - Inline asm is used so the compiler cannot constant-fold with round-to-nearest or move the op out of the
      mode. FMA3 is checked at runtime. No build flag changes.
  - Double ops (`dfa`/`dfs`/`dfm`/`dfma`/`frds`/`dfc*`) switch to the host MXCSR around themselves. The
    `ldmxcsr` asm takes the operands and result as memory operands, so no FP instruction can escape the window.
  - All fallbacks are integer-only while the flag is set.
  - `spu_run_with_halt` sets the mode around every run of lifted code. It is nest-safe and rearms after the
    landing pad's setjmp.
  - Host calls leave the mode and come back: `spu_rdch`/`spu_wrch`/`spu_rchcnt` (which cover all MFC, mailbox,
    event, sleep and wake work), `spu_stop`, `spu_halt`, and the HLE taskset syscall. The dispatchers, the drain
    and the interpreter stay in the mode (they are integer code, and their helpers are exact in either mode).
- **Verification (VERIFIED):**
  - `tools/test_spu_hwfloat.py 40`: 30 ops, about 277 M vectors (1.1 G lanes) per op. Random, edge, underflow,
    overflow, cancellation and an exhaustive slice of 2×2^23 significands, built twice (AVX2 helpers, SSE4.1
    helpers). Bit-identical mode on vs off, and equal to the integer reference. Log:
    `logs/test_spu_hwfloat_40M.txt`.
  - `hvkdiff/build_hwf.py prodhwf 11 64`: the production lift of the float-heavy Havok "collide" image (1872
    float-op sites), every function from random states, through the real drain runtime, against the
    interpreter. 4452 cases, 7.8 M SPU instructions, **0 mismatches with `PS3_SPU_HWFLOAT=0` and with `=1`**.
    Log: `hvkdiff/run_prodhwf_s11_64.txt`.
  - `tests/test_spu_hwfloat_bracket.py`, with the real runtime:
    - lifted code runs at `FFC0` with the flag set;
    - the channel's host side runs at the caller's own MXCSR (`9F80`);
    - a nested run inside a host call, a stop, and a halt longjmp all restore exactly.
  - `tests/test_spu_task_stats.py`: pin updated for the wrapper.
  - Other SPU and SPURS tests show the same results as a baseline copy of the tree without my changes. The
    pre-existing failures (`test_spu_exec_sse`, `test_spu_drain_resume_reloc`, the `fnms` link) fail there too.
  - Not done: the Kksr2 recorded-task replay (`spu_speed/differential.py`). Its taskrec hooks exist only in
    `ps3recomp-spuopt`.
- **Expected vs measured:**
  - Microbenchmark, ns per 4-lane op, off → on: fa 6.0 → 1.6, fm 9.5 → 5.0, fma 29 → 6.5 (edge-heavy inputs).
  - Havok function-level: 0.215 → 0.177 ms (−18 %).
  - Race: HYPOTHESIS, 1-2 ms/frame less SPU wait. BLOCKED on the queued races.
- **Arms:** `Khfa1-6` (off) and `Khfb1-6` (on), ABBA order, `_TX` + `PS3_SPU_TASK_STATS=1000`.

## 2. JobBatchHandler poll: `PS3_JOBPOLL_US=50` (general form `PS3_USLEEP_CAP=<lr>:<us>,...`)

- **What I built:** `sys_timer.c`. A `usleep` from a listed guest lr sleeps at most the cap, on the exact path
  (spin, never early). `PS3_JOBPOLL_US=N` is the same as `PS3_USLEEP_CAP=4AF6D0:N`.
  - This is a documented timing deviation. The loop is a pure poll, so only how soon the guest sees a batch
    changes. It costs one busy core.
- **Verification (VERIFIED):** `tools/test_timer_usleep.py` has a new `cap` mode.
  - The parser cases pass.
  - `usleep(200)` at lr `0x004AF6D0` has a median of **50.1 µs** and is never under the cap.
  - At another lr it stays 515 µs on the default timer and is never early.
  - All earlier modes still pass.
- **Expected:** HYPOTHESIS, 0.5-2 ms/frame (theirs: +15 % with wide job lists). It may be neutral on 6 cores.
  Measured: BLOCKED.
- **Arms:** `Kjpa1-6` (off) and `Kjpb1-6` (on), ABBA order, `_TX`.

## 3. Sixth host lane: `PS3_SPU_HOST_LANES=6` (+ `PS3_SPU_HOST_LANES_WIDE=1`)

- **What I built:** `cellSpurs.c`.
  - A ≥5-SPU instance gets `nlanes` host policy-module lanes. Everything the guest sees stays at 5 (the
    `SPURS_NSPUS` byte, `GetInfo`, `GetNumSpuThread`).
  - Lane 5 is spu number 5. It stays inside the WWS per-SPU quadword, which is why 6 is the ceiling, and it uses
    lane 0's priority.
  - With `WIDE`, a workload whose guest maxContention is ≥ the SPU count may use every lane. The guest-visible
    `CURCONT` can then read 6. This is a hardware deviation.
- **Verification (VERIFIED):** `tools/test_spurs_wws_concurrency.py` has a new `lanes6` mode:
  - 900 jobs exactly once each at peak 6 (lanes `0x3F`);
  - maxContention 1 and 5 leave identical guest state;
  - the 2-SPU instance still uses 2 lanes;
  - the guest still sees `nSpus` 5;
  - the shutdown and priority cases pass.
  - `test_spurs_wws_stress`, `test_spurs_admit`, `test_spurs_wkl_maxcont` and `test_spurs_event_sched` all pass.
- **Expected:** HYPOTHESIS, 0 to +1.5 ms. Negative is possible on 6 cores. Drop it if neutral.
- **Arms:** `Khla1-6` (off) and `Khlb1-6` (on), ABBA order, `_TX`.

## 4. 60 fps without artefacts

- **(a) Fixed 60** needs no new code: `MSPR_PATCH=drs,60fps,audiothread` (no vfps), `PS3_SIM_PACE_HZ=60`,
  `MSPR_CAM_MODE=1`. Every world step is the game's own 1/60.
- **(b) `MSPR_CAM_SPRING=1`** (`port-vkgame/main.cpp`, with `tools/spring_patch_ppucc.py` on copies of the lifted
  TUs).
  - The chase spring step `func_0037FB68` (and its alias `0x0037FB64`) runs once per 1/30 s of the game's frame
    clock per camera, and is skipped at entry otherwise.
  - The frame clock is the per-frame step `f1` at `func_008CF1C0`, taken before slow-motion scaling.
  - Every call of one camera in one frame gets the same answer. Long frames do not burst.
  - At 30 fps every call runs, so the behaviour is unchanged.
  - The callers were checked: they keep nothing in volatile registers across the call.
- **Verification:**
  - Builds, and the hooks are present (VERIFIED).
  - Behaviour and the look in motion: BLOCKED (needs a race and the user's eye).
- **(c) Adaptive 60/30:** not built. The design is in COMPARE §3.3 (switch `timer+0x18` 1↔2 at a frame boundary,
  never also scale dt). Its double-speed risk needs a race assert first.
- **PC Settings "60 FPS (fixed)":** not added. It is to be added only after the eye check.
- **Arms:** `Kfxs0` (Fixed 60, springs every update) and `Kfxs1` (with `MSPR_CAM_SPRING=1`). Both have
  `RSX_VEHLOG`, `MSPR_DT_LOG` and `MSPR_CAM_SPRING_LOG`, for the vehfps tools.

## Queue (`run_vk.py`)

- 38 arms were inserted before `Klt5t`, after `Ktg3o`.
- `ORDER[:len(launches_used)]` still equals the launched list (685 launched when inserted).
- Tool: `tools/add_arms_ot.py`. The pre-edit copy is `backup/run_vk.py.before_ot`.
- Launch each in order: `py -3 generated/analysis/vksync/ab2/run_vk.py launch K <tag>`, where tag is one of
  `hfa1 hfb1 hfb2 hfa2 ... hfa6`, `jpa1 ... jpa6`, `hla1 ... hla6`, `fxs0 fxs1`.
- Timing arms need EA Desktop and Epic closed. Decide with
  `py -3 generated/analysis/roadto60_next/tools/ab_compare.py --a hfa1,...,hfa6 --b hfb1,...,hfb6 --a-sha d3360b8c --b-sha d3360b8c`.
  The jp and hl pairs work the same way. Six matched pairs are needed per decision.
