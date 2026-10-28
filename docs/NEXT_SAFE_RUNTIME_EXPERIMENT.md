# Next safe runtime experiment: frame-clock stall capture (PROPOSED, NOT RUN)

One run. It needs the user's explicit go-ahead. It is never retried automatically: a
second run needs a separate go-ahead.

## Purpose

Name where the host frame-clock thread stops when presentation freezes with native
audio. In `20261023-100017-audio` this was about 104 s in (see
`NATIVE_AUDIO_STARTUP_REGRESSION.md`). The stage and host stack tell the four unlogged
candidates apart:
- DXGI Present;
- the window pump;
- the FIFO walk;
- a driver call during the drain.

## Inputs

| | |
|---|---|
| Exe | `build/motorstorm-int-fcw-f25903bc/MotorStormPacificRiftRecomp.exe` |
| SHA256 | `f25903bca47a32a13820d42f5f1dcab70fccf712e4c8ff8b7ab977ff390f7cb8` |
| Map | `build/motorstorm-int-fcw-f25903bc/MotorStorm.map` |
| ELF | `generated/decrypted/EBOOT.elf` (the runner records its hash) |
| Milestone config | live `tools/motorstorm_milestones.json`, unchanged. Its env already sets `FIRST_FRAME_AUDIO=native`. The proposed config is not needed: the GPU-watchdog stop comes from the wrapper. |
| Caches | `generated/hdd0`, `generated/hdd1` left as they are, with nothing deleted or moved. List them (`dir /s`) before the run so a change can be attributed. |
| Thermal monitor | off (default). Hardware, firmware and Windows thermal management apply. Add `--thermal-guard` only if the user asks. |

## Command (from the motorstorm root; the relative paths depend on it)

```
py -3 tools/fast_startup.py --exe build\motorstorm-int-fcw-f25903bc\MotorStormPacificRiftRecomp.exe --name fcw-audio ^
  --env PS3_FC_WATCHDOG_MS=3000 --env RSX_HEARTBEAT_MS=1000 ^
  --env PS3_VIDEO_STATS=1 --env PS3_VIDEO_STATS_TIMELINE=generated/profile/fcw_audio_vstat.csv ^
  --env PS3_AUDIO_STATS=1 --env PS3_POLLTOP=10 ^
  --env PS3_FTRACE=95:15:generated/profile/fcw_audio_ftrace.txt --env PS3_FTRACE_CAP=1000000
```

The wrapper adds the following itself:
- target `garage_resources_requested`;
- `--timeout 210`;
- `--stop-on-line "GcKernel::Present\(\) Timeout"`;
- the VFS and HDD roots;
- the hard deadline at 225 s.

There are no `--allow-extended`, `--retries` or capture flags.

## Stop conditions (first one wins)

1. Target `garage_resources_requested` reached, then stop. No extended garage execution.
2. First `GcKernel::Present() Timeout` line, the GPU watchdog: reason `stop_line`.
3. Process exit or crash.
4. 210 s wall clock: reason `timeout`.
5. Hard deadline at 225 s, if the runner loop itself hangs: tree kill, recorded in
   `safeguards.json`.

On every stop the whole process tree is killed (`taskkill /T /F`), then any leftover
instance is killed by image name. Logs and the run directory are kept.

## Expected output

- **If it freezes as before:** about 3 s after presentation stops, stderr shows
  `[fc-watchdog] frame clock no progress for ~3000 ms in stage=…` and up to 24
  `#NN module+0xoff` frames:
  - `MotorStormPacificRiftRecomp.exe` offsets resolve through the map;
  - system DLL frames name the API, for example `dxgi.dll`, `d3d12.dll`, `user32.dll`,
    `win32u.dll` or the driver.

  The first Present timeout follows within seconds and ends the run.
- **If no stall occurs:** no `[fc-watchdog]` report after the start line, and the run
  stops at the garage request. That is evidence too: compare its pacing with
  `20261023-100017-audio`.
- **Also recorded:**
  - the vstat timeline (Bink lateness and skip at about 31 s, for comparison);
  - audio stats;
  - an ftrace of 95–110 s (all threads' waits around the freeze);
  - `manifest.json` / `summary.md` / `safeguards.json` with the stop reason.

## Cancel before starting if

- the exe hash differs from the one above;
- any MotorStorm process is already running;
- the user has not authorized the run, or wants the thermal monitor on and it cannot get
  a reading.

## Stop by hand if

- the machine behaves abnormally: fans, throttling, display;
- the run passes the garage request without stopping;
- the window shows anything past the garage request.

Ctrl-C in the runner records `cancelled`, and the tree is killed.
