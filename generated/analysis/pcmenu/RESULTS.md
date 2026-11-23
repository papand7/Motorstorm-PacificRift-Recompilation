# PC Settings page: results (2026-11-05)

Private notes. The generated pages in `build/pcmenu/gui/` are game data and are never committed.

## What it is
- **Options menu:** AUDIO, DISPLAY, WIRELESS CONTROLLER, **PC SETTINGS** (LANGUAGE stays hidden, as in retail).
  - The page is `gui/optionz.gui`, built from the retail `options.gui` by `tools/make_pcmenu.py`.
- **PC Settings page:** `gui/options-pc.gui`, built from the retail Controls page. It has 8 rows in two columns:

  | Left column | Right column |
  |---|---|
  | Display Mode | Dynamic Resolution |
  | Resolution | Motion Blur |
  | V-Sync | Texture Filtering |
  | Frame Rate | HD Textures |

  - Left/Right changes a value. Back saves `settings.ini` next to the exe.
- **Port side:**
  - `port-vkgame/pc_menu.cpp` and `pc_settings.h`;
  - `PS3_VFS_OVERLAY` in `sys_fs.c` / `vfs_overlay.h`;
  - two lifted call sites routed by `tools/pcmenu_lifted.py`.
- **Without** a `pcmenu` folder next to the exe (or `PS3_VFS_OVERLAY`), the game shows the retail Options page. `settings.ini` alone still applies.

## Runs
Arm P, `run_vk.py`, menu walk with no race:
1. main menu → OPTIONS → PC SETTINGS;
2. DOWN×5 to Motion Blur, RIGHT, LEFT;
3. Back.

| Run | Exe | Result |
|---|---|---|
| Pp4 | e42c143e | Retail Options page. The hook ran but the loader saw `options`. HYPOTHESIS at the time, explained by Pp5/Pp6 |
| Pp5 | 25fe9310 | Hook log shows the path swapped to `gui/optionz.gui` (alias 1), yet the loader at 0x536A30 still read `options` and the retail page showed |
| Pp6 | 9531e520 | **VERIFIED** (details below). Stop reason `menu test done` at 79 s |

**Cause (VERIFIED):** `0x00752C98` is a TOC trampoline ending in `b 0x536A30`. Lifted, that tail branch only sets `g_trampoline_fn` and returns. The caller's `DRAIN_TRAMPOLINE` then runs the loader, which happens after the hook has already restored the path. Both hooks now drain it themselves (`pcmenu_drain`).

**Pp6 results (VERIFIED):**
- Both pages were served from the overlay:
  ```
  [vfs-overlay] .../USRDIR/gui/optionz.gui -> build/pcmenu/gui/optionz.gui
  [vfs-overlay] .../USRDIR/gui/options-pc.gui -> build/pcmenu/gui/options-pc.gui
  ```
- Screenshots show PC SETTINGS in the Options menu and the PC Settings page in the game's own style:
  - title, labels and values;
  - `< >` arrows on the focused row;
  - per-row info line, e.g. "Play in a window or fullscreen." and "The game's motion blur.".
- Focus moved row by row with DOWN.
- Motion Blur:
  - RIGHT → `[mspr-patch] on 0x0C (PC Settings)` and `[pc-menu] motionblur = Off`; the screen shows `< Off >`.
  - LEFT → `on 0x04`, `motionblur = On`.
- Back wrote `exe_r/settings.ini` (all defaults); deleted after the run.

## Not yet verified
- **Restart-only settings:** resolution, display, vsync, frame rate, filtering and textures, after a restart with a non-default `settings.ini`.
- **Options page edge cases:** Display Mode `<Windowed>` text sits close to its arrows. Language selection was not tested on a build where it is shown.
- **Live MSPR toggles in a race:** motion blur and dynamic resolution were not checked visually.

## 2026-11-13: five more pages, key rebinding, 1.03 hooks (static and unit-test only; NOT run in the game)

Labels: VERIFIED = unit tests or the offline generator; PARTIAL = matched by code shape only; NOT VERIFIED = needs the menu walk below.

### What changed
- Page set (page table `port-vkgame/pc_pages.h`, read by the generator): Options > **PC SETTINGS** opens a hub `options-pc` (the Options page's layout, five items) with
  | item | page file | rows |
  |---|---|---|
  | DISPLAY | `options-pcd` | Display Mode, Resolution, V-Sync, Dynamic Resolution, Frame Rate |
  | UPSCALING | `options-pcu` | Upscaler (FSR 1 / FSR 3.1), Upscaler Quality (Off, Ultra Quality, Quality, Balanced, Performance), HDR Output |
  | GRAPHICS | `options-pcg` | Motion Blur, Texture Filtering, HD Textures, PBR Materials, Ray-Traced Shadows |
  | DRIVING KEYS | `options-pck1` | Accelerate, Brake / Reverse, Steer Left, Steer Right, Handbrake, Boost / Accept, Square, Triangle |
  | BUTTON KEYS | `options-pck2` | Back / Circle, L1, R1, Pause / Start, Select |
- Key rows: Accept (the Cross key) makes the row show `Press a key...`; the next key pressed is bound (Esc cancels, 8 s with no key cancels); Left or Right resets the row. The keyboard presses nothing for the game while a capture runs. A key already used by another action is taken from it (it gets this action's old key if it would be left with none).
- Generator (moved to the public folder `tools/pcmenu/make_pcmenu.py` on 2026-11-13, with its five reader modules; `tools/audit_public.py --tree tools/pcmenu` passes): `py -3 tools/pcmenu/make_pcmenu.py --psarc <MS2.PSARC> --out <dir>` (or `--gui <dir>`); reproducible (two runs, identical bytes; the `--psarc` and `--gui` routes give identical bytes); writes `pcmenu.json`. Now eight pages: the hub (six items) and seven row pages, the third key page holding the arrows. 13 settings, 17 key actions.
- 1.03 hooks (PORT_V103): `tools/pcmenu_lifted_103.py` (dry run by default; `--apply` edits `generated/ppu-v103-staging/ppu_recomp_001.cpp` and `_002.cpp`): lookup `func_005604C8` (callers 0x00561DA4, 0x00564214) and the resource load `func_00503718` via the trampoline `func_0071C408`. PARTIAL: found by instruction shape against 1.02 `0x00594C10` and `0x00536A30`; the 666 (0x29A) constant is in the 1.03 lookup; the page loader that calls the trampoline was not located (it changed in 1.03), so the walk below checks it by log.

### Checked here
- `tools/build_tests.cmd`: `test_pc_settings` 0 failures, `test_pc_keys` 0 failures, `test_pad_keyboard_map` passed, mutation build fails as it must.
- `tools/syntax_pc_menu.cmd`: `pc_menu.cpp` compiles (syntax) for 1.03 (`-DPORT_V103=1` against `ppu-v103-staging`) and 1.02 (`ppu-t173-staging`).
- Generator: all eight pages re-walk clean (0 unrelocated pointers), 2026-11-13 final layout.
- Defaults changed on 2026-11-13 by the user's decision: upscaler FSR 3.1 by default (`RSX_FSR_MODE=3` is always set; FSR 1 when the DLLs are missing); keyboard layout W/Up, S/Down, A/Left, D/Right, Space, Ctrl, Q, E, C, Enter; Circle, L1, R1 unbound.

### Menu walk for the next run (do this after: `pcmenu_lifted_103.py --apply` with no build running in the staging folder, rebuild with PORT_V103=ON, `make_pcmenu.py --psarc ... --out <exe folder>/pcmenu`, delete or back up `settings.ini`)
1. Start the game, intro skip as usual, main menu. Expected log at start:
   - `[pc-menu] 175 functions at 0x2FF00000, options page from the overlay, dxc found|missing`
2. OPTIONS. Expected: `[pc-menu] resource load: gui/options.gui`, `[pc-menu] Options page: gui/optionz.gui`, and `[vfs-overlay] .../gui/optionz.gui -> .../pcmenu/gui/optionz.gui`. Screen: AUDIO, DISPLAY, CONTROLLER, PC SETTINGS. **If the retail page shows and there is no `resource load` line, the 1.03 page loader does not go through `func_0071C408`: report it, the hook site must be found.**
3. PC SETTINGS. Expected `[vfs-overlay] ... options-pc.gui`; the title "PC Settings", five items DISPLAY / UPSCALING / GRAPHICS / DRIVING KEYS / BUTTON KEYS with their info lines. If the items are empty: the 1.03 lookup hook does not run (no `Pc*` function answered).
4. Each page, Back returns to the hub. Left/Right on rows:
   - Display: `[pc-menu] resolution = 1080p`, `vsync = Off`, `display = Fullscreen`; the info shows "Restart the game to apply." after a change.
   - Upscaling: `fsr = Quality`, `fsrmode = FSR 3.1` (with the DLLs missing the value shows `FSR 3.1 (No FSR3 DLL)` and the log says `- not applied: No FSR3 DLL`), `hdr = On`.
   - Graphics: `motionblur = Off` (live: `[mspr-patch]` toggles), `aniso = 8x`, `textures = On` (`No pack` shown if `textures/pack` is missing), `rtshadow = On` shows `On (No DXC)` without DXC, `On (No RT GPU)` on a GPU without ray queries.
5. DRIVING KEYS, focus Accelerate, press the Cross key (Z): the value shows `Press a key...`, log `[pc-menu] key.accelerate: waiting for a key`. Press T: log `[pc-menu] key.accelerate = T (T)`, the value shows `T`. Press Left: log `key.accelerate = default`, value `W, 2`. Capture then Esc: `key.accelerate: cancelled`. Capture and bind Brake to W: log `key.brake = W (W), taken from key.accelerate`; Accelerate then shows its old key or the remaining one. Only while a capture runs the menu must not react to the keys.
6. Back out; `settings.ini` beside the exe has all 13 settings and 17 `key.*` lines. Restart: log lines `[pc-menu] settings.ini: ...` for the non-default ones and `[pc-menu] settings.ini: N key binding(s)`; in a race, T accelerates (with no XInput pad connected: the keyboard fallback is only used then).
7. Retail check: rename `pcmenu` away; the retail Options page shows and nothing else changes.
