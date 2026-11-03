# T190 run matrix

| Order | Tag | Arm | Exe | Env vs T184 arm P | Status |
|---|---|---|---|---|---|
| 1 | Pp1 | P, control | `9e77bd4b…8453` | none (paths only) | **not launched**: preflight FAIL |
| 2 | Bb1 | B, optimized | same | `+PS3_VM_STORE_INLINE=1` | not launched |
| 3 | Pp2 | P | same | none | not launched |
| 4 | Bb2 | B | same | `+PS3_VM_STORE_INLINE=1` | not launched |

Launches used: **0 / 4**.

**Build.** `generated/analysis/t190/tools/build_t190.cmd` (the T183/T185 recipe), with:
- `PR=ps3recomp-t190` (`a26240c5`);
- `PO=port-t190` (`port-t161` plus T152's `MSPR_PPU_INLINE_STORES` option, root `20c3123`);
- `RECOMP_DIR=generated/ppu-t190-staging`;
- `-DMSPR_PPU_INLINE_STORES=ON`.

The build takes about 11 minutes; its log is `generated/analysis/t190/build_t190.log`. No relift.

**Exe differences from T184's exe** (`c32cd09d…`, `766d3575`; the same in both arms, so they do not confound P vs B):
- T188/T189 runtime and header code;
- page-gate loads (`PPU_PAGE_GATES`, implied by `PPU_INLINE_STORES`);
- the one-byte store gate on every lifted store.

P on this exe vs T184 P (68.51 ms) is a reference, not a control.

**Race configuration.** That of T184 arm P:
- intro skip, the `nav_policy_t161` route, the warm shader cache;
- stop at race entry + 75 s, a 205 s cap;
- `RSX_FRAME_PERF=12,1,100000`, PT frame sites (`cpath_sites.cfg`);
- `PS3_SPU_TASK_STATS`, `SPURS_BUSY_MS`, `PS3_SC_WAIT_MS` and `PS3_HLE_WAIT_MS` at 1000.

No frame dumps (as in T184 P).

**Measurement window** (fixed for all four runs): the last 55 s of each run's guest trace (race entry + about 20…75 s). It covers guest main-thread frames from one `72E1E0` entry to the next, with complete phase order. This is T183/T184's definition (`arm_s_t183.py`); `analyze_t190.py` reproduces T184 P exactly (802 frames, 68.51 ms).

**Raw logs, once run:**
- `generated/runs/*-t190-<tag>/` (`stderr.log`, `stdout.log`, `manifest.json`);
- `generated/analysis/t190/ab/runtime-<tag>-*/` (`cpu.jsonl`, `mem.csv`);
- per-run SPU and wait detail in `generated/analysis/t190/logs/arm_<tag>.txt`.
