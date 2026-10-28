# Intro skip: validation

## Offline results (2026-10-23, no MotorStorm launch)

| Test | Where | Result |
|---|---|---|
| `tests/test_pad_trigger.c`: off by default, parser, arming on the first matching open only (attract/FIOS paths ignored, case-insensitive), no press before the delay, exactly Cross (DIGITAL2 0x40), held for the hold time and ≥3 reads, one release, never re-armed, real buttons OR'd through, slow poller | Windows clang-cl `/W4 /WX`; WSL gcc and clang `-Wall -Wextra -Werror` | 6941 checks PASS (all three) |
| `libs/input/tests/test_pad_trigger_getdata.c`, through `cellPadGetData` with a stubbed XInput pad holding Start: off → no Cross; on → exactly 1 rising and 1 falling Cross edge in change packets, 8 pressed packets, Start never dropped; reopen → nothing; port 1 never pressed; real Cross still passes after | Windows clang-cl | PASS |
| Compile-only: `port/main.cpp`, `runtime/ppu/ppu_fs.cpp`, `libs/input/cellPad.c` | Windows clang-cl | OK (only the existing POSIX-name deprecation warnings in `ppu_fs.cpp`) |
| `ppu_fs.cpp` | WSL g++ `-fsyntax-only` | OK |
| `cellPad.c` | POSIX/SDL2 | **not checked**: no SDL2 headers in WSL |
| `tools/test_fast_startup_safety.py`: the 19 previous tests plus 6 new ones (no snapshot by default; snapshot before launch, hash-verified, read-only, source untouched; refusal on low disk space launches nothing; never overwrites; change detection; dummy run rewriting the cache, recorded in `cache_state.json` with the pre-run copy intact). The tests use a temp hdd1; the real cache is not read. | Windows | 25/25 PASS |
| `ps3recomp-int/tools/test_startup_runner.py` | Windows | 22/22 PASS |
| `tools/test_thermal_supervisor.py` | Windows | PASS |
| `tests/test_video_stats.c`, `tests/test_log_first.c` | WSL gcc | PASS |

The real `generated/hdd1` was unchanged after testing (`cache.dat` 480248320 B, 12:40), and no
snapshot directory was created.

## Proposed runtime validation (PREPARED, NOT RUN; needs separate approval)

**Before:**
1. Build a new exe from this tree with the `build_int` procedure into a new directory (for example `build/motorstorm-int-skip-<hash>/`), and record its SHA256. `build/motorstorm` is not touched.

**Run once, from the motorstorm root:**

```
py -3 tools/fast_startup.py --exe build\motorstorm-int-skip-<hash>\MotorStormPacificRiftRecomp.exe --name skip-intro ^
  --snapshot-cache --env PS3_DEV_SKIP_INTRO=1 --env RSX_HEARTBEAT_MS=1000 ^
  --env PS3_VIDEO_STATS=1 --env PS3_VIDEO_STATS_TIMELINE=generated/profile/skip_vstat.csv --env FS_CALLER=1
```

The wrapper adds:
- target `garage_resources_requested`;
- the 210 s cap and the 225 s hard deadline;
- the GPU-watchdog stop line;
- the process-tree kill;
- no retries.

Thermal monitoring is off. There is no `--allow-extended`.

**Pass criteria (from the logs):**
1. `[pad-trigger] armed by open '…gui_intro_eu.bik'`, then one `press 0x4000` and one `release`.
2. Bink decode stops well short of 3160 frames (vstat `decoded`), and the intro's fd is closed (`[fs] close fd=N`). This is the original teardown.
3. `garage_resources_requested` is reached. Time it from process start; the earlier run took about 138 s.
4. No `GcKernel::Present() Timeout`, no crash, and no frontend page other than the original `black` → `loadscreen-garage` path (the garage world request follows).
5. `cache_state.json` lists the cache changes, and the snapshot holds the pre-run cache.

**If the press has no effect,** the intro plays to its end, as before. That result says the
acceptance timing or the button is wrong. Do not retry. The next step is an offline look at the
GUI input dispatcher, or one approved run with a larger `PS3_DEV_SKIP_INTRO_DELAY_MS`.

**Expected gain (HYPOTHESIS):**
- In the last run the intro opened at about 28 s and the garage request came about 4 s after the intro ended (138 s).
- A skip at about 29.5 s would put the garage request near 35 s. That saves about 100 s per run.

## Runtime validation (RUN 2026-10-23, `generated/runs/20261023-131454-skip-intro`)

- **Exe:** `build/motorstorm-int-skip-2c1809c6/` (`build_int_chain.cmd`, ps3recomp-int `7227eda` + private port), sha256 `2c1809c67b82a9e8c95d40a83cd6ce7e75b2e856949fdd031d35b54ff45cfefe`. Build log `generated/introskip/build_skip.log`. The previous exe `f25903bc…` is kept in `build/motorstorm-int-fcw-f25903bc/`.
- **Env:** `PS3_DEV_SKIP_INTRO=1` (1500 ms, 150 ms), `PS3_FC_WATCHDOG_MS=3000`, `RSX_HEARTBEAT_MS=1000`, `PS3_VIDEO_STATS=1`, `FS_CALLER=1`; native audio from the live config; thermal off; `--snapshot-cache`.
- **Timeline** (s since stderr.log appeared; `generated/introskip/skip_timeline.txt`, from the read-only watcher `stamp_watch.py`):

| s | Event |
|---|---|
| 29.006 | intro `gui_intro_eu.bik` opened, fd 6 (by `func_00667558+0x25EF`); trigger armed |
| 30.501 | Cross pressed (1500 ms after the open) |
| 30.664 | Cross released (156 ms, 15 reads); trigger done |
| 30.726 | `[fs] close fd=6` (by `func_00667558+0x12B98`), 62 ms after the release |
| 34.567 | first garage request `track_garage_ain_objects.rpk`; runner stop |

- **Runner:** wall 34.7 s to `garage_resources_requested` (previous run 139.0 s). Stop reason `milestone_reached`; no GPU watchdog line, no fatal, hard deadline not reached, no leftover process, 0 retries.
- **Bink:** vstat `decoded` stopped at 44 frames (natural run: 3160), at the press.

| Finding | Label |
|---|---|
| Cross on port 0 through `cellPadGetData` ends the intro early; only one press was made, and the movie stream closed 62 ms after its release. | VERIFIED |
| The game then took its normal post-intro path to the garage request (4.0 s after the close; natural run: ~4 s after the end). | VERIFIED (same milestone as the natural path) |
| The intermediate pages `black` → `loadscreen-garage` | HYPOTHESIS (page changes are not logged; consistent with the data) |
| The close is the original movie teardown (`0x5C6DB4` → `0xC6BFF0`) | PARTIAL: the stream closed and decode stopped; the teardown functions themselves were not traced |

- **Cache:** the snapshot `generated/cache-snapshots/20261023-131453/` matches the pre-run hashes (re-checked after the run). The game rewrote `cache.dat` during the run (480248320 → 30409216 bytes); the pre-run copy is in the snapshot. Fonts unchanged.
