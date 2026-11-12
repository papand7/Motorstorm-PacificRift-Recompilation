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
