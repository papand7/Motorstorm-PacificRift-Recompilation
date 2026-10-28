# Garage validation run (EXECUTED once, 2026-10-23; see Result at the end)

**Question:** after the intro skip, does the game read the whole garage world
(`/worlds/track_garage.rpk`) from `MS2.PSARC`, and what follows?

## Inputs

| | |
|---|---|
| Exe | `build/motorstorm-int-garage-8bc4932e/MotorStormPacificRiftRecomp.exe` (ps3recomp-int `2f6c7cf` + private port; build log `generated/introskip/build_garage.log`) |
| SHA256 | `8bc4932e9a9e87c9ae2a6c8e795d2d19b6133b1361b9dc2211f541ed217c044f` |
| Previous exes kept | `build/motorstorm-int-skip-2c1809c6/` (the skip run), `build/motorstorm-int-fcw-f25903bc/` |
| Config | `generated/profile/motorstorm_milestones.garage.proposed.json` (with `--config`; the live config is unchanged) |
| Audio | native (config env `FIRST_FRAME_AUDIO=native`) |
| Thermal | off (optional) |

## Command (from the motorstorm root)

```
py -3 tools/fast_startup.py --exe build\motorstorm-int-garage-8bc4932e\MotorStormPacificRiftRecomp.exe --name garage-read ^
  --config generated/profile/motorstorm_milestones.garage.proposed.json ^
  --target garage_world_read_complete --allow-extended --stop-on-fatal --stop-on-line "\[CUBE\] fp=" ^
  --snapshot-cache --env PS3_DEV_SKIP_INTRO=1 --env FS_CALLER=1 --env PS3_FSLOG_READS=5 ^
  --env PS3_FC_WATCHDOG_MS=3000 --env RSX_HEARTBEAT_MS=1000 ^
  --env PS3_VIDEO_STATS=1 --env PS3_VIDEO_STATS_TIMELINE=generated/profile/garage_vstat.csv
```

The wrapper adds:
- the 210 s cap and the 225 s hard deadline;
- the GPU-watchdog stop line;
- a process-tree kill on every stop, then a sweep by image name;
- no retries.

`--snapshot-cache` copies and hash-verifies the cache before launch.

## Stops (first wins)

1. `garage_world_read_complete`: every stored byte of `track_garage.rpk` was read.
2. The first `[CUBE] fp=` line, the first cube-mapped shader. This caps execution before
   sustained garage rendering if the read is not seen as complete, for example when served from cache.
3. The first `GcKernel::Present() Timeout`, or any fatal line (`--stop-on-fatal`).
4. 210 s, or a process exit or crash.

The extension past the garage request is expected to be seconds. In the skip run the garage world
was already being read at ~33 s, and the request came at 34.6 s.

## Evidence to collect

- Milestone times: `intro_video_closed`, `loadscreen_page_read`, `garage_world_read_started`,
  `garage_resources_requested`, `garage_world_read_complete`.
- `py -3 tools/psarc_read_map.py <run> --fd 5 --match garage,loadscreen,mainmenu`: members read,
  in order.
- `cache_state.json`, and the snapshot manifest.
- Any short read (`got < want`) or a read at an unexpected position on fd 5.

## Pass / fail

- **Pass:** `garage_world_read_complete` with no fatal line and no short reads. That shows the
  original garage world was read in full from the original archive. Decompression and parsing are
  not shown; the next evidence would be `garage_rendering_started`.
- **Inconclusive:** stopped by `[CUBE]` first. Rendering started, so the load got far enough, but
  the full read was not seen.
- **Fail:** fatal, watchdog or timeout before `garage_world_read_started`, or reads that stop
  partway through the member. Record the last member and position. No retry.

## Ready?

Yes, offline:
- the exe is built and hashed;
- the config validates and replays;
- the argv passes the wrapper's checks (without `--allow-extended` it is refused);
- all suites pass.

Not run.

## Result (run `generated/runs/20261023-134457-garage-read/`, executed once, authorized)

- Exe `8bc4932e…` (hash checked before launch). Cache snapshot `generated/cache-snapshots/20261023-134457/` (31.8 MB, hash manifest). Thermal off. No retry.
- **Termination:** `milestone_reached` (`garage_world_read_complete`), at a wall time of 34.26 s. Watchdog and hard deadline not hit; no leftover process.
- Milestones:
  - `intro_video_closed`: 30.88 s;
  - `loadscreen_page_read`: 31.24 s;
  - `garage_world_read_started`: 31.78 s;
  - `garage_world_read_complete`: 34.24 s.
- **VERIFIED:** all 23,207,184 stored bytes (764 blocks) of `/worlds/track_garage.rpk` were read from `MS2.PSARC` over 2.45 s.
  - 2,915 reads on fd 5 in the run, totalling 90.8 MB;
  - none short (`got < want`) and none at -1;
  - no fatal, NOSYS, error or `[CUBE]` line.
- **Not shown:** decompression, parsing and use.
  - The SPU job lists keep cycling (`mfc-list`/`spu-int`) with no error. That is indirect only.
- **Stopped while reading** `/env/Track0a_Garage_Sky1_driver.rpk`. The `_objects` probes (the prior "first garage request") had not happened yet.
- Failed opens (all ENOENT, all expected optional files, all by `func_00667558+0x25EF` except `flashMP3.pic`):
  - `flashMP3.pic`;
  - two `dspsettings/*.mng`;
  - `data/events/default.race`.
- `/gui/mainmenu.gui` was read at stderr line 2441. That is **before** the intro opened (line 2951), within a sequential prefetch of the archive head. It does not indicate the menu state.
- The emblem white-to-black behaviour was not reached (the run stopped before any `[CUBE]` compile; no capture).
- Full per-read map: `psarc_read_map_all.txt` in the run directory.
