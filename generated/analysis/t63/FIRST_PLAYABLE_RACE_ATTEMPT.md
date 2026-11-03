# T63: first playable race attempt

2026-10-26. One bounded private session. Nothing merged or pushed. Shared worktrees, `port/` and `generated/hdd0|hdd1` are untouched.

## Result: **PARTIAL**

- **Menu navigation (VERIFIED):** it worked end to end, using original handlers only: Main menu → Festival → Earth Zone → Kanaloa Bay "Light Fantastic" ticket → vehicle select → ATV → loading screen.
- **Race loading (VERIFIED):** the original race path ran: race state `0x3B710` (lr `0x3BFF8`, the non-garage request branch) → race loader `0x8EA00` → `LoadRace 0x89230`.
  - `worlds/track_happy_jungle` and `env/Track1a_KanaloaBay_S…` were requested.
- **Race not reached:**
  - `LoadRace` was still open after **83 s**, when the session hit its cap at 205 s.
  - The PostLevelLoad return sites (`0x8C2A0`, `0x8C2E0`) and `0x8C848`/`0x8D2B0` never fired.
  - No vehicle, camera, countdown or physics was observed, and no driving test was possible.
- **Hang or slow load: undetermined.** The `fc-watchdog` reported no stall and frames kept presenting at about 32 fps.

## 1. Executable and configuration

- **Exe:** `build/motorstorm-t62-font-c529ab0`, copied to `t63/exe/`, sha256 `162afb4a40fd8dc9f0f0ae60fe30eb0b2ebdb9dc785281a48c3bcd47882ab6b7`. This is T62B's exe (`307b08a` + T61 `166c973`). No rebuild.
- **Env (T44/T62B):**
  - `FIRST_FRAME=1`, `FIRST_FRAME_AUDIO=native`, `GCM_INTERACTIVE=never`, `PS3_DEV_SKIP_INTRO=1`, `PS3_VERBOSE=0`;
  - `PS3_FC_WATCHDOG_MS=5000`, `RSX_HEARTBEAT_MS=1000`, `PS3_TEX_SNAPSHOT=1`, `RSXI_MAX_MB=512`;
  - `PAD_FILE`, `PS3_TRACE_FILE=t63_trace.cfg`;
  - `CELLMARK_DUMP=160`, `EVERY=60`, `MINDRAWS=1`.
- **Not set:** `TEX_SAVE`, `TEX_NOCACHE` and WWS AOT.
- **HDD:** fresh private copies `t63/hdd0` (0 files) and `t63/hdd1` (4 files, `snapshot_manifest.json`).
- **Runner:** `t63/run_t63.py` (observe-only controller, hard kill at 205 s) plus `t63/op.py` (operator: one press per step, after looking at the newest frame dump and the page-load log).
- **Session length:** the session ran 205 s, not the authorized 5 min. `tools/fast_startup.py` refuses timeouts above 210 s; that cap exists because of earlier host power losses, and I did not override it. The first launch attempt (`--timeout 295`) was refused before any game process started (`runtime-20261026-130557-refused-not-launched`).
- **Run directories:** `generated/runs/20261026-130707-t63-first-race` and `t63/runtime-20261026-130707/`.

## 2. Navigation performed (host s; every press was decided from a frame dump)

| t | Screen (screenshot) | Input | Result |
|---|---|---|---|
| 38.7 | `mainmenu.gui`, THE FESTIVAL highlighted (`01`) | — | — |
| 47.7 | same | CROSS | `GameTypeSetFestival 0x76AF40` → `festivalguide.gui` |
| ~50 | Festival rank tutorial panel (`02`) | — | — |
| 61.4 | same | CROSS | `ProfileSave 0x17420`, then **back to `mainmenu.gui`** at 63.1 (`03`). Unexpected; cause unknown (HYPOTHESIS: first-visit tutorial flow). |
| 78.7 | main menu, FESTIVAL | CROSS | `0x76AF40` → `festivalguide`, Festival menu, EARTH ZONE highlighted (`04`) |
| 87.2 | Earth Zone | CROSS | `SetSelectedZone 0x33848` → `ticket-select-earthzone` |
| ~92 | ticket 1 of 24, Kanaloa Bay / Light Fantastic, ATV and buggy allowed (`05`) | — | — |
| ~103 | same | CROSS | `SetSelectedTicket 0x359D0` (r5 = "Light Fa…") → `motorstorm-vehicleselect`, ATV focused, ATV Info tutorial (`06`) |
| 113.1 | ATV Info | CROSS (Continue) | `ProfileSave` (2nd), stats view (`07`) |
| ~121 | ATV | CROSS (Select) | `ApplyConfigFromTicket 0x83848`, `0x727B0`, `ShutdownTaskset`, `loadscreen-controls1` (`08`), `0x3B710` ← `0x3BFF8`, `SetGoToRace 0x1EBD38`, `0x8EA00`, `LoadRace 0x89230` (121.5) |
| 122.4 / 141.5 | loading | none | `worlds/track_happy_jungle`, `env/Track1a_KanaloaBay_S…` |
| ~150–205 | loading screen washes out to white (`09`, `10`) | none | no further page loads; LoadRace still open at the cap |

- Totals: 7 CROSS presses, all consumed. No D-pad needed: every default focus was the wanted item.
- No profile or save dialog appeared; both ProfileSave calls returned silently.
- The invitation popup reloads with each page but never took focus.

## 3. Screenshots

`t63/screens/01…10_*.png`. All 102 raw backbuffer dumps (about every 2 s) are in `runtime-20261026-130707/frames/`.

## 4. Furthest state

The loading screen inside `LoadRace` for Festival race Light Fantastic (Kanaloa Bay), ATV class.

## 5. Race assets

**PARTIAL.**
- Track world and environment requests: VERIFIED.
- Loader completion: NOT observed.
- `fs open FAIL` on loose files that do not exist on disk: `data/events/light_fantastic.race`, `audio/atvsmall_player.vsb`, two `dspsettings/*.mng`. These may come from the PSARC instead (UNVERIFIED; not necessarily a defect).
- The LFQueue PushBody rate (streaming/decompression) fell from about 180/s before the load to about 30–50/s at 130–170 s. There were none at 180–200 s, then 121 in the last 5 s.
- No NOSYS, no non-zero HLE returns, no crash, no Present timeout.

## 6. Vehicle physics

**Not reached:** no race initialization, so no physics batch.

## 7. Driving controls

**Not tested.** The game's controls screen (`08`) confirms: R2 accelerate (`0x0200`), L2 brake/reverse (`0x0100`), D-pad steer, CROSS boost.

## 8. Frame rate

- Startup and menus: about 32 flips/s (also 32 draw frames/s).
- Loading: about 32/s (for example, 5635 → 5797 flips in 5 s).
- Bink decode: 28.7 frames/s.
- Gameplay: not reached.

## 9. First blocking issue

**`LoadRace 0x89230` does not return within 83 s** (VERIFIED). T36's garage `LoadRace` took 10.9 s. Over the same period:
- streaming slowed to near zero;
- the loading screen over-brightened to white (the known exposure symptom);
- the main thread showed no fault.

Cause is HYPOTHESIS, in this order:
- (a) a stall in a race-only stage of LoadRace: this run traced only 4 of its 59 marker sites, so the stuck stage is unknown;
- (b) a genuinely slow load, given the known slow SPU decode;
- (c) a resource wait.

No code change is justified yet.

## 10. Recommended follow-up (T64, narrow)

One bounded session, same exe, env and HDD procedure, adding only **T36's 59 LoadRace marker `ret=` sites** (plus FIOS read logging, if cheap).
- Navigation is now known: 7 CROSS presses, each gated on its page load. Done promptly, the race load starts at about 90 s, leaving about 115 s of loading inside the 210 s cap.
- Goal: name the last LoadRace stage reached and whether it is still progressing.
- Alternatively, approve a longer cap. Raising the 210 s host-safety cap is the owner's decision.
- Expect the Festival tutorial to bounce back to the main menu once. No save file was written: `t63/hdd0` is still empty after both `ProfileSave` calls. Whether saving silently fails is a separate open question (UNVERIFIED).
