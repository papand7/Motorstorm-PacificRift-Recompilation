# Menu initialization

Offline (2026-10-23). The main menu has never been observed. Nothing here is verified at runtime unless it is labelled so.

## Dependencies (what the original code needs before `mainmenu.gui`)

| Dependency | Status |
|---|---|
| Intro completes and the frontend leaves the video state | VERIFIED with silent audio. **BLOCKED with native audio:** the hang at Bink frame 2255; see [POST_INTRO_TRANSITION.md](POST_INTRO_TRANSITION.md) |
| GotoGarage → garage world `track_garage*.rpk` loaded from `MS2.PSARC` via FIOS | request VERIFIED; load UNKNOWN (no read logged) |
| Loading screen: PrepareLoadingScreen / PopulateLoadingScreen / Preload / PreloadDone | handlers mapped statically; runtime order UNKNOWN |
| Emblem / artwork screen renders | seen once; then went white → black (auto-exposure readback is a HYPOTHESIS) |
| `mainmenu.gui` loaded | referenced by `func_00016758`; members `/gui/mainmenu.gui` and `/data/gui/MainMenu.gui` exist; never observed being read |
| HowManyPads (`0x00013F18`) / GarageInput (`0x0002B410`) get a connected pad (corrected 2026-10-24; `0x0076AF40` is GameTypeSetFestival, `0x00014698` is SetGarageType) | see Input below |

## Rendering pipeline for the menu (what is known)

- **Guest side:** GCM command buffers → runtime RSX FIFO → D3D12 backend.
- **Verified for the frontend so far:**
  - splash screens;
  - the Bink intro (D3D12 texture-source order fix);
  - fragment pipeline `0x02193941`, which needs 16 texture units;
  - cellFont glyph atlas.
- **Not exercised yet:** garage and menu scene draws. Their shaders, render targets and any exposure readback are unknown.
- **The white-out** points at a GPU→CPU readback path (luminance), but this is not traced.
- **How to observe it:** a draw-gated RSX capture (`--capture-rsx --capture-at`) at the first milestone after the garage request. This is an extended run and is not authorized.

## Input (Phase G, coordinated with the secondary agent; not duplicated)

- **Primary checkout (`libs/input/cellPad.c`):**
  - XInput backend;
  - keyboard fallback on port 0 when no XInput pad is present (`PAD_NO_KEYBOARD=1` disables it);
  - the game creates `FpPadThread` (tid 20) at startup.
- **Missing:** `cellPadSetSensorMode` (sys_io NID `0xBE5BE3BA`; stub `0x00CC097C`). The game imports it and the trace records 39 calls.
- **Secondary branch (`motorstorm-garage-audit`):**
  - adds `cellPadSetSensorMode`, returning unsupported for no-motion backends;
  - fixes the pressure/sensor packet lengths (20/24);
  - removes false sensor capability claims.
  - Its own handoff says to review it selectively before integrating; it is not integrated here.
- **Not shown:** whether motion controls are required for menus. No synthetic input will be injected. Menu navigation needs a real XInput press, in a separately authorized run.
