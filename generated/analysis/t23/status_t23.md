## T23: path to the first race, offline (2026-10-25, no launch, no build, no code change)

Supporting files: `generated/analysis/t23/`.

- Baseline (VERIFIED):
  - Primary branch `motorstorm/v0.17-integration` = `307b08a`. It is not checked out in any worktree except the detached `ps3recomp-307b08a` (clean).
  - `ps3recomp-int` is on `agent/t18-c38-trace` `8f7ac89` (307b08a + c38 tracing), with one pre-existing modified file (`scratch/ppu_conformance_run.bat`).
  - Latest primary exe: `build/motorstorm-int-nm-307b08a/MotorStormPacificRiftRecomp.exe`, SHA-256 `96D9DEE10AC111A36162EE200FCA92D639169BBB356A816A0B591DABC61DBC22`. It was built from `generated/ppu-hooked-staging`, so `PS3_TRACE fn=` works on it, and it was used by run `20261025-102805-garage-capture-probe`.
  - Nothing from the T18/T22 performance branches (`ps3recomp-t17` `3b38721`) is integrated, and none is needed here.
- Where the game stands (VERIFIED from capture `generated/introskip/t16_view/f002064_bb.png`): the garage with the rider, a ◀▶ selector bubble, an info box and the ✕ ○ □ △ button bar. This matches `mainmenu.gui` (Festival / Wreckreation / Garage / Options / MotorStore), the first screen that waits for input. Its text is not drawn (see font, below). That the page is `mainmenu` is INFERRED (page changes are not logged).
- Frontend-to-race state machine (GUI scripts VERIFIED in `garage_menu/FINDINGS.md`; game-code steps VERIFIED statically here):
  1. `mainmenu` Festival Accept, gated on `GetPageOpacity() > 0.5` → `GameTypeSetFestival` `0x76AF40` (stores 1 at `+0x26D4` and `+0x26E0`) → `festivalguide`.
  2. Zone Accept → `SetSelectedZone` `0x33848` → `ticket-select-<zone>`.
  3. Ticket Accept → `SetSelectedTicket` `0x338C0`, gated on `TicketSelectable` `0x5C590` → `festivalguide-vehicleselect`.
  4. Class Accept, gated on `TicketClassSelectable` `0x359D0` → class page.
  5. Accept → `SetPlayerVehicleClassChoice` `0x145B0` → `loadscreen-popup` → `SetGoToRace(true)` `0x1EBD38` (`[+0xAE]=1`) and `ApplyConfigFromTicket` `0x83848`.
  6. Hub transition `0x3BFA0` reads the flag through `0x1E61E8`. With game type ≠ 10 (festival = 1) it calls `0x3B710` and pushes the race state; with type 10 it pushes the garage load `0x8D9F0`.
  7. Race state group: `0x727B0`, loader `0x8EA00` (loading screen `0x329660`), `0x6CC98`, `0x706B8`, `0x13FB0`. Which member is the per-frame simulation update is not identified.
  - Not known statically: the default focus on each page, and whether first-visit popups (tutorial / invitation) appear.
- Controller/HLE readiness:
  - Host: XInput, plus a keyboard fallback on port 0 (focused window only) and the `PAD_SCRIPT` / `PAD_FILE` / `PAD_PRESS_ON_OPEN` injectors.
  - The four pad tests of the primary source pass offline (`test_pad.cmd` → `test/*.log`): capability info (128-byte clear), packet ABI (`len` 8 / 20 / 24, `button[1]`), trigger GetData, sensor mode.
  - `cellPadSetSensorMode` `0xBE5BE3BA` is registered in the primary build (`ppu_hle_nids.cpp:1741`). It returns UNSUPPORTED because no host motion sensor exists. The game calls it only when the SENSOR capability is reported, which it never is, so no sensor words are read.
  - Guest pad thread `0x72ADF0`: per `FINDINGS.md`, `cellPadGetInfo` (system_info 0, port 0 status CONNECTED here) gates `cellPadGetData` on ports 0–6. In T17 it polled port 0 about every 10 ms (15 reads during a 156 ms press).
  - GUI consumption, VERIFIED at runtime earlier (`docs/INTRO_SKIP_VALIDATION.md`): one injected CROSS on port 0 was taken by the intro page's own Accept; the movie closed 62 ms after the release, then the normal path to the garage followed. Every link from host packet through guest pad thread to GUI Accept has therefore worked once. Input on the garage pages has never been sent: no earlier run used `PAD_*`.
  - `PAD_SCRIPT` verified offline (`test/test_pad_script_getdata.c`, private): 2 scripted presses give 2 rising and 2 falling CROSS edges in `len > 0` packets, about 0.63 s held, nothing early, nothing on ports 1–6.
- Earliest blocker: none is confirmed. The earliest UNVERIFIED transition is step 1, the main menu accepting a press, simply because no input has been sent after the garage appeared. No static defect was found on the path to `SetGoToRace` or the race-state push.
- Other gaps found (not shown to block anything):
  - The only unresolved import reported at runtime is `cellFontInitLibraryFreeTypeWithRevision` (`0x7A0A83C4`, stub `0xCBF23C`). It gets a faked `CELL_OK` and its library out-parameter is left unwritten. HYPOTHESIS: this explains the missing menu text; it does not gate input.
  - The sensor/tilt issue from `FINDINGS.md` defect 2 does not apply to the primary build: the SENSOR capability is not reported.
- No fix was made: no emulator defect on the progression path was established.
- Remaining unknowns:
  - default focus and first-visit popups on each page;
  - the race-state member that runs per frame;
  - race-load duration (garage loads took 14–16 s);
  - whether `track` assets load with no missing files;
  - vehicle and physics initialisation (Havok).
- Prepared launch (NOT run): `powershell -NoProfile -ExecutionPolicy Bypass -File generated\analysis\t23\run_t23_race_path.ps1`. The `-DryRun` preflight passes (`dryrun.txt`).
  - It is the T17 wrapper on the primary exe (hash checked), without ftrace, plus:
    - `PAD_SCRIPT`: CROSS every 5 s from 40 to 135 s of pad time. Pad time starts at the first `cellPadGetData`, about 9.5 s after process start, so presses fall at roughly 50–145 s of process time. Input only.
    - `PS3_TRACE` from `t23_race_path.cfg`: 26 functions (pad thread and update, GarageInput, the festival commands, `SetGoToRace`, `ApplyConfigFromTicket`, the hub transition, the race-state push, the garage and race loaders, the race state group). `limit=6`, then power-of-two visits, `max=20000`, per-function totals every 10 s, on stderr. It parses cleanly against `307b08a`'s tracer (`test/pt_cfg_check.log`).
    - One RSXI frame captured 95 s after `depth_surface_created`: the last screen reached.
  - Kept: intro skip, renderer settings, VFS/HDD roots, `--timeout 150`, `--stop-on-fatal`, `--snapshot-cache`, tree kill at 210 s, cleanup by 225 s, no retry, one instance (preflight refuses a running image or launcher). `PAD_*` and `YDKJ_*` are also scrubbed from the inherited environment.
  - Reads:
    - `[cellPad] PAD_SCRIPT … press` lines (host packet);
    - `[PT] … fn=0072B530` (guest pad update);
    - command-handler entries in order (`76AF40`, `33848`, `338C0`, `145B0`, `1EBD38`, `83848`);
    - `3B710` / `8EA00` / `329660` (race request, loader, loading screen);
    - `fnstat` entry counts of the race group (a per-frame member means the simulation is running);
    - the captured frame.
  - Limits:
    - blind timing: if the main menu's default focus is not Festival, CROSS opens another page, and the trace shows which;
    - CROSS in a race is an action button, not throttle;
    - an armed `fn=` makes every hook cost about 17 ns, which may slow frames.
- Reproduce (from the motorstorm root):
  - `cmd /c generated\analysis\t23\test_pad.cmd`
  - `cmd /c generated\analysis\t23\test_pad_script.cmd`
  - `py -3 generated/analysis/dis.py 76AF40 76AFA0` and `… 3BFA0 3C0C0`
  - the NID check script in `unregistered_imports.txt` (name → NID via SHA-1 suffix `6759659904250490566427499489741A`; that list over-reports runtime built-ins, so the runtime `[hle] unresolved NID` lines are authoritative)
  - `grep "unresolved NID" generated/runs/20261025-102805-garage-capture-probe/stderr.log`

