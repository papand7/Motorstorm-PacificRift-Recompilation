# Garage loading progress

Offline (2026-10-23). No launch.

## Existing stop condition (VERIFIED)

- **Milestone:** `garage_resources_requested` in `tools/motorstorm_milestones.json`.
  - Pattern: `\[fs\] open[^']*'([^']*track_garage[^']*)'`.
  - Must come after `intro_video_opened`.
- **What it matches:** the first failed loose-file probe, `/worlds/track_garage_ain_objects.rpk`. This is a request, not a load.
- **What happens on a match:** `startup_runner.py` records `milestone_reached` and calls `proc.terminate()`. If the process is still alive 10 s later, it kills it.
  - The guest runs about 0.02–0.25 s past detection.
  - Replay of `ind`: stop at stderr:1535.
- **Default now enforced by `tools/fast_startup.py`** (2026-10-23):
  - with no `--target`, the run stops at `garage_resources_requested`;
  - `--timeout` defaults to 210 s and cannot exceed it;
  - any target outside the pre-garage set needs `--allow-extended`, whatever the config says;
  - 7 offline tests in `tools/test_fast_startup_safety.py` cover this.
  - Before this change, a run without a target used the runner's 900 s default. With the live config, `--target garage` also ran past the request.

## Was the garage resource ever opened? NO evidence

- No archive member read has been logged in any run. The garage data lives inside `MS2.PSARC` and is read through `cellFsRead`/`cellFsLseek` on the archive descriptor.
- Read logging was off in every run: `PS3_FSLOG_READS=<fd>` was not set.
- The last two garage-capture runs (`20261021-225844-fast-garage-capture`, `20261022-064218-fast-garage-capture2`) recorded no termination. They are most likely the runs where the host lost power.

## PSARC (VERIFIED, read-only)

- **Archive:** `MS2.PSARC`, 4.8 GB.
  - SHA-256 `5c76379c…397ec`, unchanged (`generated/profile/asset_verify_20261023.txt`).
  - 5005 members, zlib, 64 KiB blocks; 722 members share or overlap compressed spans.
- **Relevant members:** `/worlds/track_garage.rpk`, `/gui/mainmenu.gui`, `/data/gui/MainMenu.gui`.
- **Extraction is not required.** The original FIOS layer reads the archive itself; extracting it would bypass the original loader.
- **`tools/psarc_read_map.py`** (private; 5 synthetic tests):
  - maps logged `[fsread] fd=N … pos=P` reads onto member compressed spans;
  - reports the first garage and mainmenu member touched;
  - a touched member means its bytes were read, not that they were decompressed or used.

## Loader capabilities available offline

- `[fs] open` / `open FAIL` / `-> fd N` are logged in every profile.
- `FS_CALLER=1` adds the opener and closer (`(opened by …)`, `[fs] close fd=N (by …)`).
- `PS3_FSLOG_READS=<fd>` logs every read on that descriptor. Use the archive fd: 5 in current cold runs.
- `PS3_FTRACE` gives a bounded function-call trace.
- Runner `fd_event` milestones follow a descriptor (see the proposed config in [MENU_MILESTONE_PLAN.md](MENU_MILESTONE_PLAN.md)).

## Cache state

- `generated/hdd0` and `generated/hdd1` are **warm** after the audio run; they hold `game/` and `cache/`.
- A warm FIOS cache produced a loop of 4071 open pairs, according to the secondary agent.
- Any next run needs cold caches. Move them aside under `generated/upstream/…`; never delete them.
- Preserved copies so far:
  - `hdd1_written/pre_audio_warm/`
  - `hdd1_written/audio_cold/` (718 MB)
  - `hdd0_written/pre_audio/`
  - `hdd0_written/audio/`
