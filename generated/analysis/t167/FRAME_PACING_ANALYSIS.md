# T167: 31 ms against 92 ms frames

Source: ps3recomp `8a12a61`. Game figures are existing logs (`frame_modes_t167.py`, `ev/frame_modes.txt`); medians in ms.

## Timelines

| Run, frames | State | Wall | Wait | Present | Record | Other |
|---|---|---:|---:|---:|---:|---:|
| T162 A1, few draws (10) | remote, normal | 31.2 | 23.3 | 0.10 | 0.1 | 4.3 |
| T162 D, few draws (10) | remote, slow | 91.8 | 82.9 | 0.20 | 0.1 | 4.5 |
| T162 A1, many draws (2116) | remote, normal | 46.0 | 0.0 | 0.20 | 4.9 | 21.0 |
| T162 D, many draws (1994) | remote, slow | 91.8 | 59.7 | 0.20 | 4.0 | 4.3 |
| T161, few draws | disconnected | 29.2 | 0.0 | | | 25 |

The brief's normal case was off in one detail: at few draws, normal is wall 31 with wait 23, not wait 31.

## What sets each figure

| Candidate | Finding | Status |
|---|---|---:|
| 30 Hz game pacing | Disconnected wall is 29.2 with wait 0, so game work sets that frame time, and 31.2 is not a 30 Hz deadline | VERIFIED |
| Present interval | Connected normal wall is 31.25 = the Remote Display Adapter's 32 Hz. The RTX 5060 reports 144 Hz | VERIFIED, adapter rates from the probe |
| Missed deadline | Not one miss: 92 is a stable state lasting hundreds of frames | VERIFIED |
| Guest RSX reference | Not the wait: it reproduces with no guest code | VERIFIED |
| Frame latency throttle | The swap chain's waitable object isn't what blocks: `[wait-diag]` shows the drain fence | VERIFIED |
| Fence | The primitive, not the cause (`GPU_WAIT_ROOT_CAUSE.md`) | VERIFIED |
| Compositor | Host-side hold; the remote compositor is the likely holder, not observed directly | HYPOTHESIS |

## Entry and exit

Slow frames do not start at a draw-count change. A2 went slow to normal at 15 s and back to slow at 39 s. D went slow at 104 s (guest frame 3166), normal at 135 s, slow at 139 s. In the probe, identical frames moved between 10.9 and 31.7 FPS from one cycle to the next. No exit trigger was identified.

## Consequences

- **Timing from a remote session is unsafe.** T161's and T162's comparisons need this in mind: T162 B1 and B2 sat at 98.5% slow frames and A1 at 0%.
- `run_guard_t167.py` now refuses a remote session unless told otherwise, and stops a run with more than 1% slow frames.
- Slow frames hide everything below 92 ms: in `val_perf_summary.txt`, `race2k` wall is 94 ms on every arm while its CPU cost varies from 9.2 to 14.6 ms.
