# Audio restoration: changes, tests, limits (2026-10-23)

**Status: offline-verified only. Audible original audio is NOT confirmed; no MotorStorm run since these changes.**

## Changes

**1. Runner: open the real device** (private, `tools/motorstorm_milestones.json`; not in git)
- `"FIRST_FRAME_AUDIO": "silent"` → `"native"`. `FIRST_FRAME=1` stays.
- The previous file is kept as `generated/audio/motorstorm_milestones.before-native-audio.json`.
- With `native`, `cellAudioInit` runs the normal WASAPI path: the default console render endpoint, shared mode, 48 kHz 2 ch float32, with the engine converting to the device format.
- Mixer pacing moves from QPC to the device buffer, the normal production path. Guest audio semantics are unchanged.
- To silence an unattended run: `--env FIRST_FRAME_AUDIO=silent` or `--env PS3_MUTE=1` (the device keeps pacing, output is silent).

**2. ps3recomp-int `8b62438`**
- `cellAudioOutGetDeviceInfo` (`libs/misc/cellAvconfExt.c/.h`): writes the guest layout (modes at 8 + 8k, 8 bytes each, u16 latency, 136 bytes), field by field.
- `PS3_AUDIO_STATS` (`include/ps3emu/audio_stats.h`, `libs/audio/cellAudio.c`):
  - per-port, mix and device levels;
  - device state `wasapi`/`sdl`/`null`/`failed`;
  - device frames, silent-flag frames and buffer errors;
  - an init log of the endpoint id and mix format.
- WASAPI error handling: `Start`, `GetBuffer` and `ReleaseBuffer` results are now checked. A failed `Start` releases the client, and the mixer falls back to clock pacing.
- `audio_backend_submit` returns the frames the device accepted.
- Mixing, ring and pacing logic are unchanged. With stats off, each hook is one load and a branch.

## Tests

| Test | Result |
|---|---|
| `libs/misc/tests/test_avconf_audio_out.c` (new): the game's mode read on the written struct, bounds, null pointer, GetState unchanged | PASS gcc/clang (WSL); FAILS on the old code (mutant check) |
| `tests/test_audio_stats.c` (+ levels, NaN, −0.0, clip, silent flag, errors, window reset) | 32 checks PASS gcc/clang |
| `libs/audio/tests/test_audio_mix.c` (+ level through the real mixer; no device = 0 device frames) | 4166 checks PASS gcc/clang |
| `libs/audio/tests/test_first_frame_silent_runtime.c` (Windows) | PASS |
| `libs/audio/tests/test_wasapi_output.c` (new, Windows, manual): 0.5 s 440 Hz tone at about −33 dBFS through the real WASAPI path | PASS. Endpoint `{0.0.0.00000000}.{6236a21b-…}`, mix 48 kHz 2 ch 32-bit; 29 184 frames accepted, RMS −34.4 dBFS, peak 0.030, 0 errors, 0 silent; released |
| `libs/misc/tests/test_avconf_gamma.c` | PASS |
| `tools/test_*.py` | Windows 87/87; WSL 84/87, the same 3 known failures (`test_loaded_image_memory`, `test_sail_boot_callback`, `test_sysmodule_unload_module_ex`) |
| `libs/audio/tests/test_audio_ring.c` | Does not link (missing `sys_event_*` stubs). Pre-existing, not in CI, not changed |

- CI: the new avconf test runs in `linux.yml` and `macos.yml`; the stats test now links `-lm`.
- Public audit: 25 inherited findings, none in this commit.

## Build

- `build/motorstorm-int/MotorStormPacificRiftRecomp.exe` was rebuilt from `8b62438` with `generated/upstream/build_int_chain.cmd` (log `generated/audio/build_int_audio.log`): sha256 `611ad702b6402de29cf352402d318bd7dc1e50d0609d13d429b8ecf800969ba8`, preserved with its map in `build/motorstorm-int-8b62438/`. The Bink lift is byte-identical to the `6637de6` one (6 `SPU_CHAIN_IND_OK` sites).
- The `6637de6` executable remains in `build/motorstorm-int-6637de6/`.
- The SPU lift arguments (chain-indirect, join-groups) are unchanged.

## Remaining limits and assumptions

- **No game run since the fix.** Guest PCM level, device submission in game, and audibility are unverified.
- **Effects of the avconf fix on the game are unknown:**
  - it now gets a valid mode and will call `cellAudioOutConfigure`, then wait 1 s (game code), which adds about 1 s before the intro;
  - which mode it picks among 2/6/8 ch;
  - whether port 0 or Bink track selection changes.
- **Gaps in the mixer model:**
  - the stereo downmix of 8 ch ports is the runtime's own mapping (not the firmware's);
  - `PortOpen` ignores the guest's initial port level.

  Neither matters for the 2 ch Bink port.
- **Output assumptions:**
  - the default console render endpoint is assumed to be the one the user listens to; the endpoint id is now logged;
  - the session volume and mute state of the process are not read.
- **Unchanged by design:** audio/video sync is untouched, and Bink resync thresholds and timing are as before.

## Validation plan (one run, NOT authorized yet)

- **Executable:** the `8b62438` build, sha256 `611ad702…969ba8`; before launch, verify the full SHA256 against `build/motorstorm-int-8b62438/`.
- **Probe:** `generated/profile/probe_audio.sh` (prepared, not run; texsnap RVA `0x198FBB60` from the new map). Before launch, move the current hdd0/hdd1 cache aside (it holds the `ind` run's cache), as for `ind`.
- **Probe:** the `probe_ind.sh` protocol with the runner's native audio, `PS3_AUDIO_STATS=1`, `AUDIO_RATE=1` and `PS3_VIDEO_STATS` / texsnap as before.
- **Safety protocol:**
  - at most 210 s;
  - stop at `garage_resources_requested`;
  - guard at 363 K with rapid-rise protection;
  - preserve `original/`, logs and cache;
  - no retries;
  - no power changes.

| Check | Pass condition |
|---|---|
| Device | stderr `[cellAudio] output: WASAPI shared …` and `dev=wasapi` |
| Guest PCM | p1 `rms` above about −60 dBFS during the intro, `nonfinite=0` |
| Mixer | `mix rms` ≈ p1 rms, `clipped` ≈ 0 |
| Windows | `frames` ≈ 48000/s, `rms` ≈ mix rms, `err=0`, `silentflag=0` |
| Config | `AudioOutConfigure` logged; no "CAN'T FIND A SUPPORTED AUDIO RESOLUTION" banner |
| Audible | The user hears the original intro soundtrack (user confirmation only) |
| Video | Decoded fps and 4:1 time in the range of `sse2`/`ind`, 0 torn, garage request reached, no process left |
