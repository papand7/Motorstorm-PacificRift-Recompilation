# MotorStorm: Pacific Rift, PC

A native PC port of **MotorStorm: Pacific Rift** (PlayStation 3, 2008), built by recompiling the game's own code ahead
of time, with an upscaling pipeline and PC settings. For **Windows x64**. **Version 0.2.0, ALPHA.**

> [!WARNING]
> **ALPHA.** Expect crashes, graphical faults and missing features (see [Known issues](#known-issues)). Report what
> you see with the launcher's log.

> [!NOTE]
> **No game files are included.** The launcher runs only with your own copy of the game: your own disc image or
> disc folder and your own decrypted program file (`EBOOT.elf`) of version 1.00. The launcher never ships or
> decrypts game data.

## What it is

The PS3 game's PowerPC and Cell SPU code is translated ahead of time into C++ and built into a native Windows
program. The PS3 system calls the game makes are provided by an independently written compatibility layer, and the
RSX graphics commands are drawn with Direct3D 12 or Vulkan. The game's logic, physics and AI are the original code,
not approximations.

<table>
<tr><th>Original lighting, game's own shadows</th><th>Reflections on the sea and cars (Enhanced)</th></tr>
<tr><td><img src="docs/screenshots/race-original-lighting.png" alt="Race with the game's own shadows"></td><td><img src="docs/screenshots/race-reflections.png" alt="Race with screen-space reflections"></td></tr>
</table>

## What you need

- Windows 10 or 11, 64-bit, with a graphics card and driver that support Vulkan.
- Your own copy of the game (the US disc, BCUS98155): an `.iso` image, or a folder with `PS3_GAME` in it.
- Your own decrypted `EBOOT.elf` of version 1.00 (the disc's), made from your own console. No update is needed. The
  launcher checks the file by its SHA-256 and refuses anything that does not match.
- Free disk space for the tools, the build and the game files, and an internet connection for the first install.
  The launcher downloads its tools from their publishers, checks each download's SHA-256, and asks you to accept
  Microsoft's terms before it installs the Visual C++ and Windows SDK libraries.

## Install

1. Download `MotorStormPacificRift.exe` (a portable exe, nothing to unzip) from the
   [latest release](https://github.com/papand7/motorstorm-pacific-rift-native/releases/latest) into a folder of your own.
2. Run `MotorStormPacificRift.exe`.
3. Choose your disc and your 1.00 `EBOOT.elf`, and press **Install**. The launcher builds the game on your PC (the
   first build takes 30 to 90 minutes). It writes everything under a `MotorStorm\` folder beside the exe.
4. Press **Play** when the install is done.

The install's last steps run the game once briefly to capture an SPU code overlay, then make the in-game PC Settings
pages and the cockpit camera lists from your own game files. Install again after updating the launcher: the PC
Settings pages must match the new exe.

The launcher keeps a `launcher.log` with every command it ran and its output. Include it when you report a problem.

## Settings

The launcher's **Settings** page and the game's own **PC Settings** pages write to the same file, `play\settings.ini`.

| Setting | Choices (default first or marked) |
|---|---|
| Display | Windowed (default) or Fullscreen |
| Resolution | 720p (default), 1080p, 1440p, 2160p |
| Frame rate | **30 FPS** (default, the original speed); 45, 60 and higher are **experimental** |
| Vsync, dynamic resolution | Off by default |
| Upscaling | Off by default. Upscaler **FSR 1** (default) or **FSR 3.1** (AMD FidelityFX; needs AMD's two DLLs beside the exe, which the install puts there, otherwise FSR 1 runs) |
| HDR | Off (default) or On |
| Lighting | **Enhanced** (default, experimental: new lighting, ambient occlusion, screen-space reflections, tone mapping; the game's own shadows) or **Original** (the game's own lighting) |
| Level of detail | Original (default), High, Ultra: finer models and objects farther out, at more CPU and GPU time |
| Textures | **HD texture pack** (your own game's textures, upscaled on your PC) and **PBR materials** (needs a pack made with PBR maps); both Off by default |
| Motion blur, anisotropic filtering | On / Original by default |
| Button prompts | Keyboard (default), Controller or Auto: the game's button icons drawn as the keys you bound |
| Racing wheel | Auto (default), Any Device, Off; steering range, deadzone, curve, pedals, force feedback (off by default) |
| Keyboard bindings | All 13 actions, rebindable |

Every choice that needs a missing part (no FSR 3.1 DLLs, no HD pack) shows the reason on its page.

The launcher's **Cheats** tab has two switches, both off by default: **Unlock all vehicles** (every vehicle class and
ticket) and **Unlock all tracks** (the Free Play track list). They do not change your saves: turn one off and the game
is as before.

## Features

- **Native PC port:** the game's own code, compiled for Windows x64 ahead of time.
- **Upscaling:** FSR 1 and FSR 3.1 (AMD FidelityFX).
- **Enhanced lighting** (default, experimental): ambient occlusion (GTAO), screen-space reflections on water and car
  paint, and tone mapping. Both lighting models are in the game and can be switched at any time.
- **Level-of-detail** setting.
- **HD texture pack** and **PBR materials:** your game's textures upscaled on your PC, applied when the pack is in place.
- **PC Settings pages:** display, upscaling, graphics, racing wheel and keyboard settings in the game's own menus,
  generated from your copy's data on your PC.
- **Keyboard rebinding** for all 13 actions, and **PC key prompts:** the game's button icons show your keys.
- **Racing wheels:** Thrustmaster and Logitech wheels (and other DirectInput wheels with Any Device), beside a gamepad.
  The layouts are not yet checked on real hardware.
- **Cockpit view:** a driver's-eye camera, reached with Select (C) like the other cameras. The install bakes in tuned
  positions for one vehicle of each class; the others use per-class defaults. **Live tuning** while the cockpit view
  is on: I / K forward and back, J / L left and right, T / G up and down, `.` / `,` pitch, M / N turn, O / U zoom
  (Shift faster, Num0 finer); **F2** saves to `cockpit_positions.json` beside the game. The next Install keeps that
  file and uses it.
- **Cheats tab:** unlock all vehicles and the Free Play tracks.

## Known issues

- **60 FPS and above are experimental:** camera and shadow artefacts (and some vehicle glitches). 30 FPS is the
  default.
- **Water too bright** in some races (Enhanced lighting).
- **Shadows:** the world-fixed shadow tiles are not in this release (they do not yet draw shadows on the ground); the
  game's own shadows are used.
- **Button prompts:** the key-cap prompts are still being tested and may show the game's original icons.
- **Garage vehicle-edit screen** may be blank (a fix is pending).
- **Cheats:** Unlock all tracks covers the Free Play list only; the Festival and Time Trial lists are not unlocked.
- **Exposure spikes:** the picture can briefly flash too bright or too dark.

## Not in this release

- **Multiplayer:** no online or LAN play.
- **Gamepad rebinding:** key bindings are keyboard-only.

## Building

The launcher is an Electron app in `launcher/electron/`. Its unit tests run with `node test_settings.js`. `npm run dist`
builds the portable exe with the game's source snapshot (`source_bundles.js --with-pcmenu`: the port, the runtime's
working tree, the lifting recipe and the install's tools, audited by `tools/audit_public.py --tree`). See
[docs/LAUNCHER.md](docs/LAUNCHER.md).

## Status

| Part | State |
|---|---|
| Launcher window and settings | Alpha: unit-tested settings file |
| Install from your own files | Checked on the development PC (2026-11-23) from the release's source snapshot through the build step: source, shader compiler, translation with all PC hook patches, and the 1.00 build. The PC Settings and cockpit tools ran separately from the snapshot; the install step and the overlay capture (it starts the game) were not run in that check |
| Game in the port | Alpha: see Known issues |

Detailed records are in [docs/STATUS.md](docs/STATUS.md) and [docs/LAUNCHER.md](docs/LAUNCHER.md).

## Credits

- **ps3recomp** by sp00nznet, the static recompilation framework this port is built on (MIT). Pinned to the v0.15.0
  revision.
- **AMD FidelityFX** (FSR 1 and FSR 3.1), redistributed by the launcher's tool step with AMD's licence.
- **DXC** (Microsoft), a shader compiler the install places beside the game.
- **Electron**, **Clang/LLVM**, **CMake**, **Ninja**, **Python** and the Vulkan SDK components, each downloaded by the
  launcher from its publisher.

Third-party components and their licences: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## License

The launcher's package is marked MIT (`launcher/electron/package.json`). No root `LICENSE` file has been added to this
repository yet; the owner must confirm the project's licence before a public release. This project contains none of
MotorStorm's code or files: MotorStorm is the property of its owners, and this port is not affiliated with Sony
Interactive Entertainment or Evolution Studios.
