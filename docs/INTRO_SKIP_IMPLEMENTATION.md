# Intro skip: implementation (development only, off by default)

## What it does

`PS3_DEV_SKIP_INTRO=1` presses **Cross once** through `cellPadGetData` port 0:
- **When:** `PS3_DEV_SKIP_INTRO_DELAY_MS` (default 1500) after the guest opens a file whose path contains `gui_intro_`. That is the original `VideoStart` of the intro movie.
- **How long:** held 150 ms, and for at least 3 port-0 reads, then released.

It is input only. The original page decides what the press does. By the page data, Accept →
`TransitionPage(black)`, the same page the movie's own `VideoIsFinished` leads to (see
`ORIGINAL_INTRO_SKIP_ANALYSIS.md`).

It does not touch any of the following:
- the guest PC, guest memory, movie or Bink state;
- file data (EOF is not faked);
- clocks or frontend calls.

## Behaviour

| Property | How |
|---|---|
| Off by default | Nothing happens unless `PS3_DEV_SKIP_INTRO=1`, or the generic `PAD_PRESS_ON_OPEN` is set. |
| Waits for the intro | Armed only by the first matching guest open. `attract*.bik` and other files do not match. |
| One press, one release | A state machine `IDLE → ARMED → PRESSING → DONE`. It never re-arms; a later intro open does nothing. |
| No spam, no menu side effects | One 150 ms press. `black` and `loadscreen-garage` have no Accept handler. |
| Manual input kept | The press is OR'd over the host buttons: XInput, keyboard, `PAD_SCRIPT`. Nothing is masked. Only port 0. |
| Safe fallback | If the page ignores the press (wrong timing, wrong button), the intro plays to its natural end. Nothing retries. |
| Logged | Lines are prefixed `[pad-trigger]`: `on: …` at startup, then `armed by open '…'`, then `press 0x4000 (N ms after the open)`, then `release after N ms and K reads; done`. |

**Why the delay counts from the open:** the open is the guest's own `VideoStart`, so the page is
active by then. In run `20261023-123757-fcw-audio` the first decode followed the open by about
0.7 s. 1.5 s puts the press on a playing movie. Whether the GUI accepts input that early is
**UNKNOWN**. This is not claimed reliable until the validation run shows it.

## Files

**ps3recomp-int** (generic, title-agnostic):

| File | Change |
|---|---|
| `include/ps3emu/pad_trigger.h` (new) | Header-only one-shot trigger. Configured by `PAD_PRESS_ON_OPEN=<substring>,<mask>[,<delay_ms>[,<hold_ms>]]` or `pad_trigger_configure()`. |
| `runtime/ppu/ppu_fs.cpp` | `cellFsOpen` calls `pad_trigger_note_open(gpath)` after a successful open. |
| `libs/input/cellPad.c` | `cellPadGetData` port 0 calls `pad_trigger_apply()` after the host buttons are set. |
| `tests/test_pad_trigger.c` (new) | Unit test, all platforms. |
| `libs/input/tests/test_pad_trigger_getdata.c` (new) | Windows end-to-end test through `cellPadGetData`. |
| `CMakeLists.txt` | Registers both tests. |

**motorstorm (private):**

| File | Change |
|---|---|
| `port/main.cpp` | `dev_skip_intro()` maps `PS3_DEV_SKIP_INTRO` to `pad_trigger_configure("gui_intro_", 0x4000, delay, 150)`. |
| `tools/fast_startup.py` | Cache evidence (see below). |
| `tools/test_fast_startup_safety.py` | 6 new tests. |

**Cost when off:** one relaxed load and a branch per open and per port-0 poll.

## FIOS cache evidence (`tools/fast_startup.py`)

- **Every run:** writes `<run>/cache_state.json`, with the size and SHA-256 of every file under `generated/hdd1` before launch and after the stop, plus the list of changes. A summary section is added.
- **`--snapshot-cache` (opt-in):**
  - Before launch, it copies those files to a new `generated/cache-snapshots/<timestamp>/files/`, checks each copy's SHA-256, marks the copies read-only and writes `manifest.json`.
  - It never reuses a directory and never deletes anything.
  - It refuses to start, with nothing launched, unless the free space covers twice the copy size plus 1 GB.
  - The current cache is about 482 MB per snapshot.
- **Hashing time:** both modes add about 1–2 s of hashing before and after a run.

## Not done

- No exe was built: `build/motorstorm` and `generated/ppu` were not written. A new exe needs a build, using the existing `build_int` procedure, into a new directory.
- `tools/motorstorm_milestones.json` was not changed. A `pad_trigger_press` milestone would need approval.
