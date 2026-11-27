# Launcher (install from the player's own disc)

`launcher/` holds the Electron launcher for players. It builds the game on the player's PC from the player's own disc and
the player's own decrypted program file (EBOOT.elf), in the manner of the NightFire launcher: a service
(`launcher/electron/service/`, Node, JSON lines on stdin/stdout) does the work and the window draws its progress.

**Supported build: MotorStorm 1.00 (Stable).**

**The launcher contains no decryption code and no keys.** The player supplies the decrypted
`EBOOT.elf` of the disc (1.00), made from their own console, or asks the launcher to make it with RPCS3 ("Decrypt
automatically", below: RPCS3 is downloaded at the player's request, used once and deleted). The launcher checks the file by
its SHA-256 (`launcher/game.json`), refuses a file that does not match, and uses it where it is. The file is never
copied out of the player's folder, stored in the launcher's source, committed, uploaded or sent anywhere. Nothing
decrypted, lifted or keyed is part of the launcher's source snapshot.

## What an install does

Everything the install makes goes under `MotorStorm\` beside the launcher exe:

| Step | What | Checked by |
|---|---|---|
| game | the disc (an `.iso` or a folder with `PS3_GAME`): its title, and the files the game reads | title id |
| elf | the player's decrypted `EBOOT.elf` of 1.00, chosen by the player and read where it is (or made by "Decrypt automatically" into `decrypted\EBOOT.elf`) | size and SHA-256 (`game.json` `discs[].eboot_elf`) |
| files | a disc image's files copied out to `game\` (a folder is read in place) | sizes |
| tools | Python 3.14.0 (embeddable; it also unpacks LLVM's `.tar.zst`, whose zstd window Windows' `tar.exe` refuses), Clang 23.1.3, CMake 4.3.1, Ninja 1.13.2, glslang/SPIRV-Tools/SPIRV-Headers/Vulkan-Headers sources (Vulkan SDK 1.4.341.0 tags), Microsoft C++ libraries 14.44 and Windows SDK 10.0.26100 (from the Visual Studio channel, after the player accepts Microsoft's terms) into `tools\`; and the run-time pieces (`toolchain.json` `runtime`): DXC 1.9.2609 (`dxc.exe`, `dxcompiler.dll`, `dxil.dll` and its licence files) and AMD's FSR 3.1 DLLs (FidelityFX SDK v2.4.0 `signedbin`) with AMD's licence | SHA-256 of every download (`launcher/toolchain.json`; Microsoft's from its manifest, whose listed sizes are not always the served ones, so only the hash is enforced there) |
| source | the launcher's source snapshot (`resources\source\motorstorm-source.tar`) into `work\src\` | `SOURCE.json` |
| glslang | glslang 16.2.0 with SPIRV-Tools built into `tools\vulkan-sdk` (Include\, Lib\ as the runtime's CMake expects of a LunarG SDK) | build result |
| lift | `pipeline/lift_motorstorm.py`: the 1.00 PPU lift (`ppu_loader.py`, `ppu_lifter.py --trace-hooks`, `mspr_patch_lifted.py`, then the hook patches `PATCHES_100`: `slice_patch_lifted.py`, `cam_patch_lifted.py`, `dist_patch_lifted.py`, `unlockall_lifted.py`, `pcmenu_lifted.py`, `cockpit_tune_patch_ppucc.py`, `fly_pause_patch_lifted.py`, `screens_patch_lifted.py`, `bench_patch_lifted.py`), the Wws_Job policy module (`spu_lifter.py`, cut from the 1.00 ELF at 0x00FFCC80), and the relocatable Wws job modules (`lift_wws_reloc.py --ctor`) | SHA-256 of every output against `pipeline/manifest.json` |
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
launcher runs `texcollect.py --play <play folder> --game <the game files folder>` with its own Python and the pinned
numpy (its A8R8G8B8 textures need it: see "What the HD textures page installs" below; the tool is in the packaged launcher's `tools\texcollect` and in the source snapshot as
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

## What the HD textures page installs

`texpack.py` ("Make the HD pack") imports numpy and Pillow and runs Real-ESRGAN; `texcollect.py` ("Collect all
textures") needs numpy for its A8R8G8B8 textures (without it, it stopped there). These are the only third-party
modules of any Python the launcher runs: the lift (`lift_motorstorm.py` and the ps3recomp tools it calls), the
overlays step, `make_pcmenu.py`, `make_cockpit_overlay.py`, `untar_zst.py` and the build's CMake scripts use the
standard library only (checked with `generated/analysis/texpack_deps/tools/find_missing.py`). The launcher used to
run the texture scripts in its Python without these packages, so on a new PC the pack stopped at `import numpy`; on
the developer PC the embedded Python had silently picked them up from the user's own
`%APPDATA%\Python\Python314\site-packages`. Real-ESRGAN was never fetched either: `texpack.py`'s default path only
exists in the developer tree.

The first time either button is used, the launcher fetches what it lacks (`service/texdeps.js`, `toolchain.json`
`textures`), each through the same pinned download as the build tools (SHA-256 and size checked, unpacked into
`MotorStorm\tools\<id>`, stamped):

| Tool | What | Where |
|---|---|---|
| `python` | Python 3.14.0 embeddable (the toolchain's own entry, if the install has not fetched it yet) | `tools\python` |
| `pydeps` | numpy 2.5.4 and Pillow 13.0.0: PyPI's `cp314-cp314-win_amd64` wheels, SHA-256 as PyPI lists them. A wheel is a zip, so they are unpacked with `tar.exe`; no pip | `tools\pydeps` |
| `realesrgan` | Real-ESRGAN ncnn Vulkan 0.2.5.0 (`realesrgan-ncnn-vulkan-20220424-windows.zip`: the exe, its OpenMP DLLs and the models) | `tools\realesrgan` |
| `realesrgan-license` | its BSD-3-Clause `LICENSE` at tag v0.2.5.0 | `tools\realesrgan-license` |

About 75 MB in all ("Collect all textures" needs only the first two). The scripts then run with
`PYTHONPATH=tools\pydeps`, `PYTHONNOUSERSITE=1` and no `PYTHONHOME`, and `texpack.py` gets
`--esrgan tools\realesrgan\realesrgan-ncnn-vulkan.exe`. The embedded Python's `python314._pth` stays deleted (the
install removes it so the lifter finds its modules beside its scripts); `PYTHONPATH` is what makes the packages
importable. After a fresh install the launcher imports `numpy, PIL` once as a check. A tool whose stamp matches (and,
for the wheels, whose `.dist-info` folders are there) is skipped, so later runs need no network. With no network on
the first run the page says `Could not download <tool>: no connection to the internet (...). It is needed once;
connect and try again.`; a wrong SHA-256 deletes the file and names both hashes. Stop also cancels the download.
Nothing goes into a system Python or Windows.

The build's own environment (`tools.buildEnv`) now also sets `PYTHONNOUSERSITE=1` and drops `PYTHONHOME` and
`PYTHONPATH`, so a user's site-packages cannot change what the lift imports. (The embedded Python without its `._pth`
still lists a registered system Python's `Lib` and `DLLs` after its own `python314.zip`; the standard library comes
from the zip first, so this changes no import.)

Tests: `node test_texdeps.js` (the list against the scripts' imports, the pins, the skip, the offline message, a bad
hash). The real run on a fresh temporary tools folder: `generated/analysis/texpack_deps/RESULTS.md`.

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

## Benchmark

The Benchmark page runs one of two benchmarks with the player's current settings: the game is started exactly as Play
starts it (`bench.js` `gameEnv`, shared with Play), plus only `MSPR_BENCH` (fly | race), `MSPR_BENCH_OUT` (the result
file, `play\benchmark\<mode>.json`) and `PS3_DEV_GUEST_STR` (the boot config). None of them is a settings.ini variable,
so the game applies settings.ini as on Play (`node launcher/electron/test_bench.js` checks both).

- **Fly-through**: two maps, one game run each, one after the other: the disc's own
  `configs/benchmark_happyJungle.cfg` (Happy Jungle), then `configs/benchmark_Wildfire.cfg` (the lava track Wildfire),
  camera flights without cars. Measured on each: from the first frame with the world drawn to the first static
  "HotSpot" view (a lift hook in `bench_patch_lifted.py`), i.e. the flight only. Each run writes
  `play\benchmark\fly_<map>.json`; the launcher (`bench.js` `runSteps`, `combineFly`) writes `fly.json` with both maps
  and the combined numbers: average = all measured frames of both maps over their measured time, min = the lower min,
  max = the higher max. A map without a result shows its error beside the other map's result. A run that ends without
  a result at the known start-up `GcKernel::Present() Timeout` is started once more; Stop ends both maps.
- **Race with AI racers**: a 16-car race on Kanaloa Bay, the player's car driven by the game's own AI (the same lift
  patch, port `bench_ai.h`). Its config is made at run time from the player's own `MS2.PSARC`
  (`configs/aggression_race.cfg` + the benchmark config's environment, a few edits checked against the SHA-256 of the
  tested config) and written into the overlay folder the game already reads (`play\pcmenu`). The game skips the pre-race
  flyover itself (CROSS through its pad layer) and measures race start + 21.5 s .. + 111.5 s.

The game measures (guest frames, not presents: `port-vkgame/bench_run.h`, test `port-vkgame/tests/test_bench_run.c`),
writes the JSON result (GPU it rendered on, CPU, RAM, min / max / avg FPS, 1 % and 0.1 % low, frame-time percentiles,
the settings it started with) and quits by itself; the page then shows it. Min and max are the slowest and fastest
whole second of the measured part.

## Decrypt automatically (RPCS3, at the player's request)

Install step 02 has a "Decrypt automatically..." button beside "EBOOT.elf..." (enabled once step 01 has a disc the
launcher accepts). It makes the `EBOOT.elf` from the chosen disc's `EBOOT.BIN` with RPCS3, so the player does not have
to (`launcher/electron/service/autodecrypt.js`, `Builder.autoDecrypt`, service command `{cmd:'autodecrypt', confirmed:true}`):

1. **Confirmation first.** The window asks before anything is downloaded: RPCS3 is a third-party open-source PS3
   emulator (GPL-2.0), downloaded from its official source, used only to decrypt the EBOOT.BIN of the player's own disc,
   and deleted afterwards. The service refuses the command without `confirmed: true` (nothing is fetched).
2. **Download.** `https://api.github.com/repos/RPCS3/rpcs3-binaries-win/releases/latest` (HTTPS). The release must have
   exactly one `rpcs3-v<ver>-<build>-<commit>_win64[_msvc].7z` asset whose link is under
   `https://github.com/RPCS3/rpcs3-binaries-win/releases/download/<tag>/`, a plausible size, and a SHA-256: GitHub's
   asset digest, the release text's `<sha256>;<size>B` and the `.sha256` asset must all agree (size too), and at least
   one must be there. The archive is checked by size and SHA-256 after the download (`tools.download`).
3. **Unpack.** Into a new temporary folder `MotorStorm\autodecrypt-XXXXXX\rpcs3\`, by Windows' own `tar.exe`
   (libarchive; it reads `.7z` where it has liblzma: Windows 11 does, the bsdtar 3.5.2 of Windows 10 does not, and then
   the step fails with a message pointing at "EBOOT.elf..."). Nothing is run from the player's game folder.
4. **Decrypt.** The disc's `EBOOT.BIN` is copied (the disc is only read) to `autodecrypt-XXXXXX\input\EBOOT.BIN`, then
   `rpcs3.exe --allow-any-location --decrypt <copy>` runs with a `portable\` folder beside `rpcs3.exe` (RPCS3 then keeps
   its config, cache, logs and `dev_hdd0` there: `fs::get_config_dir`), `RPCS3_CONFIG_DIR` pointing there too, and
   `TMP`/`TEMP` pointing into the temporary folder (RPCS3's `rpcs3_vm_sparse.tmp`). `--decrypt` makes RPCS3 a headless
   application; it writes `<input without extension>.elf` (`rpcs3/Crypto/decrypt_binaries.cpp`). `--allow-any-location`
   because RPCS3 otherwise refuses to start from a temporary or OneDrive folder. A 5-minute limit ends it.
5. **Verify.** The ELF's size and SHA-256 against `game.json` (as for a chosen file). Only a match is copied to
   `MotorStorm\decrypted\EBOOT.elf` and set as `elf100`, exactly as if the player had chosen it; anything else is
   refused with its hash and nothing is kept.
6. **Remove.** The temporary folder (RPCS3, its archive, its config/cache/`dev_hdd0`, the EBOOT.BIN copy) is deleted
   in a `finally`, on success, failure or Stop; a folder left by a crash is removed at the next start. If it cannot be
   removed the step fails and says where it is.

No network, a failed download, a refused checksum or a failed unpack each end with a message, and the cleanup runs.
RPCS3 is never bundled, committed or redistributed with the launcher. Tests: `node launcher/electron/test_autodecrypt.js`
(fakes only). CLI: `node launcher/electron/service/cli.js --root <dir> --disc <iso|folder> --autodecrypt`.

## Keys and decryption: what is and is not in the launcher

- The launcher's own code (`launcher/electron`, `launcher/pipeline`, `game.json`, `toolchain.json`) holds hashes, sizes,
  offsets and URLs only. No decryption code, no keys, no decrypted or lifted game data.
- The player's decrypted ELFs are their own files. The launcher reads them and never writes them into its source,
  its snapshot, its settings or any upload. "Decrypt automatically" stores the one it made (checked) in
  `MotorStorm\decrypted\`; RPCS3, which did the decryption, is deleted right after.
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

(2026-11-27: an opt-in replacement, "Decrypt automatically" above, downloads RPCS3 itself at the player's request and
deletes it again; nothing below came back: no stored `rpcs3.exe` path, no `decrypt` install step, no `eboot_self` hashes.)

- `launcher/electron/service/decrypt.js` (the RPCS3 call, its copy of the EBOOT and the RPCS3 update lookup).
- In the install: the `decrypt` step, the `rpcs3` choice and the stored `rpcs3.exe` path (`launcher.json`), the
  `rpcs3.exe` picker, the `--rpcs3` option of `cli.js`, and the `eboot_self` hashes in `game.json`.

## Status

See the 2026-11-13 launcher entries in `docs/STATUS.md`.
