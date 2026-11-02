# T180: race loading diagnostics

Status: **BLOCKED at the launch preflight. The launch was not used.** Why loading is slow is still not established, the 20 s wake result is not re-verified, and no load-time optimization was implemented. The build, the gate log and the corrected one-launch runner are ready.

## 1. Revisions

| Item | Value | Label |
|---|---|---|
| Code | `b55bf15f9defbb68c454910c0fcc6ecf77dbcf71`, `ps3recomp-t180`, branch `agent/t180-load-diagnostics` | VERIFIED |
| Base | T178-load `b352450d` (T177 adaptive wake `b86a1073` + `PS3_LOAD_PROBE`) | VERIFIED |
| Excluded | T174 `e528406f`, T176 `0eb257f6`, T179 `505a4d0a`, T171 `b282e262` are not ancestors | VERIFIED |
| Isolated build | rc=0, `build/motorstorm-t180` | VERIFIED |
| Exe sha256 | `6018d1f937470f92bbb2e1ceee86e2cb0a628fde50a64bb51faf45ed3a771a01`, pinned by the runner, `prepare r` passed | VERIFIED |
| Game data sha256 | `EBOOT.BIN` `218cd8aa...94af`, `PARAM.SFO` `7cc3a4bd...608e`, `EBOOT.elf` `bbb7fe25...b287`, read only | VERIFIED |

## 2. Run result: preflight blocker

`run_t180.py dryrun D x` returned rc=1:

```
PREFLIGHT FAIL: conflicting processes running: ['eabackgroundservice', 'eadesktop', 'epicgameslauncher',
'epicwebhelper', 'leoffice', 'llama-server', 'ollama']; free VRAM 3966 MiB < 6000
```

| Check | Result |
|---|---|
| Local console session (`query session`, `TerminalServerSession` False) | Pass |
| Free RAM, needs 16 GB | Pass, 26.6 GB |
| Free VRAM, needs 6,000 MiB | **Fail, 3,966 MiB** |
| Ollama, `llama-server`, LeOffice, Epic, EA closed | **Fail** |

The blocker can't be cleared from this session. Its process ancestry is shell → `claude.exe` → `LeOffice.exe`, so closing LeOffice as required would end the session that would launch and watch the run. Launching with it open would bypass the preflight. So nothing was closed, the lock file was not written, and no game process started.

The stage after the preflight (effective-config checks of the dry run) has not been exercised, because the preflight stops first.

## 3. Timeline and attribution

No new run. The only available figures are T178's, from T161 logs on an older build:

| Item | Time | Label |
|---|---|---|
| Load screen to race entry, poll | 85-90.8 s | VERIFIED, older build |
| Same, `PS3_LWCOND_WAKE` | 20-22 s | VERIFIED, older build |
| Same, T177 gate | Never run | BLOCKED |
| Main lwcond wait in asset stages | 7.29 s, overlaps tid 6 event-flag waits | VERIFIED, older build |
| Main usleep | 3.44 s in asset stages, about 5.1 s after PostLevelLoad | VERIFIED, older build |
| Main CPU | about 5.6 s, poll arm, functions unknown | PARTIAL |
| PSO and VS misses | 2.85 s | VERIFIED, older build |

These overlap and do not add up. The first-playable time, usleep and polling targets, CPU, race FPS and memory on this build are unmeasured.

## 4. Gate behaviour

Not observed in game. Added `[frame-phase] heavy=<0|1> draws=<n> min_draws=<n>`, one line per transition, which the runner timestamps. T178's log replay remains the only evidence: at most 107 draws per guest frame before the race, about 1,800 or more in it.

## 5. SPU scheduling

No new finding. The roughly 7.3 s FIOS wait is still unclassified as useful SPU work, latency or dependency stall (PARTIAL). No code was needed for async SPU coverage: `[load-probe]` gives signal latency and work, and the runner's `cpu.jsonl` samples every game thread's CPU every 5 s.

## 6. Optimizations

**None.** Phase 4 requires the run's evidence, and T178 showed each code candidate failing on existing evidence. T180 only adds the gate log, which changes no timing path.

Runner corrections against `t177/ab/run_t177.py` (`tools/make_runner_t180.py`):

| Problem | Correction |
|---|---|
| `RACE_STOP` was empty, so arms ran to the 205 s cap, not the race + 45 s the T177 request states | `{'D': 45.0}` |
| The critical-path trace was forbidden | Allowed, window `10:50` for the wake arm's race entry |
| `report=0`, so the profile was never written | `profile=5`, `report=5000`, `top=40` |
| Gate and probe lines not timestamped | Added to the controller's notes |
| No check of processes, RAM, VRAM or data hashes, and no second-launch guard | `env_preflight()` and the `launch_used.json` lock, written just before launch |

Arm D is T177 arm A plus `PS3_LWCOND_WAKE=1:poll_ms=100:stats_ms=1000:heavy_draws=200`, `PS3_LOAD_PROBE=1000`, `PS3_HLE_WAIT_MS=1000` and the trace. Stops: race + 45 s, 60 s stall, 185 s cap, 200 s timeout.

## 7. Offline validation

| Check | Result | Label |
|---|---|---|
| `test_t180_gate_log` | rc=0 | VERIFIED |
| `test_lwcond_wake` | PASS in the suite run, 4-hop hand-off poll 3,831.1 µs/op, wake 17.8, gate 19.2 loading, 4,353.5 heavy; synthetic, not a load-time claim | VERIFIED |
| Full suite through `env_t169.cmd` | 126 pass, 2 fail, 43 skip, 0 timeout | VERIFIED |
| Failures | `test_rt_pool_srv_layout`, `test_vpc_watch`, both inherited from the base. `test_spurs_wws_concurrency` passed this time; it is intermittent on the base | VERIFIED |
| Public audit, code | `--tree` on a copy, rc=0 | VERIFIED |
| Public audit, report | `--staged --private-reports`, see the commit | VERIFIED |
| Gate log overhead | Not measured. By source: one load and compare per frame when the gate is on, a print only on a transition | HYPOTHESIS |

## 8. Race-performance risks

- T180 changes no race path, apart from the per-frame compare above and a print per gate transition.
- The T177 gate's race FPS is unmeasured, and after a heavy race the next load polls until 64 light frames (about 2 s).
- **Diagnostic arm caveat:** `profile=` hooks every function, and the probe and trace add cost. Arm D's load time may be inflated, so it can't by itself confirm or refute the 20 s target; its attribution is the point. A longer load with the profile on is not a regression finding.
- Inherited: the base's T173 jump-table fix has no runtime validation.

## 9. Remaining bottlenecks

All unresolved: event-flag wait (compute or latency), main CPU functions, late usleep target, warm FIOS cache, shader misses at race entry.

## 10. Next run

**Not run, needs a clean environment.** From a plain terminal, after closing Ollama, `llama-server`, LeOffice, Epic, EA and Godot, and with the session still a local console, from the main checkout:

```
py -3 generated/analysis/t180/ab/run_t180.py dryrun D x
py -3 generated/analysis/t180/ab/run_t180.py launch D d1
```

The runner refuses a failed preflight and any second launch. Its output is the input to phases 3 and 4.

After that, the minimal A/B, which needs separate authorization: T180 gate without profile, trace or probe against T177 poll, one launch each. It decides the load time, race FPS and CPU the diagnostic arm can't.

| Arm D result | Next correction |
|---|---|
| High `sig_lat` relative to `work_ms` | Wake path |
| `work_ms` much greater than `work_mcyc` implies | `spu_dma.h` repeat-transfer sleep |
| Work dominates | Warm FIOS cache or parallelism |
| Main CPU concentrated in a few functions | Those functions |
| Gate never reaches or leaves loading state | Gate threshold |
