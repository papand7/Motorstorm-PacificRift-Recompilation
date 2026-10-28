# PS3 audio pipeline in the native Windows port (2026-10-23)

This covers intro audio: the path from the Bink file to the Windows endpoint. Status labels: VERIFIED, PARTIAL, UNKNOWN, MISSING. Sources: ps3recomp-int `8b62438`; runs `generated/runs/20261023-062815-sse2` and `20261023-084212-ind` (both before `8b62438`). No game run since then.

## Path

| # | Stage | Where | Format | Status | Evidence |
|---|---|---|---|---|---|
| 1 | Bink audio in the intro file | `USRDIR/GUI/VIDEO/GUI/GUI_INTRO_EU.BIK` (opened as `gui_intro_eu.bik`) | `BIKi`, 3159 frames 1280×720 at 29.97; **28 audio tracks**, all 48 kHz Bink DCT, 14 stereo and 14 mono | VERIFIED (header read) | Which tracks the game selects is UNKNOWN |
| 2 | Guest Bink audio decode | Game's Bink library; PPU thread "Bink Audio Thread" (entry `0x01096E98`, prio 649) | Guest-internal | PARTIAL | The thread is created. Decoder location (PPU or SPU) and output buffers not traced |
| 3 | Guest PCM into the cellAudio ring | Port 1, opened by the game: 2 ch, 16 blocks, ring at guest `0x58200000`, read index at `0x58300000` (`cellAudioGetPortConfig`) | Big-endian float32, interleaved L/R, 256 frames per block, 16-block ring | VERIFIED filled | `[astat]` p1 `filled=100.0%` in 20 consecutive 5 s windows of the intro in both runs. Level not measured before `8b62438` |
| 4 | Ring consumption (HLE mixer) | `libs/audio/cellAudio.c` `audio_mix_one_block` | Reads `read_index % nBlock`, byte-swaps (`ld_be_f32`), applies level 1.0, clears the block, publishes `read_index % nBlock` to the read-index address, pushes `CELL_AUDIO_EVENT_MIX` to notify queues | VERIFIED running | 187.5 blocks/s, total drift −0.7…+5.2 ms, 0 dropped |
| 5 | Host mix | Same function: stereo float32 sum of all running ports, 8 ch downmixed to L/R, clip to ±1 | Host float32 stereo 48 kHz | VERIFIED non-zero | `[audio-rate]`: during the intro 0.0 % of mixed blocks were all-zero (20 windows per run) |
| 6 | Windows device | `audio_backend_init/submit` (WASAPI shared mode, default console render endpoint, 48 kHz 2 ch float32 with `AUTOCONVERTPCM`, 20 ms event-driven buffer) | Float32 stereo | **MISSING in every MotorStorm run** | The runner set `FIRST_FRAME=1 FIRST_FRAME_AUDIO=silent`, so `audio_backend_init` returns before any COM/WASAPI call. stdout: `[FIRST_FRAME] cellAudioInit: silent WASAPI output`. `audio_backend_submit` returns at once with no render client. All 20 run manifests under `generated/runs/` have this setting |
| 6′ | Same backend outside the game | `libs/audio/tests/test_wasapi_output.c` | Same | VERIFIED (host only) | Default endpoint, mix format 48 kHz 2 ch 32-bit (extensible). 29 184 frames accepted, RMS −34.4 dBFS, 0 errors, 0 silent-flag frames, released cleanly. Audibility to be confirmed by the user |

## Audio-out configuration (before any PCM)

- The game calls `cellAudioOutGetSoundAvailability` (×3), `cellAudioOutGetNumberOfDevice`, `cellAudioOutGetState` and `cellAudioOutGetDeviceInfo` from one function (`0x437610`).
- Its mode search (`0x438530`–`0x438640`) reads `availableModeCount` at +1 and mode k at +8 + 8k (type, channel, fs). For each mode it checks the game's table at `TOC+0x735C`.
- If no mode matches, it prints `CAN'T FIND A SUPPORTED AUDIO RESOLUTION` (`0x438834`) and returns without `cellAudioOutConfigure`.
- With a match, it calls `cellAudioOutConfigure` with the chosen channel count, waits 1 s and re-reads the state.
- Before `8b62438` the HLE wrote the modes at +6 + 4k. VERIFIED BROKEN: the banner is in every run, and no `AudioOutConfigure` call appears.
- `8b62438` fixes the layout. What the game does differently with a valid mode is UNKNOWN until the next run.

## Imported audio APIs (EBOOT import table)

- **cellAudio:** `Init`, `Quit`, `PortOpen`, `PortClose`, `PortStart`, `PortStop`, `GetPortConfig`, `GetPortBlockTag`, `GetPortTimestamp`, `SetNotifyEventQueue`, `RemoveNotifyEventQueue`.
  - Not imported: `CreateNotifyEventQueue`, `SetPortLevel`.
- **cellSysutil audio-out:** `GetSoundAvailability`, `GetDeviceInfo`, `GetState`, `GetNumberOfDevice`, `Configure`.
- **Ports seen in the runs:**
  - port 0: 8 ch, 16 blocks, started at boot, 0 % filled through the intro (game mixer; idle or silent, UNKNOWN which);
  - port 1: 2 ch, 16 blocks, Bink, started at the intro and stopped and closed at its end.
- **Synchronization:** the guest producer is paced by the notify-queue events and the published read index. The host consumer is paced by the WASAPI buffer with a device, and by QPC without one. Video timing does not read the audio clock (cellAudio has no host-video coupling).

## Diagnostics (`PS3_AUDIO_STATS=1`, from `8b62438`)

Each `[astat]` line (5 s) adds:
- per port: `rms`/`peak` in dBFS, `nz` (non-zero share) and `nonfinite` of the consumed guest samples (stages 3–4);
- `mix rms/peak/clipped` (stage 5);
- `dev=<wasapi|sdl|null|failed> frames=/s rms peak silentflag err` (stage 6).

`cellAudioInit` logs the endpoint id, the device mix format and the buffer size, or `output: none -- ...`.
