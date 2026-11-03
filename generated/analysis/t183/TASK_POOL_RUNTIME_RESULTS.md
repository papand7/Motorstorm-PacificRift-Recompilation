# T184 SPU task pool: runtime results

I ran arm P once on 2026-11-03. Arm P is arm S plus `PS3_SPU_TASK_POOL=1`, on the same exe.

The pool reuses host threads as designed. The race frame fell from **70.40 to 68.51 ms (14.21 → 14.60 fps, −1.9 ms)**. That is about a third of T183's 5.9 ms upper bound.

`cellSpursCreateTask` only fell from **297 to 262 µs per call**, so creating host threads was a small part of its cost. Most of the cost is something else on the caller's side.

The run was stable. Task counts and anomaly counts are the same as in S. Rendering and gameplay correctness are not verified, because no frames were captured.

## 1. Executable

Both runs used `exe_r` = `build/motorstorm-t183/MotorStormPacificRiftRecomp.exe`:
- SHA-256 `c32cd09dd02447a6a4791af69a84c4aa653639f31ee5d3d8129a1324d6119b97`;
- 410,976,256 bytes;
- built from `ps3recomp-t183` commit `766d3575`.

`launches_used.jsonl` records that hash for both S and P. The exe was not rebuilt or changed. VERIFIED.

## 2. Preflight

All checks passed. VERIFIED.

| Check | Result |
|---|---|
| Session | `query session`: `>console … Active`; `TerminalServerSession` False |
| Exe and game data | runner pin and `exe_r` match `c32cd09d…9b97`; EBOOT.BIN `218cd8aa…94af`, PARAM.SFO `7cc3a4bd…608e`, EBOOT.elf `bbb7fe25…b287`, same as S |
| VRAM | 7,540 MiB free at launch; GPU 1 %, 545 MiB in use before launch |
| Competing load | no llama-server, Ollama, EA or Epic processes, and EABackgroundService stopped. The runner's open-app check showed only `leoffice`. Over 5 s the busiest process used 0.09 cores |
| Arm flags | `envcheck`, B vs P: S's 7 diagnostic keys plus `PS3_SPU_TASK_POOL=1`. Compared with S's recorded argv, the only differences are `PS3_SPU_TASK_POOL` and the per-run paths (HDD, VFS, pad) |
| Bounded logging | same as S: no new diagnostic flag, and PT limits unchanged (`cpath_sites.cfg`) |
| Stop | race + 75 s, with a 205 s timeout |
| One arm | the runner starts one arm per call, and the cap file had 1 of 5 used |

Runner change: `generated/analysis/t183/ab/run_t183.py` gains one line, `ARMS['P'] = ('r', {**ARMS['S'][1], 'PS3_SPU_TASK_POOL': '1'})`, and `envcheck` also lists P. It is private, as before, and a backup is kept beside it.

## 3. Launch count

**1.** Run `20261103-061935-t183-Pp1`:
- wall 114.6 s;
- the controller stopped it at race + 75 s;
- the wrapper reported `exited_error` (exit 1) because the controller killed the process, the same as S and T182 B.

There were no retries and no other arms. In total, T183 and T184 used 2 launches (S, P).

## 4. Task-pool configuration and pre-launch review

Code: `runtime/spu/spu_task_pool.h` with `runtime/spu/spu_workload.c`, both unchanged since T156.

| Point | Finding | Label |
|---|---|---|
| Reuse and lifecycle | Each worker has its own job slot and condition variable. Submit fills the slot and wakes the worker while holding the pool lock. A worker re-checks its slot under the same lock before sleeping. After 32 idle workers, extra ones retire | VERIFIED (code) |
| Ordering and concurrency | The pool never queues: with no idle worker, a run gets a new thread at once. Every run therefore starts as soon as it is submitted, as with thread-per-task, and the concurrency limit is unchanged | VERIFIED (code) |
| Guest-visible synchronization | Unchanged. `spu_taskset_task_exited` and completion signalling run inside the job, before the worker can be reused | VERIFIED (code) |
| Lost wakeups, reuse vs completion | Wake is issued under the lock. The job memory is freed inside the run, and the slot is cleared under the lock | VERIFIED (code) |
| Stale state | After each run: stack lines leave the lock-line and MFC reserver sets, `spu_channels_thread_reset` clears the reloc, job, wait-stat, trampoline and PCH thread-locals and the stats pointer, and the taskset lock flag is cleared. Each run gets a fresh or per-taskset local store and a fresh context, as before. Leftover thread-locals are diagnostic only (interpreter rings, `s_wait_exit_ms` for the `ran=` log). The cri image 22 stays on its own thread | VERIFIED (code) |
| Errors | If creating a pool thread fails, submit returns 0 and the old CreateThread path runs. Shutdown exists but nothing in the game calls it; the process exits with the workers parked | VERIFIED (code) |
| Pool counters | `spu_task_pool_get_stats` is never printed in the game, so reuse is measured indirectly (§6) | VERIFIED (code) |

Offline tests, run through `env_t169.cmd` on `ps3recomp-t183`:

| Test | Result |
|---|---|
| `tools/test_spu_task_pool.py` | seeds 1, 7, 12345: 2,020 checks each, 0 failures |
| `tools/test_spu_task_log.py` | 0 failures |
| `tests/test_spu_task_stats.py` | 0 failures |

The pool implementation was not modified.

## 5. Performance against arm S

Window: the last 55 s of each trace. Frames are counted where every phase marker is present (S 781 frames, P 802). Tool: `tools/arm_s_t183.py` with `T183_TAG=Ss1|Pp1`. VERIFIED.

| Metric | S | P | Δ |
|---|---:|---:|---:|
| Average race FPS | 14.21 | **14.60** | +0.39 |
| Mean frame | 70.40 ms | **68.51 ms** | **−1.89** |
| Median frame | 69.91 | 68.14 | −1.77 |
| p95 / p99 | 76.92 / 84.26 | 74.71 / 82.16 | −2.2 / −2.1 |
| `cellSpursCreateTask` on tid 1 | 84.3 ms/s, 284 calls/s, **297 µs/call → 5.93 ms/frame** | 76.5 ms/s, 292 calls/s, **262 µs/call → 5.24 ms/frame** | −35 µs/call, −0.69 ms/frame |
| Havok wait | 25.16 | 25.04 | −0.12 |
| Post-Havok PPU | 24.28 | **23.00** | **−1.28** |
| Push-buffer emit | 5.73 | 5.60 | −0.13 |
| Gap | 2.44 | 2.39 | −0.05 |
| Wws spin | 11.91 | 11.65 | −0.26 |
| Before Havok + ref | 0.84 | 0.80 | −0.04 |
| Task pickup (`run_ns − fn_ns`), Havok 4 images | 0.84 ms/frame (27–42 µs/run) | 0.71 ms/frame (22–40 µs/run) | −0.13 |

The frame sd is 4.06 in S and 4.09 in P, a standard error of 0.145 ms each. So the 1.89 ms difference is well outside the noise within each run. Noise between runs was not measured, because there is one run per arm.

## 6. Task-creation savings and reuse

| | S | P | Label |
|---|---:|---:|---|
| Tasks per frame (`built` lines, by phase) | inside Havok wait: solver 5.08, collide 5.08; after Havok: raycast 5.00, animation 10.00 | inside Havok wait: 5.15, 5.15; after Havok: 5.00, 10.01 | VERIFIED |
| Task runs/frame (`[spu-task-stats]`) | 25.06 | 25.27 | VERIFIED |
| CPU of live (sampled) threads | 217 ms/frame; task CPU missing because those threads are short-lived | **319 ms/frame**: the ~100 ms of task CPU now sits on persistent threads | VERIFIED |
| Thread IDs seen in the window samples | 58 (55 live) | 67 (64 live): about 9 more persistent workers; no new ID between samples in the window | VERIFIED |
| Threads created in the race | about 25 per frame (thread-per-task, the old path) | close to 0 per frame from the stable ID set | PARTIAL: the pool's own counters are not printed, and `cpu.jsonl` samples only every ~5 s |
| Reuse rate | n/a | close to 100 % in steady race | PARTIAL, same reason |

- **Thread creation was about 35 µs of each 297 µs call** (−12 %).
- The remaining ~262 µs per call is not explained. Each call writes one unconditional `printf` line to stdout: 23,294 `[cellSpurs] CreateTask(...)` lines in P, matching the call rate. There is also a `[taskset]` / `dispatch HIT` line on stderr with `fflush`, and a scan of 128 task slots. **HYPOTHESIS:** the per-call logging through the runner's pipes dominates. T183's bench timed stderr writes to a file, not to these pipes.

## 7. Where the frame-time saving went

- The −1.89 ms is mostly in the **post-Havok window (−1.28 ms)**. That is where 15 of the 25 tasks per frame are created, and where raycast and animation run.
- In P, the raycast and animation tasks run faster: **0.551 → 0.379 ms** and **0.534 → 0.383 ms per run**. On-CPU share is unchanged (97 %). This is consistent with warm reused threads, with no new-stack page faults or cold caches. HYPOTHESIS on the cause; the per-run drop is VERIFIED.
- Solver and collide (10.56 / 10.78 ms per run against 10.54 / 10.73) did not change. Neither did the Havok wait (−0.12 ms).
- So the saving does reach total frame time; nothing else on the critical path absorbed it. But it comes from cheaper thread setup per task, about 0.7 ms on creation and about 0.6 ms on the short tasks, not from removing the CreateTask cost.
- Wws: lane busy per lane rose slightly (wid 1: 281–285 → 289–296 ms/s, over 3 % more frames per second), and the spin fell 0.26 ms.
- **System CPU:** S 61.9 %, P 55.8 % of all logical CPUs over the window, from `cpu.jsonl` sys counters. The process CPU rate is about the same in both: 428.6 s against 429.2 s of host CPU over a 114.6 s run.
- **Memory:** peak working set S 671.7 MB, P 673.6 MB (summary). The extra parked workers reserve stack address space but do not commit it.

## 8. Correctness observations

| Check | Result | Label |
|---|---|---|
| Missing or duplicated tasks | tasks per frame per image unchanged (5 / 5 / 5 / 10); per-phase placement unchanged | VERIFIED (counts) |
| Completion order | phase order (refx ≤ Havok enter ≤ Havok exit ≤ push-buffer ≤ spin) held in all 802 joined frames, as filtered | VERIFIED for frame-level order only |
| Deadlocks, hangs | none: race reached at 38 s as in S; the frame clock advanced to the stop; one `[fc-watchdog]` line (the start banner) in both | VERIFIED |
| Lost wakeups | none seen: no wait stalls, and Havok wait sd 4.08 against 3.39 with similar p99 frames | PARTIAL: indirect |
| State leaking between runs | no new error lines. `REJECTED malformed transfer` count is 8 in both runs (image 283218738, pre-existing). No STACKOVERFLOW, task-ID exhaustion, dispatch MISS or Present timeout in either | VERIFIED (log), PARTIAL as a test of leaks |
| Physics timing | solver and collide per-run time, DMA counts, GETLLAR rate and PUTLLC fail rate within 2–14 % of S; collide GETLLAR 477 → 543 | VERIFIED values; physics correctness not tested |
| Rendering or gameplay | **not verified**: the runner captures no frames, and nothing checks the race state | BLOCKED |

So the evidence supports execution stability, not verified gameplay correctness.

## 9. Measurement limitations

- One run per arm. Run-to-run variance on this exe was not measured, so the −1.9 ms could partly be noise between runs. The ~15 ms of identical-looking phases and the matching task counts make a large confound unlikely, but that is not proven.
- The pool counters (`created`, `reused`, `peak_busy`) are not printed in the game. Reuse is inferred from thread-ID and thread-CPU sampling at about 5 s.
- Both arms carry the S diagnostics. With them off, task creation might cost less, so the pool's share might differ.
- The 262 µs remaining per create is not split.
- The PPU sampler is still not wired into the game exe, so the ~20 ms of post-Havok PPU work stays unattributed.
- No frame captures.

## 10. Recommendation

**Keep the pool as an opt-in, and do not make it the default yet.** The run gives a measured, mechanism-consistent gain of 1.9 ms per frame, and the code review and logs found no defect. But it rests on:
- a single run per arm;
- no frame capture;
- no long-session stress (more than 75 s of race, track changes, menu transitions).

To support a default, the next authorized runs should be:
- a second P run against a second S, or B against B + POOL, to bound noise between runs;
- one capture-armed P run, to look at the race frames.

## 11. Next optimization opportunity

The ~262 µs per `cellSpursCreateTask` call that the pool did not remove is about 5.2 ms per frame, all on the frame thread, measured.

The next step is a host timer split inside `cellSpursCreateTask`: stdout `printf`, stderr lines, slot scan, context and taskset bookkeeping, and the pool handoff. That needs a small diagnostic code change and a build, so it needs its own authorization.

If the stdout `CreateTask(...)` line dominates, as suspected, gating it behind the existing `PS3_SPU_TASK_QUIET=1` would be a log-only change with no guest-visible effect. It can then be measured in the same way.

The larger item is still the ~20 ms of unattributed post-Havok PPU work. It needs `ps3_sampler_start()` wired into the game host.

## Files

- `tools/arm_s_t183.py`: now takes `T183_TAG` and also reports frame sd, thread churn, working set and system CPU.
- `tools/arm_s_place_t183.py`: takes `T183_TAG`.

Logs are kept private in:
- `generated/runs/20261103-061935-t183-Pp1`;
- `generated/analysis/t183/ab/runtime-p1-20261103-061935`.
