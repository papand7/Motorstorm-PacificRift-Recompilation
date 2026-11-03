# T177: aggressive PC-native race loading

Status: **PARTIAL**. The main limit is identified and its fix is built and tested offline. The new build has not been run in the game. Under 10 s is not supported by the evidence yet.

## What limits loading

Load screen to race entry, from the T161 game runs (`generated/analysis/t161/FAST_RACE_BENCHMARK.md` §14, §16; 2 runs per arm).

| Suspect | Finding | Label |
|---|---|---|
| Emulated synchronization | HLE `sys_lwcond` waits poll with `Sleep(1)`. Host wakeups cut about 85 s to about 20 s. Race entry 121-124 s to 41.7-42.1 s; the four asset loads 80 s to 13.6 s | VERIFIED |
| Artificial waits or pacing | The same `Sleep(1)` polling is the only large one found | VERIFIED |
| Shader compilation | 64 PSO misses 1.77 s + VS misses 1.08 s = 2.85 s, all in the first race frames, none during load (`RSX_SHADER_CACHE=1` is memory only) | VERIFIED |
| SSD / parallel I/O | 1,069 reads took 0.03 s in the track phase. Read-ahead and garage prefetch offer little | VERIFIED |
| Main-thread work | About 8 s of non-wait time in load stages, not attributed. May be serialized init or data processing | HYPOTHESIS |
| SPU decompression | About 1.3 ms wait per operation, measured in the poll era only | PARTIAL |
| GPU, stage overlap | Loading screen uses 1.7 s of render-thread time, with no evidence that it blocks the main thread. Stage overlap is not assessed, because the about 8 s is unattributed | PARTIAL |

Remaining wake-arm time, 20 s (run D1): track 4.8, env 0.9, vehicles 3.9, gap 0.6, characters and rest 3.4, PostLevelLoad to return 2.8, return to race entry 3.5.

## What was changed

Commit `b86a1073`, branch `agent/t177-fast-load` in `ps3recomp-t177`, based on T173 `b6f53f8`. Off unless `PS3_LWCOND_WAKE` is set.

Wakeups cost -2.8 % FPS and +0.88 cores in a light race (T161), which is why they stayed opt-in. The new `heavy_draws=N` option keeps wakeups for loading and uses the existing poll path for new waits during sustained heavy scenes.

- `include/ps3emu/frame_phase.h`: detector fed by the renderer's per-frame draw count. Heavy after 16 heavy frames in a row, light again after 64 light frames.
- It reads no guest state and only chooses between two host wait paths that are both correct, so a wrong answer costs speed, not behaviour. Waiters already registered are still woken.
- Readiness checks, gameplay timing, assets and SPURS synchronization are untouched.

## Offline results (VERIFIED)

`tools/test_lwcond_wake.py` through `env_t169.cmd`, final commit: 0 failures. It includes a C/C++ link check of the shared detector state and stress runs that flip the phase under load.

| 4-hop hand-off chain | us/op |
|---|---|
| Poll | about 4,700-4,800 |
| Wake | about 18 |
| Gate, loading | 19.5 |
| Gate, heavy scene | 4,569 |

So the gate keeps the wake speed for loading, at about 240× less hand-off latency than polling. This is a fixture measurement. It does not predict game load time; the game figure is the 85 s to 20 s above.

Build: rc=0, 0 errors, exe sha256 `86896155d5a6d31a1a36899cf575668ea013a7ce9f8d5a13ecba36c8a72c4113`, `heavy_draws=` present. Provenance is in `generated/t177/provenance.txt`. Runner `prepare r` and `envcheck` passed, with no launch.

## Projection (HYPOTHESIS)

| Step | Load screen to race entry |
|---|---|
| Existing port (poll) | about 85 s |
| Wake | about 20 s (measured, on an older build) |
| + persistent shader cache, warm | about 17.6 s (T116 ratio applied to 2.85 s) |
| + attributing and shrinking the about 8 s main-thread time | unknown |

Under 10 s needs about 8 s more than the known savings provide, and the unattributed time is the only known place to find it. The 2-5 s goal has no supporting path yet.

## Investigated options

- **Persistent shader cache:** `RSX_SHADER_CACHE=3` exists, config only. It is the best next structural step and is versioned by the existing cache. Garage-time PSO preparation would help only the first run, so try the cache first.
- **Warm FIOS cache:** `cache.dat` grows from 459 MB to 1.94 GB per session, and runners restart from a fresh HDD copy, so a warm cache has never been measured. It is the most likely real repeat-load gain that remains untested.
- **Checkpointing:** not feasible (T161 §5), so near-instant repeat loads have no path today.
- **PS3 reference:** no reliable measurement was found in the T161 report or in `docs/` and the analysis reports. Any PS3 claim must wait for one.

## Risks

- `heavy_draws=200` is unvalidated. If loading screens reach 200 draws for 16 frames, the gate falls back to polling and loading slows down. The game run must check this.
- The gate's FPS benefit is unmeasured. Waits during race start use wake until the detector turns heavy.
- The T173 jump-table fix in this base has not been validated at runtime, and the T173 launch remains unrun.
