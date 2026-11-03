# T132: original frame timing in MotorStorm: Pacific Rift (static, retail EBOOT)

Read-only static analysis. I did not build or launch anything. Inputs: `generated/decrypted/EBOOT.elf`, the stub map
`generated/analysis/garage_menu/stubs.json`, and the developer build `generated/analysis/c38/rv/resourceviewer.elf`
with its `symbols.txt`, used for names. I matched developer functions to retail with masked instruction signatures
(`tools/match.py`). Tools are in `t132/tools/`: `elf.py`, `ppcdis.py` (capstone, per-function TOC), `callers.py`,
`scan_imports.py`, `floatscan.py`, `devdis.py` and `match.py`. Raw outputs: `scan_imports.txt`, `floatscan.txt` and
`dis_*.txt`.

Labels: VERIFIED = seen in code; PARTIAL = part of it is seen; HYPOTHESIS = inferred, not seen.

## 1. Imports and call sites

| Import / syscall | Stub | Call sites (caller fn) | Label |
|---|---|---|---|
| cellGcmSetFlipMode | 0xCC0B5C | 0x736AC0 (GCM init 0x72F530, arg **2 = VSYNC**); 0x737114 (wrapper 0x7370E0) | VERIFIED |
| wrapper 0x7370E0(x) | - | stores x in gcm+0x1C (gcm=0x1367100). x=0 calls SetFlipMode(1=HSYNC); x=1 calls SetFlipMode(2); x=2 makes no call (the flip then uses FlipImmediate). Called from Present 0x522718 (x=0, on a TimeMode vsync change), 0x522574 (x=0, shutdown) and 0x72ED14 | VERIFIED |
| cellGcmSetVBlankHandler | 0xCC0C5C | 0x737488 (wrapper 0x73747C). Registers handler OPD 0x108C588 = **0x522448** (from 0x5223EC); cleared at 0x5225D8 | VERIFIED |
| cellGcmSetFlipHandler | 0xCC0BDC | no call site found | VERIFIED |
| _cellGcmSetFlipCommand | 0xCC0DBC | 0x7515B4 in 0x751568 (inline cellGcmSetFlip, buffer id ≤7) | VERIFIED |
| cellGcmSetFlipImmediate | 0xCC0C7C | 0x736764 (when gcm+0x1C == 2) | VERIFIED |
| cellGcmGetLastFlipTime / GetFlipStatus / ResetFlipStatus / GetVBlankCount / SetWaitFlip | not imported | none | VERIFIED |
| cellGcmGetControlRegister / GetLabelAddress | 0xCC0C1C / 0xCBFA5C | 0x7368F0 / 0x7368A8, 0x7368B8, 0x513C70 | VERIFIED |
| cellVideoOutConfigure / GetState / GetResolution | 0xCBED7C / 0xCBEE5C / 0xCBEEBC | 0x736A78 / 0x73690C, 0x736A8C / 0x73691C (GCM init); 0x4387D4 / 0x438288 / 0x438298 (0x437610) | VERIFIED |
| sys_time_get_system_time (sysPrxForUser) | 0xCC011C | 31 sites. Timing core: 0x435EC4 (GetHiResTime 0x435EB0) and 0x435F4C (Timer::Step 0x435F28) | VERIFIED |
| sys_time_get_timebase_frequency (sc 147) | inline | 0x435F08, 0x66B744, 0x72E210 (RSX wait) | VERIFIED |
| mftb | inline | 883 sites, mostly profiling. Used for timing at 0x435E60 (GetHiResTime_Ticks) and the RSX-wait timeout 0x72E218/0x72E270 | VERIFIED |
| sys_timer_usleep (sc 141) | inline | 101 sites. Frame-relevant: 0x72E26C/0x72E43C, `usleep(30)` in the RSX ref poll. SystemTimeSleep 0x438960 is the generic wrapper | VERIFIED |
| sys_timer_sleep (sc 142) | inline | 0x72F018 only (`sleep(1)` after a sync, in 0x72EFF0, reached from 0x50BA84; teardown path) | VERIFIED |
| sys_event_queue_receive (sc 130) | inline | 14 sites. Earlier work found main's receives at lr 0xA48ED4/0xA49E3C (SPU events, not vblank) | VERIFIED (sites); runtime from STATUS |

## 2. Frame loop, flip and vblank

- **Main application loop is `0x82358`** (called from 0x13D54). It steps the app Timer at `app+0x130` with
  `Timer::Step` (0x82D0C) and reads its step `app+0x140` as seconds (0x825C8). It then dispatches through virtual
  calls on `app+0x40`, and its back edge is `beq 0x82560` at 0x82D7C. **PARTIAL:** I have not mapped each per-frame
  virtual call to a subsystem.
- **Present:** `DisplayATG::Present(Timer const&)` = **0x5226A8** (vtable slot 5, see STATUS). It calls
  `GcKernel::Present` = **0x72E518** (string "GcKernel::Present()") with r3 = gcm(0x1366F48)+0x98 + 1, the next ref.
  - 0x72E518 first calls **0x72E1E0**. That function polls `ctrl->ref` (*(0x1367140)+8) until it reaches
    gcm+0x98, the previous frame's target, with `usleep(30)`. It has a 4-second timebase timeout that prints
    "Gc ERROR: %s Timeout!".
  - It then stores the new target, flips (0x736770 → 0x736618: cellGcmSetFlip, or FlipImmediate if mode 2) and
    increments the 64-bit frame counter at gcm+0xA0. Command buffers are double-buffered on counter & 1.
  - So the CPU runs at most one frame ahead of the RSX. **VERIFIED.**
- **Vsync mechanism (VERIFIED):** GCM init sets VSYNC at 0x736AC0. On the first Present, the cached flag
  (0x11478C0, initialised to 2) differs from the TimeMode's vsync byte, so Present calls 0x7370E0(0), which selects
  **HSYNC** flip mode. Vsync is then done by a GPU-side semaphore:
  - If TimeMode.vsync (+0x20) != 0, Present (0x522950) pushes NV406E `SEMAPHORE_OFFSET` = label **0x48** (0x735960,
    method 0x64, value 0x480) and `SEMAPHORE_ACQUIRE` = v (0x7359D0, method 0x68). It then calls GcKernel::Present.
    Afterwards it resets the vblank counter (0x12C5EAC+4 = 0) and toggles v (0x12C5EAC+8 ^= 1).
  - The VBlank handler **0x522448** increments that counter. When counter ≥ threshold, it writes label 0x48 = v^1,
    which matches the acquire value of the latest Present.
  - The threshold is `*(0x11478BC) = 1`. It comes from initial data, and the only code reference (TOC slot
    0x10AFBE4-0x6A38) is a read.
  - So each flip executes no earlier than the **first vblank after the CPU's Present**. Display cadence = one flip
    per frame, gated to ≥1 vblank. There is no CPU wait on vblank or flip status.
- **30 Hz vs 60 Hz:** the GPU gate alone allows up to 60 Hz. **HYPOTHESIS:** on hardware the 30 Hz rate comes from
  the frame cost, which exceeds 16.7 ms, plus the one-frame-ahead ref wait. See section 4 for the missing CPU limiter.
- Refresh rate: GCM init stores 59.94 (TOC 0x426FC28F) at gcm+0x104, or 50.0 (0x42480000) if the height is 576
  (0x72E940/0x72EEFC). **VERIFIED.**

## 3. Simulation delta time

- Timing classes (retail ↔ developer build, verified by full-length signature matches):
  - `Timer::Step` 0x435F28;
  - `TimeMode::updateValues` 0x435B50;
  - setters `ForceMinTimeStepInterval` 0x435D08, `SetFixedTimeStepFromRefresh` 0x435D18, `SetTimeRate` 0x435D28,
    `SetVSyncMode` 0x435D38, `SetRefreshRate` 0x435D48, `SetTimeStepMode` 0x146C0;
  - `TimeMode()` 0x435D58; `Timer()` 0x436130; `Timer(TimeMode&)` 0x436208; `SetPaused` 0x4360A8;
  - `GetHiResTime` 0x435EB0; `Time::GetSeconds` (float, ×1e-6) 0x434D00.
  - Time unit: int64 microseconds from sys_time_get_system_time.
- **TimeMode layout (VERIFIED):**

  | Offset | Field |
  |---|---|
  | +0 | fixed step (Time, µs) |
  | +8 | min interval |
  | +0x10 | refresh rate (Hz) |
  | +0x14 | rate (float) |
  | +0x18 | refreshes per step |
  | +0x1C | StepMode (0 = fixed) |
  | +0x20 | vsync |
  | +0x21 | forceMinInterval |

  - updateValues: step = (n·1,000,000 / refresh) µs × rate.
  - minInterval = vsync ? (n−1)·1e6/refresh + 2000 µs : step, or 0 when forceMin is off.
  - Default ctor: 60 Hz, vsync off, StepMode 1, rate 1.0, n = 1, forceMin off.
- **Timer::Step (VERIFIED):**
  - paused: dt = 0;
  - StepMode 0: **dt = the fixed step, whatever the real elapsed time**;
  - otherwise: dt = (now − last) × rate.
  - It then does time += dt and last = now. There is **no clamp and no accumulator or substepping** in Step.
- **Game TimeMode (VERIFIED), helper 0x185B8,** called at 0x4825C for `app+0x108`, which becomes `app+0x148` = the
  Timer's mode; also at 0x186C4 and 0x49E5C:
  - refresh = 60, or 50 when gcm+0x104 is nearer 50;
  - VSync = 1, StepMode = 0 (fixed), rate = 1.0, **FixedTimeStepFromRefresh = 2**, ForceMinTimeStepInterval = 1.
  - **So dt = 2,000,000/60 = 33,333 µs = 1/30 s** (PAL: 40,000 µs = 1/25 s). minInterval = 18,666 µs.
  - The same set is applied at 0x1FAA60 in 0x1F91D0, called 4× from 0x467C8. That function also builds a real-time
    mode: 60 Hz, vsync 0, StepMode 1, n = 1.
- The Timer at app+0x130 is reset in place at 0x71888 (last = now, time = 0, unpaused).
- **Physics (VERIFIED):** `ms2Physics` (RTTI "10ms2Physics", vtable 0x103BFD8) slot 7 = 0x8CF1C0, `Update(dt)`.
  - If dt > 0 it calls:
    - 0x31BA20: a 60 Hz tick converter. ticks += (int)(dt·60 + frac); frac kept at +0x11C; counter +0xA8++. One 1/30
      step gives 2 ticks.
    - Then **one** Havok world step per frame with the same dt (0x30B710: skipped if dt < 1e-5; multithreaded,
      hkpWorld step functions 0xB773F8/0xB77478/0xB77450/0xB7A8E8).
  - **No physics substep loop was found** (PARTIAL: the virtual caller of slot 7 is not traced).
- Constant scan (TOC-inline lfs; `floatscan.txt`): 1/30 (0x3D088889 etc.) at 34 sites, 30.0 at 32, 60.0 at 15,
  1/60 at 5, 1/120 at 4, 120.0 at 3, 59.94 at 1 (GCM init).
  - 1/30 is spread across gameplay code (0x36F650, 0x371858, 0x37F770, 0x432EB8 …). **PARTIAL:** this fits code
    written for a 30 Hz step; I did not identify each use.
- Other per-frame timers: Present steps its own display Timer (+0x3C8) and stores the frame time in ms (×1000.0) at
  +0x30. Post-flip seconds (×1e-6) go to +0x34. **VERIFIED.**

## 4. Frame counters and limiting

- Frame counters (VERIFIED):
  - gcm+0xA0 (u64, +1 per GcKernel::Present);
  - render-system +0x2A0 (+1 per Present at 0x522870);
  - vblank counter 0x12C5EAC+4 (reset on Present);
  - 60 Hz physics ticks (0x31BA20).
- **CPU frame limiter:**
  - In the developer build, `Timer::SleepTilMinStepInterval` (0x89ED8) usleeps until minInterval has elapsed.
  - It has **no retail match and no caller in either build**.
  - No usleep, SystemTimeSleep or system-time call sits in the main loop 0x82358.
  - VERIFIED for those sites: retail has no CPU-side minimum-frame-time sleep. Pacing = RSX ref wait plus the
    vblank-gated semaphore before each flip.
- Consequence (VERIFIED from the code above): sim speed ∝ presented fps, because each frame advances exactly 1/30 s.
  - At 13 fps the game runs at 43% speed.
  - Above 30 fps it would run fast; the ceiling is set by the ≥1-vblank gate (60 Hz).

## 5. Runtime evidence (existing, not re-run)

- perf_t15/FINDINGS.md: garage at 11.7–13.2 fps; guest flip-request interval median 75–82 ms. Presented fps = guest
  flip rate.
- STATUS (T21): main's waits are the condition-variable back-off and SPU event receives. 7 Ice usleeps at lr
  **0x72E5C0** = the return from the 0x72E1E0 ref wait inside GcKernel::Present (consistent with section 2). There
  is no guest vblank wait.
- RESEARCH: the port's vblank ticker is 62.5 Hz (16 ms steps), not 59.94. The flip gate (label 0x48 written by the
  guest vblank handler 0x522448) depends on this ticker, and runtime gating via label 0x48 is unverified in the port.
  T104 counts guest fps from 0x72E1E0 entries.

## Open items

- Map the per-frame virtual calls in 0x82358, and the caller of ms2Physics slot 7, to confirm one physics step per
  frame.
- Confirm at runtime that the port honours the NV406E acquire on label 0x48 (method 0x68) and runs the guest vblank
  handler at 59.94 Hz.
