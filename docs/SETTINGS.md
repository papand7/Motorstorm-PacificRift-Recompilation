# Player settings: one file, `settings.ini`

For the launcher, the in-game PC Settings pages and the port (`port-vkgame/pc_settings.h`, `pc_keys.h`, `pc_pages.h`, `pc_menu.cpp`, `main.cpp`). Contains no game data. Status of every claim below: see the end.

## The file

`settings.ini` sits beside the game exe (the launcher's `MotorStorm` folder). Plain text, one `key = choice` per line, `#` or `;` for comments, any case, spaces around `=` ignored, CRLF fine. A choice is its label (`1080p`, `Ultra Quality`) or its value (`1.5`, `ultra`). Unknown keys, unknown choices and unreadable lines are ignored, so a newer file loads in an older exe. A key that is missing means "the default".

The port **owns** the file: the in-game page rewrites all of it on every change (comments and unknown lines are dropped). Anything else that writes it must read it, change the keys it knows and write the whole file back (write `settings.ini.tmp`, then rename over it).

| key | page | choices (default marked *) | what it drives |
|---|---|---|---|
| `display` | Display | Windowed*, Fullscreen | `PS3RECOMP_VK_FULLSCREEN` 0 / 1 |
| `resolution` | Display | 720p*, 1080p, 1440p, 2160p | `RSX_RES_SCALE` 1, 1.5, 2, 3 |
| `vsync` | Display | On* (1), Off (0) | `RSX_PRESENT_INTERVAL` |
| `dynres` | Display | On, Off* | MSPR patch `drs` when Off (the game's own resolution drops are suppressed) |
| `framerate` | Display | 30 FPS, 60 FPS, Variable* | MSPR patch `60fps` / `vfps` |
| `fsrmode` | Upscaling | FSR 1, FSR 3.1* | `RSX_FSR_MODE` 1 / 3. **Always set**, also at the default (see below) |
| `fsr` | Upscaling | Off*, Ultra Quality, Quality, Balanced, Performance | `RSX_FSR` off / ultra / quality / balanced / performance |
| `hdr` | Upscaling | Off*, On | `RSX_HDR` 0 / 1 |
| `motionblur` | Graphics | On*, Off | MSPR patch `mblur` when Off |
| `aniso` | Graphics | Original*, 2x, 4x, 8x, 16x | `PS3_ANISO` |
| `textures` | Graphics | Off*, On | `RSX_TEX_PACK` = `<exe folder>/textures/pack` (not applied when that folder is missing) |
| `pbr` | Graphics | Off*, On | `RSX_TEX_PBR` = 1 (needs a pack with PBR maps) |
| `rtshadow` | Graphics | Off*, On | `RSX_RT_SHADOW` = 1 (not applied without DXC; the backend turns it off itself on a GPU without ray queries) |

**Upscaler mode (`fsrmode`)** is the one setting that sets its variable at its default too. The default is FSR 3.1, which the port's own default (FSR 1) does not give, so the exe sets `RSX_FSR_MODE=3` unless the choice is unavailable. FSR 3.1 needs AMD's two DLLs beside the exe; without them the choice is not applied and the port runs FSR 1 (the page shows "FSR 3.1 (No FSR3 DLL)"). The mode only matters when `fsr` is not Off.

## Key bindings

Keyboard only (the keyboard fallback, used when no XInput pad is plugged into port 0). Gamepad rebinding is not in the alpha.

Format: `key.<action> = <key>[, <key>]`, up to two keys. Key names: letters, digits, `F1`..`F24`, `Num0`..`Num9`, or `Space Enter Tab Ctrl Shift Backspace Left Right Up Down Insert Delete Home End PageUp PageDown CapsLock Pause NumLock ScrollLock NumPlus NumMinus NumMultiply NumDivide NumDecimal Semicolon Equals Comma Minus Period Slash Backquote LBracket Backslash RBracket Quote`; `0xNN` (a Windows virtual-key code); or `none`. Esc, Alt, the Windows keys and mouse buttons cannot be bound. `Ctrl` is either Ctrl key.

**Default keys** (`pad_kb_layout_default` in `ps3recomp-vkgame/libs/input/pad_keyboard_map.h`; unit-tested):

| action (`key.`) | page | default | | action (`key.`) | page | default |
|---|---|---|---|---|---|---|
| `accelerate` | Driving | W, Up | | `start` | Buttons | Enter |
| `brake` | Driving | S, Down | | `select` | Buttons | C |
| `steerleft` | Driving | A, Left | | `up` | Arrows | Up |
| `steerright` | Driving | D, Right | | `down` | Arrows | Down |
| `handbrake` | Driving | Space | | `left` | Arrows | Left |
| `cross` (boost, accept) | Driving | Ctrl | | `right` | Arrows | Right |
| `square` | Driving | Q | | `circle` (back in menus) | Buttons | **none** |
| `triangle` | Driving | E | | `l1` | Buttons | **none** |
| | | | | `r1` | Buttons | **none** |

Actions with no default key: `circle`, `l1`, `r1`. The launcher and the page show them as "none". Consequence: in menus Back (Circle) has no key until the player binds one.

`up/down/left/right` are the menu movement and the d-pad; Up and Down are also accelerate and brake, and Left and Right also steer. A key can belong to two actions on purpose (shared defaults); a rebind removes the key from the other action, and a reset keeps shared defaults on both.

## Precedence (strongest first)

1. The process environment (the test runners, a shell). Any variable already set wins.
2. `settings.ini`. For a key the file names, the variable it drives is set from the file (unless step 1 set it), **and a line for that variable in `motorstorm.cfg` is ignored**. A key at its default sets nothing, except `fsrmode` (see above), so the port's own default applies.
3. `motorstorm.cfg` (`NAME=value`, written by the launcher): for variables **no settings.ini key covers** only: `PS3_VFS_ROOT`, `RSX_TEX_DUMP`, `RSX_RT_DXC`, `RSX_FSR3_DIR`, diagnostics. A cfg line for a variable the ini names (e.g. `RSX_FSR=quality`) is ignored once `settings.ini` has the matching key, which the in-game page writes in full on its first save.
4. The port's built-in defaults (`main.cpp` `k_defaults`).

Why: the player must not have two files that disagree. The old launcher wrote `RSX_FSR=...` into `motorstorm.cfg`; the in-game page wrote `settings.ini`. Now both write `settings.ini`; `motorstorm.cfg` keeps paths and diagnostics only.

Migration: if `settings.ini` does not exist, the launcher creates it from the old cfg lines (`RSX_FSR`, `RSX_FSR_MODE`, `RSX_HDR`, `PS3RECOMP_VK_FULLSCREEN`, `RSX_PRESENT_INTERVAL`, `RSX_TEX_PACK` set = `textures = On`, `RSX_TEX_PBR=1` = `pbr = On`) and deletes those lines from the cfg.

## Availability

A choice whose feature is missing is kept in the file but not applied, and the page shows the reason next to it ("On (No RT GPU)"):

| choice | missing when | page text |
|---|---|---|
| `textures = On`, `pbr = On` | `<exe>/textures/pack` (or `RSX_TEX_PACK`) is not a folder | No pack |
| `rtshadow = On` | no `dxc.exe` found (see below) | No DXC |
| `rtshadow = On` | the GPU lacks VK_KHR_acceleration_structure / ray_query / deferred_host_operations or Vulkan 1.2 (`rsx_vk_rt_supported()`, known once the backend is up, so only the page can show it, not boot) | No RT GPU |
| `fsrmode = FSR 3.1` (the default) | `amd_fidelityfx_loader_vk.dll` not beside the exe (or in `RSX_FSR3_DIR`); the port then runs FSR 1 | No FSR3 DLL |

DXC lookup (`pcmenu_find_dxc`): `RSX_RT_DXC` if set, else `<exe>/dxc/dxc.exe`, else `<exe>/dxc.exe`, else `dxc.exe` on `PATH`. The port sets `RSX_RT_DXC` to what it found. The backend compiles shader variants with it in the background (cache in `%TEMP%\ps3recomp_rt` or `RSX_RT_DXC_CACHE`; the first session after enabling shows the non-RT shadows while they compile, the next session has RT).

## What the launcher does

The launcher (`launcher/electron`, see `docs/LAUNCHER.md`) does not decrypt anything and holds no keys. Its settings
are the ones below, written as labels; the decrypted program files (EBOOT.elf) the install needs are the player's own,
chosen by them, checked by hash and never copied into `settings.ini` or anywhere else.

Status of the items, as the launcher has them now:

1. **Write `settings.ini`, not `motorstorm.cfg`, for every key in the table above** (read-modify-write, whole file, tmp + rename; the launcher's `SETTINGS` object maps: `RSX_FSR` -> `fsr`, `RSX_FSR_MODE` -> `fsrmode`, `RSX_HDR` -> `hdr`, `PS3RECOMP_VK_FULLSCREEN` -> `display`, `RSX_PRESENT_INTERVAL` -> `vsync`, `HD_TEXTURES` -> `textures`, `PBR` -> `pbr`). Labels in the file are the choice labels above, not the numbers. Keep writing `PS3_VFS_ROOT` etc. to `motorstorm.cfg`. The launcher's FSR default becomes `fsrmode = FSR 3.1` (it was 3.1 before too).
2. Done: the launcher's Settings page has `resolution`, `dynres`, `framerate`, `motionblur`, `aniso`, `rtshadow` and the thirteen key bindings (`key.<action>`), written to `settings.ini` in the same format. The in-game page remains an equal editor of the same file.
3. **Ship the pinned DXC** (Microsoft DirectXShaderCompiler release zip; the files from `bin/x64`: `dxc.exe`, `dxcompiler.dll`, `dxil.dll`) into `<MotorStorm folder>/dxc/`, like the other toolchain pieces, and show Ray-Traced Shadows as "needs DXC" until it is there. Pin the release and its sha256 in the launcher. DXC is LLVM-licensed (Apache-2.0 with LLVM exceptions): add it to `THIRD_PARTY_LICENSES.md`.
4. Ship AMD's FSR 3.1 runtime (`amd_fidelityfx_loader_vk.dll`, `amd_fidelityfx_upscaler_vk.dll`) beside the exe (already planned for FSR 3.1).
5. **Generate the PC Settings pages on the player's PC** (never ship them). Tool: **`tools/pcmenu/make_pcmenu.py`** (public source; its five reader modules `page.py actions.py widgets.py coverage.py pack.py` sit in the same folder, no other dependency). Run after install and after every game or exe update:
   `py -3 tools/pcmenu/make_pcmenu.py --psarc <game>/PS3_GAME/USRDIR/MS2.PSARC --out <MotorStorm folder>/pcmenu`
   - Inputs: the retail pages `/gui/options.gui` and `/gui/options-controls.gui`, extracted from `MS2.PSARC` by the tool itself (archive table of contents and two members); and `port-vkgame/pc_pages.h` and `pc_settings.h` (the page table and the setting count; pass `--port <folder>` if the launcher ships them elsewhere). Alternative input: `--gui <folder>` with the two extracted pages.
   - Outputs: `pcmenu/gui/{optionz,options-pc,options-pcd,options-pcu,options-pcg,options-pck1,options-pck2,options-pck3}.gui` and `pcmenu/pcmenu.json` (the hashes of inputs and outputs). The pages are game data: the output stays on the player's PC.
   - Regenerate when the exe, `pc_pages.h`, `pc_settings.h` or the tool changes (`pcmenu.json` says which).
   - Exit code 0 means every page re-walked clean. If the folder is missing the game shows the retail Options page and `settings.ini` still applies.
   - Needs Python 3. `--psarc` needs nothing from the game but that one file.
6. The exe finds `pcmenu` beside itself (or `PS3_VFS_OVERLAY`). Never put `pcmenu/` into a release or CI artefact: it is made from game data. `tools/audit_public.py --tree tools/pcmenu` passes for the tool itself; run it again before each release.

## Status of the claims

- VERIFIED (unit tests, `generated/analysis/pcmenu/tools/build_tests.cmd`; 0 failures; the mutation build fails as it must): parsing, writing, precedence and ownership rules, the upscaler default and its FSR 1 fallback, availability skipping, key parsing and format, the default key set above, rebinding, conflicts, shared defaults and reset, the key-capture state machine, the page table (every setting and key row on exactly one page).
- VERIFIED (offline generator, `tools/pcmenu/make_pcmenu.py`, 2026-11-13): eight pages from the retail pages, all re-walked clean (0 unrelocated pointers); the `--psarc` and `--gui` routes give identical bytes.
- VERIFIED (syntax only): `pc_menu.cpp` compiles for 1.02 and 1.03 (`syntax_pc_menu.cmd`). Not linked, not run.
- PARTIAL: the two 1.03 hook sites were found by instruction shape against the 1.02 functions (lookup: callers 0x00561DA4 and 0x00564214, the 666 "no such function" constant is in it; resource load: `func_00503718`). Not run. `pcmenu_lifted_103.py` not applied.
- NOT VERIFIED in the running game: that the generated pages load, that the rows react, that a key capture works with the real keyboard, MSPR live toggles, settings after a restart, RT and FSR availability text, the default keys in play. See `generated/analysis/pcmenu/RESULTS.md` for the walk to do.
