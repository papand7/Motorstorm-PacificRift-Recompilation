# T25 — vertex-buffer growth fix, clean performance baseline, SPU job timing

Secondary agent, offline only: no MotorStorm launch, no merge, no push. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

## 1. Worktrees, branches, HEADs

| Worktree | Branch | Base | HEAD | Content |
|---|---|---|---|---|
| `ps3recomp-t25` | `agent/t25-vpvb` | `307b08a` (primary's integration base) | **`23612494ecb10a610a845710fc5148356ffeccd1`** | vertex-buffer growth fix only (the isolated fix commit) |
| `ps3recomp-t25-perf` | `agent/t25-perf` | `3b38721` (T17/T18 perf branch, as T18's exe) | `991337d` | the same fix cherry-picked (`1595ee4`), `3e4696d` inline-load startup line, `991337d` `PS3_FTRACE_SPURS` |

Both were created from the shared object store with `git worktree add`. Neither touches the primary's worktrees or branches.
`git merge-tree` (read-only) results:
- `agent/t25-vpvb` merges cleanly with `agent/t24-render`, `t24-spu`, `t24-ppu`, `t24-build` and `agent/t24-infamous-ports`.
- `agent/t25-perf` merges cleanly with all of those except `t24-render`. That conflict in `rsx_d3d12_backend.c` already exists between `3b38721` and `t24-render` (the T17/T18 commits). It is not from T25 (§12).

## 2. Vertex-buffer defect — source evidence (VERIFIED)

At `307b08a`, in `libs/video/rsx_d3d12_backend.c`:
- `vp_vb` is one committed D3D12 **UPLOAD**-heap buffer, `cap × 256 B × 2` parities, persistently mapped: 192 MB at `cap = 393216`, allocated at 1320-1347.
- `vp_vb_grow` (5941) runs in `render_frame` right after `wait_for_gpu()`, when the frame overflowed (`vpvb_end_frame`, `include/ps3emu/vp_vb_budget.h`).
- It creates the new buffer and then does this at 5962:

  ```c
  memcpy((u8*)nm + parity*new_cap*256, (const u8*)s_d3d.vp_vb_mapped + parity*old_cap*256, s_d3d.vp_vb_offset);
  ```

- That is a CPU **read** of the current frame's vertices, up to a full 96 MB parity at the 393,216-vertex cap, from **write-combined** memory.

**What references the buffer.** Checked all `vp_vb` / `vp_vb_mapped` / `s_vpvb.cap` uses:
- Draw records hold only `vb_byte_offset`, a byte offset inside their parity half (`D3D12DrawRecord.vb_byte_offset`, written by the six `upload_*_vp` helpers at 8148-8558). They hold no resource pointer and no GPU address.
- The **only** vertex-buffer view is built once per replay at 6723 from `GetGPUVirtualAddress(s_d3d.vp_vb) + parity*cap*256`, size `cap*256`.
- The replay runs in the same `render_frame` call, after the growth and before `ExecuteCommandLists` (7409). `render_frame` (5976-7639) has no early return.
- CPU readers during the replay are diagnostics only: `rsxi_write_geom` 5575, `VP_TESTTRI` 6870, the per-draw dump 7107.
- The other `vp_parity` reader (1680) indexes `vp_cb`, not `vp_vb`.
- Nothing reads `vp_vb` after the parity flip (7263).

**Effect.** The ON-arm 1.6 s and 3.0 s gaps in T18 start at the `[VPVB] … grown: 393216 -> 1048576` line (T24 §5). The offline benchmark below reproduces the copy at 2.9–7.3 s.

## 3. Selected correction and why it is safe (VERIFIED offline)

**No copy. The old buffer is kept until the GPU has finished with it.** This is `vpvb_hold`, a header-only, GPU-free helper in `vp_vb_budget.h`.

| Step | Where (agent/t25-vpvb) | What |
|---|---|---|
| grow | `vp_vb_grow` 5957, `vpvb_hold_swap` 5980 | allocate + map the new buffer; the old buffer, at the old capacity, becomes `hold.frame`; nothing is read back |
| replay | bind 6744, diagnostics 5588 / 6892 / 7129 | `vp_frame_buf()` (504) = `hold.frame` if set, else the live buffer; GPU VA, parity base and `SizeInBytes` all use **that buffer's own cap** |
| submit | after `ExecuteCommandLists`, 7434 | `vpvb_hold_replayed`: `frame` → `retired` (the GPU may still read it) |
| retire | `render_frame` 6009, after its `wait_for_gpu()` and before any growth; shutdown 9438 | `vpvb_hold_idle` releases the retired buffer |

Why it is correct:
- Records keep offsets relative to their parity half, so the overflowing frame's records index the old buffer exactly as before.
- Later frames upload, through the unchanged writers (live `vp_vb_mapped`, live `s_vpvb.cap`), to the new buffer and bind it.
- The retired buffer is released only after the full GPU drain that `render_frame` already does at its start. The fix adds **no new GPU wait**.
- `vpvb_hold_swap` also handles the two orders that should never happen: a growth with a frame still unreplayed, and a retired buffer not yet released. In both it releases only buffers that hold no pending records (GPU idle). `vpvb_hold_replayed` has a fallback that waits before releasing; it is unreachable in the backend's order.

Smallest correct option:
- A GPU-side copy (`CopyBufferRegion` UPLOAD→UPLOAD is not allowed; it needs a DEFAULT intermediate) costs a submission and a wait.
- A CPU shadow buffer costs 192–512 MB more memory plus a write to every vertex.
- Neither is needed, because the replay can read the old buffer directly.

## 4. Before/after offline benchmark (VERIFIED)

The benchmark is `generated/analysis/t25/vpvb_grow_bench.c`: real D3D12, the T18 growth from 192 to 512 MB with one 96 MB parity already uploaded. The "after" path also replays the old buffer on the GPU (a 96 MB `CopyBufferRegion` into a DEFAULT buffer) and releases it after the fence. Run 1 is in `vpvb_grow_bench_run1.txt`.

| rep | before: create+map | before: WC copy | before: grow step | after: grow step | after: GPU replay of old buffer (fence) | after: deferred release |
|---|---|---|---|---|---|---|
| 0 | 36.5 ms | 3219.5 ms | **3264.2 ms** | **43.4 ms** | 0.6 ms | 3.1 ms |
| 1 | 43.7 ms | 7244.3 ms | **7291.4 ms** | **36.4 ms** | 0.6 ms | 3.0 ms |
| 2 | 29.8 ms | 2930.1 ms | **2966.4 ms** | **36.3 ms** | 0.6 ms | 3.0 ms |

- The growth step falls from 2.97–7.29 s to 36–43 ms, which is the allocation alone. The read-back is gone, not moved behind another wait.
- T24's earlier benchmark measured 3.3–4.1 s for the copy alone.
- First touch of the new buffer's untouched 416 MB costs ~78 ms (T24 benchmark). It is spread over the frames that fill it.

## 5. Regression tests (VERIFIED)

The compiler setup is the T17 shim (`CC=scratch\t17\cc_shim.cmd`, empty `m.lib`), via `scratch\t25\run_tests.cmd`. Every runner's output was checked for `SKIP`.

- **`tools/test_vpvb_hold.py`**, new, 0 failures. Its harness is `libs/video/tests/test_vpvb_hold.c`.
  - A fake GPU executes submitted replays only at `wait_for_gpu`, reads every recorded vertex through the bound buffer, capacity and parity, and counts reads of released buffers.
  - Released buffers stay allocated, so a late read is detected.
  - Cases covered:
    - initial allocation;
    - growth 393216 → 1048576 with the overflowing frame's draws pending;
    - four consecutive growths;
    - a second growth before a replay;
    - failed allocation;
    - shutdown cleanup;
    - the late-release fallback;
    - vertex integrity, offsets and binding;
    - release exactly once and no use after release;
    - one GPU wait per frame (no added stall).
  - Wiring checks (12):
    - no `memcpy` or read of the old mapping in `vp_vb_grow`;
    - order drain → retire → grow → bind → submit → replayed;
    - the bind uses `fb.res` / `fb.cap`;
    - no live-mapping reader is left;
    - the six writers are unchanged;
    - shutdown releases after its drain.
  - Mutation check: a header that releases the old buffer at swap fails 9 checks (`scratch/t25/cc_mut.cmd`).
- **`tools/test_draw_rejection.py`**: updated for the new bind and growth checks, 0 failures.
- **All 17 other runners that inspect `rsx_d3d12_backend.c` / `vp_vb_budget.h`**: 17/17 exit 0, none skipped (`scratch/t25/tests_run3.txt`).
- On `agent/t25-perf`:
  - the same 19 pass (`tests_perf_run1.txt`);
  - `test_ftrace_spurs` and `test_rt_vis_trace` (343 checks) pass;
  - `test_ppu_trace` passes;
  - `test_spurs_*` exit 0 but their harnesses SKIP (POSIX fixtures), so `cellSpurs.c` was compile-checked directly.
- **Release-flag compiles** with clang-cl: `rsx_d3d12_backend.c` on both branches, `cellSpurs.c` and `ppu_loader.cpp` on `agent/t25-perf`. No errors and no new kind of warning (`cc_*.txt`).
- `audit_public.py --staged` before each commit reports the same 25 items as the untouched `307b08a`. All are pre-existing files (PDF, icons, SPU test fixtures); none is a T25 file.

## 6. Remaining GPU synchronization risks

- **Full drain assumption (VERIFIED, by design).** Release relies on `render_frame` draining the GPU at its start. A future overlap mode, such as upstream's RF_ASYNC or frame-in-flight, must release on a per-frame fence instead. `vpvb_hold` keeps one retired slot, so it would need a small queue.
- **Device removal (pre-existing).** `wait_for_gpu` returns after 3 × 2 s even without the fence completing (TDR path). The retired buffer would then be released while the GPU is lost. This is the same pattern as every other release after `wait_for_gpu` in the backend.
- **Peak memory (unchanged).** Old and new buffers coexist for one frame (192 + 512 MB UPLOAD), as they did during the old copy, now for ~1 frame longer.
- **New CPU readers.** Any future diagnostic that reads `vp_vb` during the replay must use `vp_frame_buf()`. `test_vpvb_hold.py` fails on a new direct `(const u8*)s_d3d.vp_vb_mapped` or `(char*)s_d3d.vp_vb_mapped` read.
- **Not addressed (HYPOTHESIS, T24).** Why one frame emitted 790 draws and reached the 393,216-vertex cap in the ON runs. The fix makes the growth cheap; it does not explain the overflowing frame.

## 7. `RSX_RTVIS` and the inline-load fast path (VERIFIED)

1. **Where.** `runtime/ppu/ppu_loader.cpp:1596-1608` (307b08a).
   - A static constructor sets `vm_inline_ok = 0` if **any** of these is *set*: `PPU_RWATCH`, `PPU_FORCE_READ_ADDR`, `YDKJ_RWATCH`, `PPU_RVAL`, `PPU_RVAL64`, `PPU_HOTMAP`, `PPU_HOTREAD`, `PPU_SPINBT`, `RSX_RTVIS`. A `PS3_TRACE` read watch (`ppu_trace_wants_reads`) does the same.
   - The test is `getenv(var) != NULL`, so `RSX_RTVIS=` or `RSX_RTVIS=0` still turns the fast path **off**. The variable must be **absent**.
2. **Scope.** It covers all lifted PPU loads in every generated function. `generated/ppu-hooked-staging/ppu_recomp.h:177` maps `vm_read8/16/32/64` to `vm_read*_inl` unless `PPU_NO_INLINE_LOADS` is defined; it is not defined in the build.
   - The staging contains 5,742,000 `vm_read32`, 465,138 `vm_read64`, 158,717 `vm_read8` and 41,949 `vm_read16` call sites. Every one tests `vm_inline_ok` first (`tools/ppu_lifter.py:180-190`).
   - Loads from HLE / runtime C code and **all stores** (`vm_write*`) are out-of-line regardless of the flag.
   - The out-of-line `vm_read*` adds the bounds check, hotmap, null-page report, `PPU_FORCE_READ_ADDR`, rwatch and the per-thread HOTREAD spin detector on every load.
3. **Generated code, runtime, or both.** Runtime only: the generated code always contains both paths, and one global picks between them.
4. **Regeneration or recompilation.** Neither. Removing `RSX_RTVIS` from the environment is sufficient, and is required in its absence-not-zero form. `RSX_RTVIS` also enables RTVIS bookkeeping in `cellGcmSys.c:4198-4290`: per-draw / submit / complete hooks and per-read checks of the watched window. That also goes away.
5. **Verifying the fast path.**
   - `agent/t25-perf` `3e4696d` prints one startup line, `[vm] inline guest loads on`, or `OFF (<var> is set)`.
   - `ab_report.py` reports it, and `run_t25_ab.ps1` refuses to launch with any of the ten disabling variables.
   - Older exes (T17/T18) print nothing; for them the proof is the env in `manifest.json`.
6. **Other flags that change execution cost** (in the T18 profile unless noted):

| Flag | Effect | Clean run |
|---|---|---|
| `RSX_RTVIS` | inline loads off + RTVIS hooks | **remove** |
| `PPU_RWATCH`, `PPU_FORCE_READ_ADDR`, `YDKJ_RWATCH`, `PPU_RVAL(64)`, `PPU_HOTMAP`, `PPU_HOTREAD`, `PPU_SPINBT`, `PS3_TRACE` read watch | inline loads off (not in T18) | keep absent |
| `RSX_RT_READBACK=1` (+`_LOG`) | GPU copies of orphan RTs + CPU write-back; **guest-visible** (CPU sees RT results, e.g. exposure) | keep as T18 (functional, same in both arms); its cost is a separate question |
| `PS3_FTRACE` (+`_MIN_US=200`, `_SYNC`, `_USLEEP_REG`, `_SPURS`) | QPC + record per syscall/usleep run/SPU wait ≥ 200 µs, label/vblank/drain instants, SPURS kick/pick/PM | keep (needed for the metrics), identical in both arms |
| `--capture-rsx` at depth+85 s | RSXI frame capture (GPU waits, dumps) at ~124 s, **after** the 30–120 s window | keep (ends the run); outside the window |
| `RSX_HEARTBEAT_MS=1000` | one log line / s | keep |
| `PS3_TEX_SNAPSHOT=1` | the default (1); functional | keep |
| `PS3_VP_VCACHE`, `PS3_TEX_SNAPSHOT_SHARE` | T17 frame-prep optimisations; default **1** | leave unset (default) |
| `PS3_USLEEP_SPIN=1` | sub-ms usleeps spin (`SwitchToThread` to a QPC deadline); ≥ 1 ms sleeps use a legacy (non-HR) waitable timer instead of the HR timer (`sys_timer.c:263-313`) | Run B only |
| `PS3_VERBOSE`, `PS3_PRESENT_DIAG_MS`, `PS3_DRAW_ACCT_MS`, `RSX_SHADER_TRACE`, `PS3_FSLOG_READS`, `FS_CALLER`, `RSXI_EVENT` | chatty logging | off (fast profile) |

## 8. Clean performance configuration (Run A)

- **Exe:** `build\motorstorm-t25-perf-991337d\MotorStormPacificRiftRecomp.exe` (§11). It is `3b38721` plus the fix, the `[vm]` line and the SPURS spans, compiled against the same PPU staging as T18.
- **Env** is the T18 profile with these changes:
  - `RSX_RTVIS` absent;
  - `PS3_VP_VCACHE` / `PS3_TEX_SNAPSHOT_SHARE` unset (default on);
  - `PS3_FTRACE_SPURS=1` added.
  - Everything else is as T18: `FIRST_FRAME=1`, `FIRST_FRAME_AUDIO=native`, `GCM_INTERACTIVE=never`, `PS3_DEV_SKIP_INTRO=1`, `PS3_VERBOSE=0`, `PS3_FC_WATCHDOG_MS=3000`, `RSX_HEARTBEAT_MS=1000`, `RSX_RT_READBACK=1`, `RSX_RT_READBACK_LOG=160`, `PS3_TEX_SNAPSHOT=1`, `RSXI_MAX_MB=512`, `PS3_FTRACE=30:90:…`, `_MIN_US=200`, `_SYNC=1`, `_USLEEP_REG=29`.
  - Inherited game variables are scrubbed.
- **Cache:** a private copy of the pinned baseline `generated\cache-snapshots\20261025-132231`, hashes checked, made per run as `scratch\t25\hdd1-<seq>-<arm>`. The run goes through `scratch\t25\t25_launch.py`, which points `fast_startup`'s `HDD1` there and refuses the shared path. **Shared `generated\hdd1` is never touched**, unlike T18, which swapped it.
- **Proof checks after the run:**
  - `[vm] inline guest loads on` in stderr;
  - the manifest env;
  - exe sha256 equal in both runs (`ab_report.py` prints the env difference and "same exe").

## 9. SPU job timing instrumentation (implemented; PARTIAL by design)

The instrumentation is `agent/t25-perf` `991337d`, enabled with `PS3_FTRACE_SPURS=1`, and it only records. Each event carries the workload's kick sequence number:

| Event | Kind | Where | Fields |
|---|---|---|---|
| batch submission | 23 `SPURS_KICK` | `cellSpursReadyCountStore` (1912), Swap/CAS when written (1941), after the guest-visible store | who = SPURS EA, a = wid \| value<<8, b = seq |
| worker pickup | 24 `SPURS_PICK` | coordinator, when a lane is given the workload (1814) | a = wid \| lane<<8 \| kicked<<16, b = seq |
| execution start/end on the lane | 25 `SPURS_PM` | worker, around `spu_run_policy_module` (1747) | a = wid \| lane<<8 \| min(polls,0xFFFF)<<16, b = seq at pick |
| SPU compute vs waits inside the run | existing 4 `SPU_BUSY` / 3 `SPU_WAIT` | `spu_channels.c` | (unchanged) |
| main-thread wake | existing 2 `USLEEP` end, per lr | sys_timer | (unchanged) |
| next frame continuation | existing 9 `FLIP_REQ` | cellGcm | (unchanged) |

Off, each hook costs one load and a branch. On, there is one 32-byte record per kick, pick and policy-module run, in the bounded `PS3_FTRACE` buffer (`CAP`, window). No change to scheduling, admission, contention, atomics or memory.

`generated/analysis/t25/ab_report.py` separates the latencies per workload:
- **kick → pick:** scheduler latency, including the coordinator's 1 ms CV timeout when no wake reaches it;
- **pick → PM start:** worker wake;
- **PM residency:** median and p95, plus lane busy share;
- **main thread:** CV back-off, ref wait, pre-flip silence and the busy remainder per frame;
- **RSX:** host-thread CPU, vertex and texture-snapshot time per frame;
- **CPU:** process cores and top threads, plus host CPU % from typeperf.

The pairing was checked on a synthetic trace (`scratch/t25/fake_run`): 1200 µs, 50 µs and 3000 µs came back exactly. On the T18 runs it reproduces T18/T24: 75.2 ms median frame, 13.17 FPS, 26.8 ms CV back-off and 21.2 ms pre-flip silence.

**BLOCKED / not done:**
- **Per-job completion inside a policy module.** The WWS job manager runs individual jobs inside the guest SPU kernel, and completion is a guest-memory write, likely an atomic PUTLLC. A completion-write watch belongs in `runtime/spu/spu_channels.c` (PUTLLC) and `spu_dma.h`. `spu_channels.c` is being changed by the primary's SPU-atomics agent (`agent/t24-spu`), so this part is stopped (§12).
  - Until then, "notification latency" is bounded by PM end → the main thread's next `USLEEP` run end at the job-wait lr.
  - "Polling latency" is the `USLEEP` granularity: ~506 µs per call with the HR timer, which Run B removes.
- **SPURS lane threads have no name in the trace.** Lane CPU comes from `performance.json`'s unnamed top threads plus PM residency, not from a per-lane CPU counter.

## 10. Proposed two-run experiment (prepared, NOT run)

- **Wrapper:** `scratch\t25\run_t25_ab.ps1`. It parses without errors; `-DryRun` runs all preflight checks and launches nothing.
  - Run 1 is `-Arm A -Seq 1`, Run 2 is `-Arm B -Seq 2`. Seqs 3 = B and 4 = A exist only for an optional ABBA repeat that needs separate approval.
  - The arms differ **only** in `PS3_USLEEP_SPIN=1` (B).
  - Before launch it checks: the same pinned exe hash, re-checked right before launch; a fresh private hdd1 from the same snapshot; the same target, capture and trace window; no other launcher or game process; at least 4 GB free; no inline-disabling variable.
  - Limits: `fast_startup --timeout 150`, wrapper kill at 210 s.
- **Analysis:**

  ```
  python generated/analysis/t25/ab_report.py --host scratch\t25\ab1-a-*\host.csv --host scratch\t25\ab2-b-*\host.csv generated\runs\*-perf-t25-ab1-a generated\runs\*-perf-t25-ab2-b
  ```

  - The window is 40–118 s, the garage steady state. Loading gaps over 250 ms are excluded per `scratch/t18iso/gaps.py`.
  - Outputs:
    - FPS with and without gaps;
    - frame median / p95 / p99;
    - main-thread waits, CV back-off and ref wait;
    - pre-flip silence (Present spin);
    - main busy;
    - RSX CPU, vertex and texture-snapshot time;
    - SPURS kick→pick, pick→PM and PM residency;
    - process cores, top threads and host CPU %;
    - the env difference and same-exe check.
- **Falsifiable expectations:**
  - **Run A vs T18 (HYPOTHESIS).** Inline loads on lowers main busy time below T18's ~46 ms/frame. If FPS stays ~13 and main busy does not drop, the PPU load path is not a limit.
  - **Run B vs A (HYPOTHESIS, T24 C2).**
    - Main CV back-off per frame drops by ≥ 2 ms, and FPS rises by at least the same fraction.
    - Process CPU rises by roughly one core or less.
    - If CV back-off falls but FPS does not, sleep latency is not on the critical path.
    - If the CPU cost exceeds ~1 core for < 5 % FPS, keep the HR timer as the default.
- **Stop rule.** One launch per approval. Nothing is relaunched automatically, and a failed run is reported, not retried.

## 11. Dedicated executable

- `build\motorstorm-t25-perf-991337d\MotorStormPacificRiftRecomp.exe`, built from `ps3recomp-t25-perf` at `991337d`.
- SHA-256: **`104ff7534ff353a145fb74d4971591f57a243148b1c252d1059967a08e48ab01`** (hashed after the build; re-hashed before any launch, pinned in `run_t25_ab.ps1`).
- Build:
  - The folder is a copy of `build\motorstorm-t18iso-3b38721`, retargeted, with the old folder name replaced in every non-`.log` text file.
  - `scratch\t25\build_exe.cmd` reconfigures it with `-DPS3RECOMP_DIR=ps3recomp-t25-perf`, the same `RECOMP_DIR` (`generated\ppu-hooked-staging`, read only) and `PORT_HLE_NIDS_GENERATE=ON`, which writes into the build folder.
  - Log: `scratch\t25\build_exe.log`.
- The shared staging was hashed before and after the build (`scratch\t25\staging_before.txt` / `staging_after.txt`).
- No shared build folder or exe was written.

## 12. Coordination with the primary agents

- No primary worktree, branch, shared build folder, shared exe, `generated/hdd1` or `port/main.cpp` was modified. Primary branches were only read (`git log`, `git diff --name-only`, `git merge-tree`).
- **Overlaps:**
  - `rsx_d3d12_backend.c` is also changed by `agent/t24-render`. The fix branch `agent/t25-vpvb` merges cleanly with it.
  - `agent/t25-perf` conflicts with `t24-render` only through the T17/T18 commits, which `3b38721` already conflicts with. Resolving that belongs to whoever integrates the T17 switches.
  - `runtime/ppu/ppu_loader.cpp` is also changed by `agent/t24-spu`. `3e4696d` merges cleanly with it.
  - `runtime/spu/spu_channels.c` (PUTLLC) is owned by `agent/t24-spu`. The per-job completion watch was **not** added there (§9, BLOCKED until that work lands).
  - `libs/spurs/cellSpurs.c` is changed by no primary branch. The T25 hooks there only record.
- **Integration suggestion (needs approval):**
  - `agent/t25-vpvb` `2361249` is self-contained, on the primary's base `307b08a`, with tests. It is the candidate to integrate.
  - `3e4696d` and `991337d` are optional diagnostics.

## 13. Results of the two authorized runs (2026-10-25)

The user authorized exactly two launches, and both have been done. Neither will be repeated without new authorization.
- Wrapper: `scratch\t25\run_t25_ab.ps1`. Exe `104ff753…`, re-hashed before each launch.
- Private hdd1 copies `scratch\t25\hdd1-1-a` and `hdd1-2-b`. The shared `generated/hdd1` was not touched.
- Runs:
  - A: `generated/runs/20261025-183416-perf-t25-ab1-a`;
  - B: `generated/runs/20261025-183635-perf-t25-ab2-b`.
- Both ended with `milestone_reached` (exit 0). The wrapper did not have to kill either run, and no process was left behind.
- `ab_report.py` env difference: only `PS3_USLEEP_SPIN` (plus each run's private `PS3_HDD1_ROOT`). Same exe.
- Report files: `scratch/t25/report_{A_42-118,A_67-118,B_67-118}.txt`.

**Window caveat.** B reached the garage 25 s later than A: `depth_surface_created` at 63.2 s vs 38.3 s, `first_original_draw` at 26.1 s vs 13.3 s. Over the default 40–118 s window, B therefore mixes intro and loading frames into the result, which made it look like 19.8 FPS with a 31 ms median. That comparison is invalid. The table below uses **the same garage window, 67–118 s, for both runs** (A over 42–118 s gives the same numbers).

| Metric (garage, 67–118 s) | T18 ab2 (RTVIS on) | **A** clean | **B** + USLEEP_SPIN | B − A |
|---|---|---|---|---|
| inline guest loads | off | **on** (`[vm]` line) | **on** | |
| FPS (all = excluding gaps) | 13.2 | **13.10** | **13.74** | +4.9 % |
| frame median / p95 / p99 ms | 74.7 / 82.9 / 88.2 | 75.5 / 83.5 / 87.2 | 72.3 / 78.9 / 82.8 | −3.2 / −4.6 / −4.4 |
| gaps > 250 ms | 1 (1.57 s, VPVB growth) | none | none | |
| main waits / CV back-off ms/frame | 27.4 / 24.7 | 27.4 / 24.7 | 26.1 / 23.3 | −1.3 / −1.5 |
| main busy ms/frame | 47.3 | 47.8 | 46.0 | −1.8 |
| pre-flip silence (Present spin) ms | 21.5 | 23.3 | 22.2 | −1.1 |
| RSX CPU / vertex / texture snapshot ms | 31.3 / 12.5 / 11.1 | 31.3 / 12.3 / 10.7 | 31.3 / 12.3 / 10.9 | 0 |
| process cores / host CPU % | 2.75 / 28.5 | **2.68 / 25.0** | **3.94 / 34.5** | **+1.26 cores** |

SPURS, instance `0x1003F180`, kick→pick / pick→PM start / PM residency (median, p95) in µs:
- wid 1, A: 2349 (11675) / 5.0 / 780 (4249).
- wid 1, B: 2761 (12694) / 5.0 / 765 (4769).
- wids 0 and 2: kick→pick 16–29 µs median, PM ~15 µs median.
- Lane busy share: wid 1 0.6, wid 2 0.3.

Findings:
- **Inline loads (VERIFIED):**
  - On in both runs.
  - Removing `RSX_RTVIS` changed nothing measurable: 13.10 vs T18's 13.17–13.21 FPS, and main busy 47.8 vs 46–47 ms.
  - So the out-of-line load path is **not** a frame-rate limit.
- **Vertex-buffer fix (VERIFIED offline; NOT exercised in-game):**
  - Neither run overflowed the buffer, so no `[VPVB] … grown` line appeared and no garage loading gap occurred.
  - Both runs stayed at the initial 192 MB buffer.
  - Its effect is therefore unmeasured in-game; T18 needed the rare 790-draw frame to trigger it.
  - No buffer-lifetime symptom appeared: no `wait_for_gpu STUCK`, device removal, fatal error or growth failure.
  - **None of the A/B difference can be attributed to the fix.**
- **`PS3_USLEEP_SPIN` (VERIFIED, small):**
  - +4.9 % garage FPS; median frame −3.2 ms; main CV back-off −1.5 ms per frame.
  - Costs **+1.26 cores**: guest thread 12 sits at 0.98 cores, and host CPU rises from 25 % to 34 %.
  - Boot to the garage is **25 s slower**; spinning appears to starve other threads during the intro and loading.
  - SPURS latencies are unchanged.
  - Short-sleep latency is a minor contributor, not the 75 ms limit. Do not make spinning the default.
- **New lead (HYPOTHESIS):** workload 1 waits 2.3–2.8 ms (median) and 11.7–12.7 ms (p95) from kick to lane pick, while its PM run is ~0.78 ms. Lane wake is 5 µs. The wait is admission or queueing in the coordinator (one active instance per workload at `maxcont=1`, the 1 ms CV timeout), not SPU compute. Next offline step: correlate wid 1 kicks with main's CV-back-off waits per frame.
- **Crashes and visual check:**
  - No crash or fatal error.
  - The RSXI frame at depth+85 s matches T18's structurally in both runs: 721 events, 619 draws, the same draw targets, vertex counts and shaders, and identical RSXI warnings. Only per-frame fragment-constant values differ.
  - No images were captured (`--capture-snap none`, as in T18), so pixel-level regressions are not checked.

**Integration recommendation for `2361249`.**
- It is safe to integrate as an isolated robustness fix. It is offline-verified and tested, merges cleanly with every `agent/t24-*` branch, and shows no regression in two garage runs.
- It does **not** raise steady-state FPS. It only removes the multi-second stall when the 790-draw frame triggers a growth.
- To show the in-game benefit, a later approved run needs a frame that overflows the buffer, or a lower initial capacity in a test build only.
