# Garage menu, input and race transition: offline audit (2026-10-24, no launch)

Inputs: decrypted EBOOT, lifted `generated/ppu`, GUI pages extracted from MS2.PSARC (`gui/`, private), runs
20261023-172442, 20261024-180419, 20261024-194334. Helpers: `gui_handlers.py`, `psarc_get.py`, `cmdmap2.py`, `pmf.py`.

## Correction to earlier docs (VERIFIED)
Frontend command table entries are `{OPD, name_ptr}`, not `{name_ptr, OPD}`. Evidence: Set/Get pairs line up
(SetGarageType 0x14698 `stb [0x70]` / GetGarageType 0x146A0 `lbz [0x70]`), and MainMenuMotorStoreGuard → 0x16758,
the function that references "mainmenu.gui". POST_INTRO_TRANSITION.md / MENU_INITIALIZATION.md / frontend-toc-map.txt
are shifted by one: e.g. 0x5C0B0 is LeaveGarage (not GotoGarage), 0x14698 is SetGarageType (not GarageInput),
0x76AF40 is GameTypeSetFestival (not HowManyPads). Correct handlers:

| Command | Handler | | Command | Handler |
|---|---|---|---|---|
| GotoGarage | 0x2DE08 | | SetSelectedZone | 0x33848 |
| LeaveGarage | 0x5C0B0 | | SetSelectedTicket | 0x338C0 |
| GarageInput | 0x2B410 | | TicketSelectable | 0x5C590 |
| HowManyPads | 0x13F18 | | TicketClassSelectable | 0x359D0 |
| GameTypeSetFestival | 0x76AF40 | | SetPlayerVehicleClassChoice | 0x145B0 |
| FrontendVideoCanStart | 0x14AF8 | | ApplyConfigFromTicket | 0x83848 |
| SetIntroVideoSeen | 0x147F0 | | SetGoToRace | 0x1EBD38 |
| MainMenuMotorStoreGuard | 0x16758 | | PrepareLoadingScreen | 0x18060 |
| EnableButton | 0x83320 | | PopulateLoadingScreen | 0x2AAF8 |
| SetGarageVehicle | 0x33888 | | Preload / PreloadDone | 0x13E58 / 0x13EE8 |

## Menu state machine (VERIFIED from GUI scripts; "kind" field meaning is HYPOTHESIS)
mainmenu (idle 90 s → attractvideo):
- Festival → `GameTypeSetFestival`, → festivalguide
- Wreckreation → wreckreation; Garage → garage-temp-interior; Options → options; MotorStore → motorstore-connecting
- each Accept is gated on `GetPageOpacity() > 0.5`; focus handlers only change highlight/info text.
festivalguide → `SetSelectedZone(Earth|Air|Fire|Water)` → ticket-select-<zone> (spinner prev/next; Accept:
`SetSelectedTicket`, `TicketSelectable` gate) → festivalguide-vehicleselect (per-class `TicketClassSelectable`)
→ class page → Accept: `SetPlayerVehicleClassChoice(n)`, PopPage, → loadscreen-popup → `SetGoToRace(true)`,
`ApplyConfigFromTicket`, `PopulateLoadingScreen`, `PrepareLoadingScreen`. Back = `TransitionBack()` everywhere.

## Race transition (VERIFIED static)
- `SetGoToRace` 0x1EBD38: `[obj+0xAE]=1`, `[obj+0xAF]=0`, calls 0x1EB9E0, 0x752218, 0x753318.
- Getter 0x1E61E8 ← 0x3BFA0 (state member, TOC slot 0x109A8CC): if set and game type `[+0x26D4]==10` → push the
  garage-load state (0x8D9F0); else 0x3B710 (in 0x3B1B0) → push the race state.
- Game states are PMF groups in TOC: race {0x727B0, **0x8EA00 load**, 0x6CC98, 0x706B8, 0x13FB0}; hub
  {0x6CF48, 0x60D70, 0x82188, 0x18518, 0x698A0, 0x3BFA0}; garage {0x82308, **0x8D9F0 load**, 0x41488, 0x70380, 0x14628}.
- Race loader 0x8EA00 ("Game type is %d", "Track info for (%s)…", "Vehicle type is %d"): loading screen start 0x8EA64
  (0x329660), stop 0x8EE88 / unwind 0x8F0A4. Same synchronous pattern as the garage loader.
- All of the above are lifted (`generated/ppu`, incl. `func_0072B530`). None has been observed at runtime.

## Controller path (VERIFIED static + logs)
- Init 0x72B258 (← input init 0x728D58 at 0x7294E8): `cellPadInit(7)`, 0x7D88-byte state, lwmutex, event queue,
  thread "FpPadThread" (tid 20, OPD 0x1096F38, prio 255). Sample period `[+0x7D80] = 1e6 / rate` µs; rate unknown statically.
- FpPadThread 0x72ADF0: lock; `cellPadGetInfo` into a 20-slot ring (slot 1604 B); if not intercepted
  (system_info bit 0), `cellPadGetData` ports 0–6; unlock; `sys_timer_usleep`; exits on an event-queue message.
- Update 0x72B530 (bl from 0x7292E0): per port, a state machine 2 = disconnected → 5 = active (on status bit 0)
  ⇄ 6 = intercepted. In state 5, each update: `GetCapabilityInfo` → `SetPressMode(1)` if PRESS cap, `SetSensorMode(1)`
  if SENSOR cap (flags 1/2/4/8 = press/sensor/HP-stick/actuator). This is why the logs show ≥39 SetSensorMode calls
  (log capped at 40): every update, not re-detection.
- Packets: processed only if `len > 0`; `len == 0` keeps the previous mask (= no change). Mask bits: DIGITAL1 → 0x01..0x80,
  DIGITAL2 → 0x100..0x8000. Edges in guest: +0x54 pressed, +0x50 released, +0x58 held. Pressure words read only if press
  mode was accepted and `len > 8`; sensor words (button[20..23]) only if sensor mode was accepted and `len > 20`.
- Sticks: right X/Y = button[4..5], left = button[6..7], through 0x72C810.

## Native defects
1. VERIFIED, fixed in branch `agent/garage-input-audit`: `cellPadGetCapabilityInfo` cleared 64 words (256 B) into a
   32-word (128 B) struct. MotorStorm passes r1+0x78 with its CellPadInfo copy at r1+0xF8 → header and vendor/product
   ids clobbered. Effect today: benign for one pad (only status bytes at +0x208 are read later); a second pad connecting
   would get vendor/product 0. Test `libs/input/tests/test_pad_capability_info.c` (old code fails at the guard).
2. VERIFIED, not fixed here (covered by the uncommitted motorstorm-garage-audit patch): `CELL_PAD_LEN_CHANGE_PRESS_ON`
   is 24 (SDK 20) and `cellPadSetSensorMode` is unresolved (faked CELL_OK). Combined: the game believes sensor mode is
   on and `len 24 > 20`, so it reads sensor X/Y/Z/G = 0 into its sensor history. Default RaceConfig binds Slam to
   SixAxisTiltX → HYPOTHESIS: constant extreme tilt in races. Not a menu blocker (menus use digital buttons).
3. No other pad API is missing: all 8 imported cellPad functions except SetSensorMode are implemented.

## Ranked blockers to a functional menu
1. Menu has never been observed (garage compositing/readback, primary agent's milestone). BLOCKED on that.
2. No runtime confirmation that a real press reaches `func_0072B530` and the GUI (no physical pad test).
3. Loading duration ≈14–16 s per load (unknown wait), applies to the race load 0x8EA00 too.
4. Sensor-data defect (2) before races.

## Pad ABI milestone (2026-10-24, offline)
- Sensor gate (VERIFIED static): 0x72B990 tests cap bit 0x2 → SetPressMode(1) (stub 0xCC0A1C), flag |= 1 on r3 == 0 (0x72C618);
  cap bit 0x4 → SetSensorMode(1) (stub 0xCC097C), flag |= 2 on r3 == 0 (0x72C62C). Sensor words read only if flag 2 and
  len > 20 (0x72BEA8..0x72BEBC). With no SENSOR cap the game never calls SetSensorMode and never reads button[20..23].
- Integrated the motorstorm-garage-audit sensor/length hunks (keyboard remap left out) + capability fix; pressure fill
  for digital bits now only replaces 0 (XInput trigger analog value was forced to 255 above threshold 30).
- Consumers of the game's sensor history (r26+0x2B0.. +0xC) and what tilt they use without flag 2: not traced (HYPOTHESIS: neutral/unused).
