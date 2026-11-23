# Launcher (install from the player's own disc)

`launcher/` holds the Electron launcher for players. It builds the game on the player's PC from the player's own disc and
the player's own decrypted program file (EBOOT.elf), in the manner of the NightFire launcher: a service
(`launcher/electron/service/`, Node, JSON lines on stdin/stdout) does the work and the window draws its progress.

**Supported build: MotorStorm 1.00 (Stable).**

**The launcher does not decrypt anything, contains no decryption code and no keys.** The player supplies the decrypted
`EBOOT.elf` of the disc (1.00), made from their own console. The launcher checks the file by
its SHA-256 (`launcher/game.json`), refuses a file that does not match, and uses it where it is. The file is never
copied out of the player's folder, stored in the launcher's source, committed, uploaded or sent anywhere. Nothing
decrypted, lifted or keyed is part of the launcher's source snapshot.

## What an install does

Everything the install makes goes under `MotorStorm\` beside the launcher exe:

| Step | What | Checked by |
|---|---|---|
| game | the disc (an `.iso` or a folder with `PS3_GAME`): its title, and the files the game reads | title id |
| elf | the player's decrypted `EBOOT.elf` of 1.00, chosen by the player, read where it is, and never copied, decrypted or stored | size and SHA-256 (`game.json` `discs[].eboot_elf`) |
| files | a disc image's files copied out to `game\` (a folder is read in place) | sizes |
| tools | Python 3.14.0 (embeddable; it also unpacks LLVM's `.tar.zst`, whose zstd window Windows' `tar.exe` refuses), Clang 23.1.3, CMake 4.3.1, Ninja 1.13.2, glslang/SPIRV-Tools/SPIRV-Headers/Vulkan-Headers sources (Vulkan SDK 1.4.341.0 tags), Microsoft C++ libraries 14.44 and Windows SDK 10.0.26100 (from the Visual Studio channel, after the player accepts Microsoft's terms) into `tools\`; and the run-time pieces (`toolchain.json` `runtime`): DXC 1.9.2609 (`dxc.exe`, `dxcompiler.dll`, `dxil.dll` and its licence files) and AMD's FSR 3.1 DLLs (FidelityFX SDK v2.4.0 `signedbin`) with AMD's licence | SHA-256 of every download (`launcher/toolchain.json`; Microsoft's from its manifest, whose listed sizes are not always the served ones, so only the hash is enforced there) |
| source | the launcher's source snapshot (`resources\source\motorstorm-source.tar`) into `work\src\` | `SOURCE.json` |
| glslang | glslang 16.2.0 with SPIRV-Tools built into `tools\vulkan-sdk` (Include\, Lib\ as the runtime's CMake expects of a LunarG SDK) | build result |
| lift | `pipeline/lift_motorstorm.py`: the 1.00 PPU lift (`ppu_loader.py`, `ppu_lifter.py --trace-hooks`, `mspr_patch_lifted.py`, then the hook patches `PATCHES_100`: `slice_patch_lifted.py`, `cam_patch_lifted.py`, `dist_patch_lifted.py`, `unlockall_lifted.py`, `pcmenu_lifted.py`, `cockpit_tune_patch_ppucc.py`), the Wws_Job policy module (`spu_lifter.py`, cut from the 1.00 ELF at 0x00FFCC80), and the relocatable Wws job modules (`lift_wws_reloc.py --ctor`) | SHA-256 of every output against `pipeline/manifest.json` |
| build | CMake + Ninja in `work\build-stable` with the options of `game.json` `builds.stable` (includes `PORT_EXPECT_ENTRY_OPD=0x107B8D8`, the 1.00 entry check, so a wrong ELF is refused before guest code runs) | exe exists |
| install | the exe as `play\MotorStormPacificRiftRecomp.exe`; DXC into `play\dxc\`, the FSR 3.1 DLLs beside the exe, licences into `play\licenses\`; `play\play.json` (the exe, the player's ELF it runs, and its start environment); `motorstorm.cfg` with `PS3_VFS_ROOT` only | |
| pcmenu | the in-game PC Settings pages: `make_pcmenu.py --psarc <game>\PS3_GAME\USRDIR\MS2.PSARC --out play\pcmenu --port <src>\port-vkgame`, after every install (the pages must match the exe). Made from the player's own data, never shipped. The tool is found at `MS_PCMENU_DIR`, `launcher.json` `pcmenuDir`, or `pcmenu-tool\` in the source snapshot (`source_bundles.js --with-pcmenu`). Missing or failing: a warning only; the game keeps its retail Options page and `settings.ini` still applies | `make_pcmenu.py` exit 0 (every page re-walked) |
| overlays | runs the installed exe once (up to 2 minutes) with `SPU_DUMP_OVL` to capture the SPU overlay, lifts it with `<src>\tools\build_spu_overlay.py --lifter-arg=--chain-chunks` (its lifter: `<src>\ps3recomp\tools`) and rebuilds with `MSPR_OVL_CHAIN=ON`. Soft failure: the game runs without it | overlay SHA-256 |
| cockpit | `cockpit-tool\make_cockpit_overlay.py --psarc <MS2.PSARC> --out play\pcmenu --positions work\cockpit_positions.json`: the cockpit camera lists, from the player's data, never shipped. The positions are the shipped `cockpit_positions.default.json` (camera offsets only) with the player's `play\cockpit_positions.json` (written by F2 in the game) on top; the player's file is only read | exit 0 |

Every step leaves a stamp in `work\`, so Install continues after a stop or a failure. `launcher.log` has every command
and its output.

## Collect all textures

The **Collect all textures** button on the HD Textures page saves every texture of the game without playing a single
race (the old "Start collecting" is now "Collect while playing", the fallback for textures built at run time). The
launcher runs `texcollect.py --play <play folder> --game <the game files folder>` with its own Python (the tool uses
the standard library only; it is in the packaged launcher's `tools\texcollect` and in the source snapshot as
`texcollect-tool`), shows its output, and the totals stay in the page's log. It prints no progress while it works
(about 75 s). "Make the HD pack" then reads the same dump; the full set takes many hours (about 9 s per texture at 2x
on the test PC), so 2x is the default and 4x is offered only for a smaller set. It runs `tools/texcollect/texcollect.py` on the player's own
`MS2.PSARC`: it reads the archive directly (the game does not start), finds every texture resource (resource type 5
of the `.rpk` and `.gui` packs: DXT1, DXT3, DXT5 and A8R8G8B8, with their mip chains), and writes level 0 of each as
`<w>x<h>_<rsx format>_<hash>.dds` into `<play>\textures\dump`. The key is the one the engine computes when it uploads
the texture (a word-wise FNV-1a over the whole mip chain as the game stores it), so the files are the same ones the
in-game dump (`RSX_TEX_DUMP`) writes and the pack lookup (`RSX_TEX_PACK`) finds. The existing **Make the HD pack**
upscaler reads this folder as it always did, so the dump can be made first and the pack built from it, or topped up
by playing with the dump on.

On the test machine it finds 5,974 distinct textures in about 70 s and reproduces 367 of the 372 files a played
session had dumped, byte for byte (98.7 percent). It cannot reach textures the game builds at run time (a few
128x128 and 64x64 DXT5 images, and the Bink video frames); those still arrive through the in-game dump. Cube maps,
volume textures, one-channel and two-channel formats and sides under 16 texels are not collected, as the engine's
dump does not write them either. The dump is derived from the game's data: it stays on the player's PC and is never
shared or uploaded.

## Shader cache (planned launcher step, "warm")

The pre-race warm-up (5 to 24 s) is mostly glslang turning the game's RSX programs into SPIR-V. The port keeps those
translations on disk when `PS3RECOMP_SPIRV_CACHE` is set. `PS3RECOMP_SPIRV_CACHE=auto` uses `shader_cache\` beside the
exe (created on first use); any other value is an existing folder. One `.spv` file per shader, named by the FNV-1a hash
of stage + generated HLSL; the file stores the full key and is a miss if the key, the glslang version or the exe's
translator build stamp differs. So a rebuilt exe (or a Reinstall) starts cold, and the cache must be filled by the exe
that will play. The Vulkan pipeline cache (`rsx_vk_pipeline.cache`, `RSX_VK_PIPELINE_CACHE`) is separate and is
driver-specific.

Launcher step text: "Preparing shaders: the game is started once in the background with
`PS3RECOMP_SPIRV_CACHE=auto`, through its loading screens and a race start, then closed. This makes the first race
start faster. It can be skipped; the cache also fills as you play." Set the same variable in `play\play.json`'s start
environment for every normal Play so later runs reuse and extend it. The folder is removed by Uninstall and by any
exe rebuild.

The cache is derived from the game's programs. It must never be committed, shipped, uploaded or put in a release or
public CI artifact (`tools/audit_public.py` must keep refusing `shader_cache\` and `*.spv`). It stays on the player's PC.

Not verified: that a warm run removes the pre-race compile. That needs a game run (compare `[vk-compile]
translations=` and `disk_hits=` on a second run).

## Build

Play starts `play\MotorStormPacificRiftRecomp.exe` with the player's 1.00 EBOOT.elf and the disc's files. The build has
the fail-fast entry check (`PORT_EXPECT_ENTRY_OPD`): it refuses any ELF whose entry OPD is not 0x107B8D8 before guest
code runs. The PC Settings pages (`pcmenu`) are made from the disc's `MS2.PSARC`.

## Settings

The Settings page writes `play\settings.ini`, the file the port and its in-game PC Settings page share
(`docs/SETTINGS.md`): every key of that page (display, resolution, vsync, dynres, framerate, fsrmode, fsr, hdr,
motionblur, aniso, textures, pbr, lod, lighting, prompts, the wheel rows; the Cheats tab's unlockvehicles and
unlocktracks) and the thirteen keyboard bindings, as choice labels, by a whole-file
read-modify-write through `settings.ini.tmp` (lines it does not know are kept). A choice whose feature is missing is
shown with the reason (no FSR 3.1 DLLs, no HD pack). `motorstorm.cfg` keeps only paths and diagnostics. On first
load, an old launcher's `motorstorm.cfg` lines (`RSX_FSR`, `RSX_FSR_MODE`, `RSX_HDR`, `PS3RECOMP_VK_FULLSCREEN`,
`RSX_PRESENT_INTERVAL`, `RSX_TEX_PACK`, `RSX_TEX_PBR`) move into `settings.ini` once (`launcher/electron/settings.js`,
tests: `node launcher/electron/test_settings.js`). No RPCS3 path is stored in any settings file.

## Keys and decryption: what is and is not in the launcher

- The launcher's own code (`launcher/electron`, `launcher/pipeline`, `game.json`, `toolchain.json`) holds hashes, sizes,
  offsets and URLs only. No decryption code, no keys, no decrypted or lifted game data.
- The player's decrypted ELFs are their own files. The launcher reads them and never writes them into its source,
  its snapshot, its settings or any upload.
- **The ps3recomp runtime's upstream key tables.** Two of its source files (in the runtime's file-system
  library and its PPU runtime) and two of its developer tools hold upstream key material. `source_bundles.js` leaves
  the two tools (and their test) out of the snapshot. It still refuses to pack the runtime's two key files unless run
  with `--allow-runtime-keys`, so no launcher containing them is packed by accident. On 2026-11-23 the key scan found none in the
  runtime's working tree (`SOURCE.json` `runtime_key_files: []`), and the tar is packed.
  The file names are kept out of this public document on purpose.

## Making the launcher (developers)

    cd launcher/electron
    node source_bundles.js [--allow-runtime-keys] [--with-pcmenu] [--runtime-head] [--dev] [--stage-only]
                                                     # build/launcher-source: staged, audited (tools/audit_public.py --tree), packed
                                                     # default: ps3recomp-vkgame's working tree (git ls-files -co --exclude-standard)
                                                     # --runtime-head: its committed tree only (git archive HEAD)
                                                     # --dev: for `npm start` (reads build/launcher-source); packs even with key tables, SOURCE.json says dev_only
                                                     # --stage-only: no tar; SOURCE.json says stage_only and an old tar is removed
    npm start                                        # the window; MotorStorm\ under launcher/dev
    npm run dist                                     # source_bundles.js --with-pcmenu, then the portable exe (game.json, toolchain.json, texpack.py, the source tar)
    npm run dist:public                              # portable exe for public release: game.json, toolchain.json only, no source tar,
                                                     # no texpack.py (the installer then stops: "carries no game source"); to build\release-0.2.0

`source_bundles.js` stages `port-vkgame/` (copied: it is not in git), `ps3recomp-vkgame`'s working tree (tracked and
untracked non-ignored files, as on disk; build and generated folders left out), `launcher/pipeline/`, `tools/`
(`build_spu_overlay.py`), `cockpit-tool/` (`tools/cockpit`), `texcollect-tool/` and, with `--with-pcmenu`,
`pcmenu-tool/`. It refuses to pack when `tools/audit_public.py --tree`, the include check (every quoted include of the
port and runtime resolves in the bundle) or the key scan fails. The service can be driven
from a terminal: `node launcher/electron/service/cli.js --root <dir> --disc <iso|folder> --elf100 <EBOOT.elf> --agree --install [--until <step>]`.

The install's source step compares the tar's own SHA-256 with `SOURCE.json`'s `tar_sha256` and refuses a snapshot that does
not match (or a stage-only one); it unpacks again, after removing `work\src`, whenever the tar differs from the one unpacked
(`work\src\SOURCE.sha256`). A new snapshot is therefore always picked up.

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
