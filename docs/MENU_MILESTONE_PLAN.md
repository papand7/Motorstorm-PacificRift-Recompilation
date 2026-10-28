# Menu milestone plan

Offline (2026-10-23). **No launch is authorized by this plan.** Each run below needs separate, explicit authorization.

## Where things stand

- **Earliest blocker:** native-audio intro hang at Bink frame 2255; 26 `GcKernel::Present() Timeout`; cause unknown. See [POST_INTRO_TRANSITION.md](POST_INTRO_TRANSITION.md).
- **With silent audio:** the garage is requested, then nothing is observed. See [GARAGE_LOADING_PROGRESS.md](GARAGE_LOADING_PROGRESS.md).
- **Menu dependencies and input:** [MENU_INITIALIZATION.md](MENU_INITIALIZATION.md).

## Safety tooling (offline-validated)

- **Thermal guard v2:** `generated/profile/thermal_guard_v2.ps1`.
  - Fails closed: 2 consecutive samples with no reading kill the target.
  - Harness `generated/profile/test_thermal_guard.ps1` drives a dummy process (a renamed PING copy) through 10 cases, **all PASS**:
    - normal 330 K and below-limit 362 K: no kill;
    - exactly 363 K: kill "at tz=363";
    - slow climb to 365 K: kill at the limit;
    - rapid rise 330→339 K: kill;
    - slow rise 330→336 K: no kill;
    - empty sensor, missing sensor file, non-numeric reading, sensor lost mid-run: kill "no temperature reading".
  - Every case checks that the guard exited and that no dummy process is left; the temp dir is removed.
  - Real sensor check (no game): reads 347–349 K at idle, **only ~14 K under the cutoff**. Samples arrive every ~7 s because the counter reads are slow, so the 12 s rapid-rise window holds about 2 samples.
  - v1 (`thermal_guard.ps1`) fails open and must not be used again.
- **`tools/fast_startup.py`:** safe stop by default (garage request, 210 s cap); extended targets need `--allow-extended`. It now imports the runner from `ps3recomp-int`.
- **Runner** (`ps3recomp-int/tools/startup_runner.py`):
  - `fd_event` milestones;
  - per-milestone `extended` flag;
  - `--allow-extended`, `--stop-after-next`, `--stop-on-fatal`;
  - each milestone records `since_prev_s`, fd, caller and result.

## Proposed milestone config (NOT installed; needs approval)

File: `generated/profile/motorstorm_milestones.proposed.json`. Changes compared with the live config:

1. **`psarc_opened`** — archive open (`-> fd N`), no `after`.
2. **`intro_video_closed`** — `fd_event` close of the intro Bink descriptor; requires `FS_CALLER=1`. Whether Bink closes the file at the end is unverified.
3. **`garage_archive_read`** — `fd_event` read on the archive fd after `garage_resources_requested`; requires `PS3_FSLOG_READS`; **extended**; reliability indirect.
4. **`garage_rendering_started`** — marked **extended**.
5. **Fatal pattern** `GcKernel::Present\(\) Timeout`, so `--stop-on-fatal` ends a hung run early instead of waiting for the timeout.
6. **Main-menu milestones** stay `supported: false`.

Replay of saved logs (`generated/profile/replay_milestones.py`):
- **`ind`:** stops at the garage request (stderr:1535) with both configs; `psarc_opened` fd 5.
- **old diag run:** garage request at stderr:59270; archive on fd 3.
- **audio run:** garage not reached with either config; only the proposed config detects the GcKernel fatal line.

## Proposed next runs (do NOT execute without authorization)

**Run 1 — native-audio hang diagnosis (recommended next verified milestone). Stays inside the existing safe stop.**
- **Purpose:** establish why video and FIFO progress stop at about frame 2255 under native audio. Silent audio is not a fix.
- **Command shape:** `fast_startup.py --profile fast --stop-on-fatal --timeout 210`.
  - Default target: `garage_resources_requested`.
  - Env: `FIRST_FRAME_AUDIO=native`, `PS3_AUDIO_STATS=1`, `PS3_VIDEO_STATS=1`, and a bounded `PS3_FTRACE` on the Bink audio/video sync and GcKernel present paths (window and cap set in advance).
  - Requires the proposed config, so that `--stop-on-fatal` knows the GcKernel line.
- **Preconditions:**
  - cold caches (move `generated/hdd0`, `generated/hdd1` aside; no deletion);
  - thermal guard v2 running against the exe;
  - host idle temperature recorded first;
  - no retries; no power-setting changes.
- **Stop conditions:** first GcKernel timeout, the garage request, 210 s, the thermal kill, or `no_progress` 120 s.
- **Output:** one run directory; no PSARC reads logged (not needed).

**Run 2 — garage archive read (extended). Only after Run 1 explains the hang and guard v2 has run cleanly in Run 1.**
- **Command:** `--stop-after-next garage_resources_requested --allow-extended --timeout 210`, with `PS3_FSLOG_READS=5`.
  - Stops at the first milestone after the request: in practice `garage_archive_read`, a few ms later.
- **Afterwards:** `tools/psarc_read_map.py RUN --fd 5` shows whether garage members are read.
- **Risk:** this is the first execution past the safe stop since the power-loss runs. Exposure is limited to the next event.

**Not proposed:** any run toward the menu itself, RSX captures in the garage, or longer timeouts. Revisit after Run 2.
