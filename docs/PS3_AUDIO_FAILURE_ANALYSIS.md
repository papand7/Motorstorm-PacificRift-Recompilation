# Silent intro: failure analysis (2026-10-23)

**Status: root cause VERIFIED for the host side. Audible output is NOT yet verified (no game run since the fix).**

## Root cause (earliest proven failure on the path to the speaker)

**No Windows audio device was ever opened in a MotorStorm run.**
- The runner config `tools/motorstorm_milestones.json` set `"env": {"FIRST_FRAME": "1", "FIRST_FRAME_AUDIO": "silent"}` for every `fast_startup.py` run.
- With that policy, `audio_backend_init` (`ps3recomp-int/libs/audio/cellAudio.c`, WASAPI branch) returns 0 before `CoInitializeEx`.
- The mixing thread then paces on QPC, and `audio_backend_submit` returns at once because there is no render client.
- This is the development-only "silent sink" (`first_frame_audio_policy.h`; `docs/STATUS.md` line 161) from first-frame bring-up. It was never switched off.

Evidence:
- `generated/runs/20261023-084212-ind/stdout.log`: `[FIRST_FRAME] cellAudioInit: silent WASAPI output; guest mixer remains active`.
- `manifest.json` of all 20 runs under `generated/runs/`: `"FIRST_FRAME_AUDIO": "silent"`.
- No run log contains a WASAPI init or endpoint line.

## Separate verified defect upstream: audio-out mode list

- `cellAudioOutGetDeviceInfo` wrote its sound modes at +6 + 4k.
- The game reads them at +8 + 8k: disassembly of `0x438530`–`0x438640`, mode stride 8, type/channel/fs at +8/+9/+10.
- It found no LPCM mode, printed `CAN'T FIND A SUPPORTED AUDIO RESOLUTION` in every run, and skipped `cellAudioOutConfigure`.
- The effect on the Bink port is UNKNOWN: port 1 was filled anyway.
- Possible effects on the game's own mixer (port 0, 8 ch, 0 % filled through the intro) or on track/speaker selection are also UNKNOWN.

## What worked before the fix (VERIFIED from the `sse2` and `ind` runs)

- The game opens a 2 ch, 16-block Bink port, starts it at the intro and stops it at the end.
- The mixer consumes it at 187.5 blocks/s with 0 dropped and drift under 6 ms.
- During the intro, 100 % of port-1 blocks held a non-zero sample, and 0 % of mixed output blocks were all-zero.

**NOT measured:** the level. A "non-zero" block can still be inaudibly quiet or noise. `8b62438` adds RMS and peak per stage.

## Eliminated or unchanged alternatives

| Candidate | Verdict | Why |
|---|---|---|
| Backend missing or not built | Eliminated | WASAPI is the default on `_WIN32` (`AUDIO_BACKEND_WASAPI`); `ole32` is linked. The host test plays through it |
| Device format mismatch | Eliminated (host) | Shared mode with `AUTOCONVERTPCM`; the endpoint mix format is 48 kHz 2 ch float, and the test stream was accepted |
| Endianness of guest PCM | Eliminated in code, not in game | `ld_be_f32` byte-swaps; `test_audio_mix.c` passes. In game, "non-zero" alone cannot rule out wrong-endian noise; RMS/peak will |
| Port never started | Eliminated | `PortStart(port=1)` logged; no "HAS DATA but never started" warning |
| `PS3_MUTE` / silent flag | Eliminated | Not set in any manifest. Now also counted (`silentflag`) |
| Ring addressing or wrap | Eliminated for consumption | Filled share 100 %, read index published modulo nBlock (`test_audio_mix.c`) |
| Port level / gain | Open, low risk | `PortOpen` ignores the param's `attr`/`level`, and level is always 1.0. Not a silence cause, but not faithful if the game passes an initial level |
| Guest decoder produces zeros | Eliminated as a cause of total silence | Blocks are non-zero. Their level is still unmeasured |
| Audio/video sync | Not a cause | 0 resyncs; video timing does not depend on the audio clock |

## Missing measurements for the next run

1. `[astat]` p1 `rms`/`peak`: is the guest PCM at program level, not noise?
2. `dev=wasapi`, `frames≈48000/s`, `rms` close to the port's level, `err=0`, `silentflag=0`.
3. Whether the game now calls `cellAudioOutConfigure`, and with which channel count.
4. Whether port 0 starts carrying audio.
5. Audibility: only the user can confirm it.
