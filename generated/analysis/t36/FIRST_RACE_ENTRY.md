## T36 first-race entry: one bounded diagnostic run (2026-10-26)

Private. One launch, no retry, no rebuild, no code change, no merge or push.

### Run
- Exe: `build/motorstorm-int-nm-307b08a/MotorStormPacificRiftRecomp.exe`, copied to `t36/exe/`. Runtime `motorstorm/v0.17-integration` @ `307b08a`, lifted from `generated/ppu-hooked-staging`. SHA-256 `96d9dee10ac111a36162ee200fca92d639169bbb356a816a0b591dabc61dbc22`. The T30 fix branch is not in this exe.
- HDD: private snapshot `t36/hdd0` (empty) and `t36/hdd1` (4 files, `snapshot_manifest.json`). Baseline files untouched.
- Env:
  - `SPURS_LFQ_TRACE=1`, `SPU_JOBEXEC=1`, `SPU_DMA_RANGE=FB2C00-FFAA40`.
  - `PS3_TRACE_FILE=t36_trace.cfg`: 40 fn, the 59 LoadRace marker sites, 6 HLE.
  - `PAD_FILE` closed loop, `PS3_FC_WATCHDOG_MS=5000`, `PS3_DEV_SKIP_INTRO=1`. The intro skip is one real CROSS press, the same as in earlier approved runs.
- Driver: `t36/run_t36.py launch`.
- Logs:
  - Controller: `t36/runtime-20261026-061327/` (`controller.log`, `timeline.jsonl`).
  - Run: `generated/runs/20261026-061327-t36-first-race/` (`stderr.log`, `stdout.log`, `rsxi/frames/f004569`).
- Stop: the controller stopped the run at 96.8 s (57.6 s after garage entry). Reason: "input stopped: GameTypeSetFestival 0x0076AF40 not entered". Process killed after the capture.

### Progression (host seconds from launch)
| t | Event | Status |
|---|---|---|
| 26.9 | Garage loader `0x8D9F0` entered. `0x1EBD38` called with r4=1, then 0, on the garage path, so it is not a race-only marker. | VERIFIED |
| 27.4–38.3 | `LoadRace 0x89230` runs for the garage: all marker sites from `0x892C4` to `0x8C848`, 10.9 s. | VERIFIED |
| 39.19 | `0x8D9F0` exits: garage entry G. | VERIFIED |
| 49.22 | Press 1, CROSS. Consumed. | VERIFIED |
| 52.30 | Press 2, UP. Consumed. | VERIFIED |
| 54.35 | Press 3, CROSS. Within 0.13 s, `LeaveGarage 0x5C0B0`, `SetFirstGarageVisit 0x17EC0` and `SetConfigGUIPage 0x2C310` all run. **UP selects Yes.** | VERIFIED |
| 54.10 / 54.19 / 54.52 | Page loads (`0x536A30`): `gui/black.gui`, then `gui/mainmenu.gui`, then `gui/invitation-p…` (mainmenu enter `+0x2C4` does `PushPage(invitation-popup)`). `gui_b.bik` background video opens. | VERIFIED |
| 54.5–72.6 | No loader runs (no `0x89230`/`0x8D9F0`). Waited 12 s, then the 6 s settle. | VERIFIED |
| 72.65 | Press 4, CROSS. Consumed by `cellPadGetData`. Entered in the next 4 s: only `0x3BFA0` and `0x1E61E8`, which are per-frame (69 entries, dispatcher lr `0x780290`). `GameTypeSetFestival 0x76AF40` not entered, so input stopped as specified. | VERIFIED |
| 96.8 | Capture, then stop. | — |

Not reached: festivalguide, ticket, vehicleselect, `SetGoToRace` for a race, race enter `0x8EA00`, race config `0x727B0`, race state `0x3B710`, race streaming, vehicle/physics init, first race frame.

### Blocker
**Main menu is loaded but renders no widgets, and CROSS has no effect.** Status: PARTIAL (symptom VERIFIED, cause unknown).
- Final capture (`t36/final_bb.png`, `final_snaps_sheet.png`):
  - Only the `gui_b.bik` parachute background is visible; no menu items or text in the backbuffer or in any of the 14 render targets.
  - Draw count is a constant 41–42 per frame from 72 s to 96 s, at about 63 fps.
- A CROSS 18 s after the page load produced no Accept.
- HYPOTHESIS A: mainmenu Accepts require `GetPageOpacity() ≥ 0.5` (T30 frontend item 3). If the page fade never progresses, the widgets stay invisible and input is ignored. This matches the earlier "emblem brightens to white then goes black" symptom.
- HYPOTHESIS B: input focus or the page stack. The pushed `invitation-popup` overlay sits on top. Its handlers only hide it when there are no pending invites, so it probably does not take Accept, but this is not verified.
- HYPOTHESIS C: widget draws fail or are culled in the backend (the menu state is fine but invisible). This would not explain the missing Accept by itself.
- Next step, offline (no launch needed to decide): find where `GetPageOpacity` reads the page fade value and what drives it. Trace those functions plus the mainmenu page update `+0x50` in a later approved run.

### Diagnostics requested
These cover the garage boot and the menu; no race load happened.

| Category | Result | Status |
|---|---|---|
| Streaming / decompression LFQ | 96 `PushBody rc=0`, no NOSYS, 0 non-zero HLE returns. No loss in this window. | VERIFIED |
| SPURS shutdown / sync | 0 Shutdown or RemoveWorkload calls. `spu_workload` WAIT_SIGNAL loop on taskset `0x10483480` task 0 (ran 0 ms, idle). | VERIFIED (not exercised) |
| Audio SPU | MultiStream image `283218738` `synthesised stop 0x0000 at LS 0x19800` at 24.36 s. 24 `EventFlagWait BLOCKED`. 8 zero-size DMA REJECTED. Same as T30 race item 1. | VERIFIED (known) |
| WWS job modules | Policy module `1297305682` runs through the interpreter (8 `microstep`). `SPU_DMA_RANGE`: module EAs `0xFD3180`–`0xFFA800` fetched, including `0xFF2800` (vehiclephysics, 4×) already in the garage. The 4 `spu-dma` "identical transfers for 30s" polls at pc `0x25A4` are idle-polling. `SPU_JOBEXEC` produced no matching log lines. | PARTIAL |
| Missing resources | No failed opens in the log. | VERIFIED |
| Frame clock | `fc-watchdog` armed; no stall report. | VERIFIED |

### Facts for the next run
- UP on the garage quit popup selects Yes; `LeaveGarage` follows CROSS within 0.13 s.
- `mainmenu.gui` loads about 0.1 s after `SetConfigGUIPage`, with no loading screen.
- `0x1EBD38` and the LoadRace markers also fire for the garage load. Only `0x8EA00` and `0x727B0` mark a race.
