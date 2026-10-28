# Development and debugging

Build first ([BUILDING.md](BUILDING.md)). All logs, captures and traces below are written to Git-ignored
`generated/` and must stay there.

## Bounded runs

| Script | Use |
|---|---|
| `tools/probe_first_frame.ps1 -Seconds N -Name <name> [-FirstFrame] [-AudioPolicy silent]` | Run the game for at most N seconds (≤ 600) and keep stdout/stderr under `generated/logs/`. |
| `tools/trace_runtime.py "<spec>" --seconds N --name <name>` | Hooked-executable traces (functions, registers, HLE calls); see `ps3recomp/docs/TRACING.md`. |
| `tools/fast_startup.py` | Scripted route through the intro and frontend, used by the A/B runners. |
| `tools/thermal_supervisor.py` | Stops a run if the host overheats. |

Full game launches and builds are expensive and, for agents, need the owner's authorisation
([AGENT_WORKFLOW.md](AGENT_WORKFLOW.md)).

## Runtime switches

Defaults reproduce the original behaviour. Several switches exist only on agent branches until integrated;
the branch column says where to find them.

| Switch | Effect | Branch |
|---|---|---|
| `PS3_FTRACE` | Timeline of PPU/SPU/RSX spans, dumped at exit | T113 line and later |
| `PS3_CRITICAL_PATH_TRACE=1 \| start:secs[:path]` | Streaming timeline with host thread CPU; `ps3recomp/tools/cpath_report.py` | `agent/t134-ppu-spu-critical-path` |
| `PS3_SPURS_GUEST_MAXCONT=0` | One Wws lane instead of the game's `maxContention` | `agent/t134-…` |
| `PS3_SPURS_EVENT_SCHED=1`, `PS3_SPURS_KICK_WAKE=1` | Event-driven SPURS scheduling experiments | `agent/t134-…` |
| `PS3_USLEEP_SPIN` | Host sleep strategy for short guest sleeps | all MotorStorm lines |
| `PS3_SIM_PACE` | Simulation pacing experiment | `agent/t132b-framerate-independent` |
| `PS3_TEX_SNAPSHOT_EPOCH=1` | Skip re-hashing unchanged texture snapshots | `agent/t122-…`, `agent/t134-…` |
| `RSX_RT_READBACK=0` | Disable render-target write-back to guest memory (default on) | T113 line and later |
| `RSX_FP_SPAN=0` | Read fragment programs as a fixed 4096 bytes (old behaviour) | T113 line and later |
| `RSX_GUEST_SAMPLERS` | Guest sampler state per texture unit (bit mask) | T113 line and later |
| `RSX_VP_COMPACT=1` | Compact vertex-program upload path | `agent/t119-renderer-performance` |
| `RSX_TEX_MIPS=1` | Upload full mip chains | `agent/t133-…`, `agent/t137-…` |
| `RSX_RT_WINDOW=1` | Sample render targets through the declared window | `agent/t120-…`, T133, T137 |
| `RSX_DEPTH_STATE=1` | Guest depth-write, compare and stencil state | `agent/t120-…`, T133, T137 |
| `RSX_FP_PRECISION=1` | Clamp FX12/FX9/FP16 fragment results | `agent/t133-…`, T137 |
| `RSX_MSAA=1` | Multisampled 2x MSAA targets (needs `RSX_GUEST_SAMPLERS=15`) | `agent/t137-rsx-msaa-fidelity` |
| `CELLMARK_DUMP=N`, `CELLMARK_DUMP_DIR=…` | Dump N presented frames as BMP | all lines |

Check a switch on a branch with `git -C ps3recomp grep -n '"NAME"' <branch> -- '*.c' '*.cpp' '*.h'`.

## Tests

| Suite | Command |
|---|---|
| Project tool tests (synthetic, no game data) | `python tools/test_audit_public.py` and the other `tools/test_*.py` |
| Documentation links and Mermaid blocks | `python tools/check_docs.py` |
| ps3recomp offline suites | per task, e.g. `generated/analysis/<task>/tools/run_suite_*.cmd`; each test's header documents its build |

Some `tools/test_*.py` scripts take a private log as an argument (for example `test_spurs_lfqueue_init.py`); they
are not run in CI.

## Reports

Each task writes `generated/analysis/<task>/<REPORT>.md` and its analysis scripts in
`generated/analysis/<task>/tools/`. Label findings VERIFIED, PARTIAL, HYPOTHESIS or BLOCKED, and summarise them
in `docs/STATUS.md`.
