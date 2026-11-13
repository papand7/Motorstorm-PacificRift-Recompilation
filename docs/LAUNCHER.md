# Launcher (install from the player's own disc)

`launcher/` holds the Electron launcher for players. It builds the game on the player's PC from the player's own disc,
the 1.03 update and the player's own decrypted program files (EBOOT.elf), in the manner of the NightFire launcher: a
service (`launcher/electron/service/`, Node, JSON lines on stdin/stdout) does the work and the window draws its
progress.

**The launcher does not decrypt anything, contains no decryption code and no keys.** The player supplies the decrypted
`EBOOT.elf` of the disc (1.00) and of the 1.03 update, made from their own console. The launcher checks each file by
its SHA-256 (`launcher/game.json`), refuses a file that does not match, and uses it where it is. The file is never
copied out of the player's folder, stored in the launcher's source, committed, uploaded or sent anywhere. Nothing
decrypted, lifted or keyed is part of the launcher's source snapshot.

## What an install does

Everything the install makes goes under `MotorStorm\` beside the launcher exe:

| Step | What | Checked by |
|---|---|---|
| game | the disc (an `.iso` or a folder with `PS3_GAME`): its title, and the files the game reads; the 1.03 update folder (its `USRDIR\ms2patch.psarc`, the update's data, chosen by the player) | title id; size and SHA-256 of `ms2patch.psarc` (`game.json` `update.data`) |
| elf | the player's decrypted `EBOOT.elf` of 1.00 (the disc) and of 1.03 (the update), each chosen by the player. Read where they are; not copied, decrypted or stored | size and SHA-256 of each (`game.json` `eboot_elf`) |
| files | a disc image's files copied out to `game\` (a folder is read in place); the update's `PARAM.SFO` and `ms2patch.psarc` into `hdd0\game\BCUS98155\` (hard link when possible) | sizes |
| tools | Python 3.14.0 (embeddable; it also unpacks LLVM's `.tar.zst`, whose zstd window Windows' `tar.exe` refuses), Clang 23.1.3, CMake 4.3.1, Ninja 1.13.2, glslang/SPIRV-Tools/SPIRV-Headers/Vulkan-Headers sources (Vulkan SDK 1.4.341.0 tags), Microsoft C++ libraries 14.44 and Windows SDK 10.0.26100 (from the Visual Studio channel, after the player accepts Microsoft's terms) into `tools\`; and the run-time pieces (`toolchain.json` `runtime`): DXC 1.9.2609 (`dxc.exe`, `dxcompiler.dll`, `dxil.dll` and its licence files) and AMD's FSR 3.1 DLLs (FidelityFX SDK v2.4.0 `signedbin`) with AMD's licence | SHA-256 of every download (`launcher/toolchain.json`; Microsoft's from its manifest, whose listed sizes are not always the served ones, so only the hash is enforced there) |
| source | the launcher's source snapshot (`resources\source\motorstorm-source.tar`) into `work\src\` | `SOURCE.json` |
| glslang | glslang 16.2.0 with SPIRV-Tools built into `tools\vulkan-sdk` (Include\, Lib\ as the runtime's CMake expects of a LunarG SDK) | build result |
| lift | `pipeline/lift_motorstorm.py` on the two chosen ELFs: `find_functions.py`, `gen_imports.py`, `ppu_lifter.py --trace-hooks`, `mspr_patch_lifted.py`, the Wws_Job policy module (`spu_lifter.py`, cut from the 1.00 ELF at 0x00FFCC80: the 1.03 ELF has no segment there), the 31 Wws job modules of the 1.03 ELF (`lift_wws_reloc.py --ctor`) | SHA-256 of every output against `pipeline/manifest.json` |
| build | CMake + Ninja with the options of `generated/analysis/vksync/tools/build_vkgame_103.cmd` (`game.json` `build`) | the exe exists |
| install | the exe into `play\`, DXC into `play\dxc\`, the FSR 3.1 DLLs beside the exe, licences into `play\licenses\`, `play\play.json` (the paths of the two chosen ELFs, and the game's file root), `motorstorm.cfg` with `PS3_VFS_ROOT`, `PS3_HDD0_ROOT`, `PS3_VFS_OVERLAY` | |
| pcmenu | the in-game PC Settings pages: `make_pcmenu.py --psarc <game>\PS3_GAME\USRDIR\MS2.PSARC --out play\pcmenu --port <src>\port-vkgame`, after every install (the pages must match the exe). Made from the player's own data, never shipped. The tool is found at `MS_PCMENU_DIR`, `launcher.json` `pcmenuDir`, or `pcmenu-tool\` in the source snapshot (`source_bundles.js --with-pcmenu`). Missing or failing: a warning only; the game keeps its retail Options page and `settings.ini` still applies | `make_pcmenu.py` exit 0 (every page re-walked) |

Every step leaves a stamp in `work\`, so Install continues after a stop or a failure. `launcher.log` has every command
and its output. Play starts `play\MotorStormPacificRiftRecomp.exe <the player's 1.03 EBOOT.elf>` (named in `play\play.json`).

Why two ELFs: the 1.03 ELF has no code at the address of the Wws_Job policy module (checked: no PT_LOAD segment holds
0x00FFCC80+0x2D00 in `EBOOT_103.elf`), so the lift takes that module from the 1.00 ELF, as the verified 1.03 translation
does. Both are the player's own files.

## Settings

The Settings page writes `play\settings.ini`, the file the port and its in-game PC Settings page share
(`docs/SETTINGS.md`): every key of that page (display, resolution, vsync, dynres, framerate, fsrmode, fsr, hdr,
motionblur, aniso, textures, pbr, rtshadow) and the thirteen keyboard bindings, as choice labels, by a whole-file
read-modify-write through `settings.ini.tmp` (lines it does not know are kept). A choice whose feature is missing is
shown with the reason (no DXC, no FSR 3.1 DLLs, no HD pack). `motorstorm.cfg` keeps only paths and diagnostics. On first
load, an old launcher's `motorstorm.cfg` lines (`RSX_FSR`, `RSX_FSR_MODE`, `RSX_HDR`, `PS3RECOMP_VK_FULLSCREEN`,
`RSX_PRESENT_INTERVAL`, `RSX_TEX_PACK`, `RSX_TEX_PBR`) move into `settings.ini` once (`launcher/electron/settings.js`,
tests: `node launcher/electron/test_settings.js`). No RPCS3 path is stored in any settings file.

## Keys and decryption: what is and is not in the launcher

- The launcher's own code (`launcher/electron`, `launcher/pipeline`, `game.json`, `toolchain.json`) holds hashes, sizes,
  offsets and URLs only. No decryption code, no keys, no decrypted or lifted game data.
- The player's decrypted ELFs are their own files. The launcher reads them and never writes them into its source,
  its snapshot, its settings or any upload.
- **Open: the ps3recomp runtime carries upstream key tables.** Two of its source files (in the runtime's file-system
  library and its PPU runtime) and two of its developer tools hold upstream key material. `source_bundles.js` leaves
  the two tools (and their test) out of the snapshot. It still refuses to pack the runtime's two key files unless run
  with `--allow-runtime-keys`, so **no launcher containing them is packed until the owner removes those tables from the
  runtime or the launcher's build without them is tested.** Until then `source_bundles.js` does not produce a tar.
  The file names are kept out of this public document on purpose.

## Making the launcher (developers)

    cd launcher/electron
    node source_bundles.js [--allow-runtime-keys] [--with-pcmenu] [--runtime-worktree]
                                                     # build/launcher-source: staged, audited (tools/audit_public.py --tree), packed
                                                     # --runtime-worktree: ps3recomp-vkgame's tracked files as on disk (uncommitted changes)
    npm start                                        # the window; MotorStorm\ under launcher/dev
    npm run dist                                     # portable exe (carries game.json, toolchain.json, texpack.py, the source tar)
    npm run dist:public                              # portable exe for public release: game.json, toolchain.json only, no source tar,
                                                     # no texpack.py (the installer then stops: "carries no game source"); to build\release-0.1.0

`source_bundles.js` stages `port-vkgame/` (copied: it is not in git), `git archive HEAD` of `ps3recomp-vkgame` (only
committed changes; it warns when the working tree has others), and `launcher/pipeline/`. The service can be driven
from a terminal: `node launcher/electron/service/cli.js --root <dir> --disc <iso|folder> --update <folder> --elf100 <EBOOT.elf> --elf103 <EBOOT.elf> --agree --install [--until <step>]`.

`pipeline/manifest.json` holds only SHA-256s, offsets and sizes (no game bytes). Regenerate it after a lifter or
patch change with `lift_motorstorm.py --write-manifest` on private inputs.

The developer-only "Install from a built folder" (copies a build made elsewhere, which contains lifted game code)
shows only in an unpackaged launcher or with `MS_DEV_INSTALL=1`.

## Files removed with the RPCS3 step

- `launcher/electron/service/decrypt.js` (the RPCS3 call, its copy of the EBOOT and the RPCS3 update lookup).
- In the install: the `decrypt` step, the `rpcs3` choice and the stored `rpcs3.exe` path (`launcher.json`), the
  `rpcs3.exe` picker, the `--rpcs3` option of `cli.js`, and the `eboot_self` hashes in `game.json`.

## Status

See the 2026-11-13 launcher entries in `docs/STATUS.md`.
