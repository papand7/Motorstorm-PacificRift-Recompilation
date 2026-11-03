# T177: in-game comparison request

**Not run. Needs authorization.** Requires a local console session (`query session`, not RDP), Godot closed and other workloads closed or suspended (`nvidia-smi --query-compute-apps` empty, including Ollama).

Exe sha256 `86896155d5a6d31a1a36899cf575668ea013a7ce9f8d5a13ecba36c8a72c4113`. Runner: `generated/analysis/t177/ab/run_t177.py` (main checkout), already prepared.

```
py -3 generated/analysis/t177/ab/run_t177.py launch <arm> <tag>
```

## Arms

| Arm | Setup | Question |
|---|---|---|
| P | Poll, same build | Baseline (existing port's behaviour) |
| U | Wakeups, no gate | Reproduces T161 on this build |
| W | Wakeups + `heavy_draws=200` | Same load as U, with FPS back at P? |
| C | W + `RSX_SHADER_CACHE=3`, cold | Cost of filling the cache |
| H | Same, warm; straight after C, same directory | The 2.85 s shader saving |

Two runs each of P, U and W, in rotated order. C then H, twice. That is 10 launches. Race-stage stop is at race + 45 s, so these runs do not show longer-term stability.

## Measures

- Load screen to race entry, and to first playable frame (correctly rendered, control available).
- The last `[rsx-hb]` against session end, since frame-time sums undercount a freeze.
- Light-race FPS and CPU cores against P.
- `[lwc-wake]` `gated=` counters: about 0 during load, rising in the race.
- Per-frame draw counts on loading screens and in the race, to validate the threshold of 200.
- `rsx-frame-perf` PSO and VS misses in the first race frames, for H against C.
- Same race, frame output and no new errors against P.

## Pass criteria

- W load within 10 % of U.
- W light-race FPS within 1 % of P.
- H saves at least 2 s against W.
- No crash, hang, missing asset or SPURS stall in any arm.

## Follow-ups, not yet in the runner

- **Profile run:** one W run with the tracer's `profile=` option, to attribute the about 8 s of main-thread time. This is the deciding input for under 10 s.
- **Warm FIOS:** W launched twice on one HDD copy (the runner now copies fresh per tag, so it needs a small change).

## PS3 reference

No reliable measurement exists in the project. Needed: a stopwatch or capture on real hardware from the same race selection to first playable, same track, 3 runs or more. Until then, report only native-against-native.
