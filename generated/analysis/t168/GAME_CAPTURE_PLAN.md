# T168: game capture plan

**Not run. Needs approval.** It answers the two questions offline evidence can't: are the 1,427 candidates real duplicates, and does the heavy scene replay anything?

| Item | Plan |
|---|---|
| **Executable** | A new build: the T161 game recipe on ps3recomp `800287c`. **Its hash doesn't exist yet**: record the SHA-256 after the build; the harness must refuse any other |
| **Do not use** | Any executable other agents are using |
| **Scene** | The T161 fast race benchmark |
| **Guest frames** | Light: race frames 40-499. Heavy: 600-690 |
| **Maximum runtime** | 480 s. T158 race entry took 145-165 s, and a slow boot under 205 s misses the heavy scene |
| **Runs** | One. A second only if the first ends before heavy frames |
| **Coordination** | First run `ListAgents` and check for running `run_t1xx.py` or `seq_*.sh`; no overlap with other A/B sessions |

## Settings

```
RSX_DRAW_DUP_DIAG=1
RSX_DRAW_DUP_EVENTS=4000
RSX_DRAW_DUP_FRAMES=2000
RSX_FRAME_PERF=<as in T161>
```

Everything else stays as T161 arm C. The rendering path is the same; timing is not comparable.

## Counters and expected evidence

| Line | Field | Tells us |
|---|---|---|
| `[dd-frame]` | `exec_replay` | **Above 0 with matching `first`, `count` and content: a real replay.** Event lines give the FIFO position |
| | `same_target` | Candidates that survive vertex addresses, `first` and all 512 constants |
| | `same_target_opaque`, `_blend` | Which kind |
| | `same_state_diff_const`, `other_target` | Instancing and multipass volume |
| | `offset_reuse` | Guest rewrites |
| | `table_full` | Above 0 means undercounting; the frame's result is partial |
| `[dd-fifo]` | `nested_calls`, `stray_rets` | Must stay 0, or the hazard is live |
| `[dd-event]` | Signature | For checking individual candidates. Offsets and hashes only |

| Outcome | Conclusion |
|---|---|
| `exec_replay` = 0, `same_target` near 0 | No duplicate rendering; close T168 |
| `exec_replay` = 0, `same_target` high | Guest or SPU-emitted. Disassemble renderablejob's list handling; nothing to fix in the walker |
| `exec_replay` above 0 | Defect. Reproduce in `test_gcm_fifo_replay`, then fix the mechanism |

**Remaining blind spot:** textures are hashed by binding, not by bytes, and a fragment program by address. Candidates still need checking before anything is called a duplicate.

## Stop conditions

- Runtime reaches 480 s.
- At least 90 heavy guest frames logged, which is enough.
- Executable hash mismatch: don't start.
- Crash or hang: stop and keep logs. No retry without a new approval.
- Another launcher starts or is running: don't start, or stop.

Logs stay under `generated/analysis/t168/`, private. Public reports get aggregates only.
