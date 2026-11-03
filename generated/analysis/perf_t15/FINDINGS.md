# T15 RSX performance / GPU sync / frame stalls (offline, 2026-10-25, no launch)

Host: AMD Ryzen 5 9600X (6C/12T), 47 GB, Windows 11 26200, VS 18 Community (MSVC 14.51), project Clang 23.1.3 (build/llvm).
Worktree: `ps3recomp-perf` on `agent/perf-regression-audit` (stale old-machine worktree registration moved to
`scratch/stale_worktree_admin/`; its index had no staged work beyond b45919c). Primary: `ps3recomp-int` @ 86c9e07, untouched.
Build helpers: `scratch/t15/{env,build_offline,cc_backend}.cmd`; workload scripts `scratch/t15/rsxi_{workload,texsnap}.py`.

## Commits (agent/perf-regression-audit)
- a409590 bench_texsnap_record (benchmark only)
- d4944b5 D3D12: fetch each indexed-strip vertex once per draw call (+ test)
- `git merge-tree` vs motorstorm/v0.17-integration: clean. The primary edits rsx_d3d12_backend.c only in the
  readback region (~3850-4750); this change is in upload_strip_vp_indexed (~8360). Not merged.
- `audit_public.py --staged`: 25 BLOCK items, all pre-existing tracked upstream files (PDF, icons, runtime/spu/tests/out_*,
  scratch/ppu_conformance.cpp); none from these commits.

## 1. Profiler (b45919c) on the new host - VERIFIED
test_ftrace_rsx_cpu, 6 runs: busy 0.94-1.04, blocked 0.00-0.10, half 0.35-0.49 CPU/wall (GetThreadTimes ~15.6 ms
quantum). Hook cost off 0.2-0.5 ns, on 47-51 ns/span, thread-CPU read 147-174 ns. ftrace_report.py parses the output.
No game run has used RSX_CPU yet: all existing exes (motorstorm-int*, built from v0.17-integration) predate b45919c.

## 2. s_gcm_fifo_lock - VERIFIED not a contention source
- Only acquirer: cellGcm_rsx_process_fifo. On Windows its only callers are port/main.cpp frame_clock (beat_drain and the
  outer loop), the same thread. host_posix.c is non-Windows. Guest threads use s_ref_pub_lock (TryAcquire, never blocks)
  and the ring-recycle wait (guest Sleep(1)-polls the walker; it does not take the lock).
- Holder work: FIFO walk + backend draw recording; may block in wait_for_gpu on RT resize/evict and zeta graveyard
  overflow (bounded 3x2 s). SEMA ACQUIRE does not wait (breaks the pass).
- Nobody else waits on it, so it cannot delay the RSX thread. Lock-wait instrumentation not justified.

## 3. GPU synchronization (rsx_d3d12_backend.c @ d4944b5)
| wait | when | needed? |
|---|---|---|
| render_frame start `wait_for_gpu` (full drain) | every replayed frame | Yes, until vp_cb constants and per-frame texture staging get per-frame copies (vp_vb already has x2 parity). Also the VPVB-growth point. Only per-frame CPU/GPU serialization. |
| move_to_next_frame fence | every present | Standard frame-index wait; after the drain above it is normally already complete. |
| off_rt_get resize / evict | RT size/format change, pool full | Yes (resource lifetime, D3D12 msg 921). Rare. |
| zeta_retire overflow, zeta_frame_begin | graveyard full / non-empty | Yes (lifetime). Graveyard bounds it. |
| rsxi_frame_finish, dumps, rt_save | diagnostics only | Off by default. |
| RT readback | own fence + worker thread | No wait on the RSX thread. |
Guest labels/semaphores/refs are written by the CPU walker in FIFO order, not by GPU fences, so the GPU waits do not
gate guest-visible sync directly; they only delay the frame-clock thread. Removing the per-frame drain needs ring-buffered
vp_cb and staging plus an ordering proof. Not attempted.

## 4. Stalls (runs 194334 A, 204223 B, 223035 rtrb2) - cause BLOCKED offline
- Reproduced in both readback runs (B, rtrb2: 7 stalls each, 2.7-6.1 s heartbeat gaps every ~45 frames). Absent in A over
  the same frame range (1 run; A has no readback).
- All 15 symbolized watchdog samples (B 8, rtrb2 7) are in CPU draw recording: rsx_fetch_attrib/upload_strip_vp_indexed (9),
  vp_record_tex_snap (3), vp_record_cb (2), rsx_vtx_pos_dbg (1). None in GPU waits, lock waits or readback code.
- Measured per-frame CPU on this host: vertex expansion 16-22 ms (garage shape), texture snapshot hashing 21-22 ms.
  A 3.5-6 s frame is >50x that. So the thread was slow inside memory-touching code, not waiting: preemption, page/memory
  stalls, or a much larger guest workload in those frames. HYPOTHESIS. Supporting: process CPU 5-7 cores and 1.4-2.2
  cores kernel during B's stalls vs 3.1 / 0.6-0.9 in A.
- Readback makes guest-visible writes (rtrb2 applied 1201 copies to 0xC2903600 by flip 1752, and guest tid 1 reads the
  surface). The guest workload with readback is therefore not the same as without it. HYPOTHESIS: more guest threads busy ->
  RSX thread preempted. RSX_CPU user/kernel/wall per frame separates the possibilities.
- Lazy guest commit (vm_commit_veh) only fires on first touch; there is no decommit path, so steady-state VEH faults are
  not expected.

## 5. Vertex expansion - VERIFIED (offline)
- RSXI garage frames: 578/619 draws are indexed strips (prim 6), 143606 indices -> ~426k emitted vertices, restart 0xFFFF,
  a0 half3 at stride 38. bench_vertex_fetch_vp: 43-59 ns/vertex sequential, 83-93 ns random (WC dst ~ cached dst).
- d4944b5: an 8-entry direct-mapped cache of converted vertices per call. test_vp_vertex_cache: 3000 random draws byte-
  identical; restart-boundary case; 2 mutants fail. Garage shape, WC output, 3 x 31 reps:
  before median 16.2-21.7 ms (max 18.6-36.7), after 7.2-10.7 ms (max 8.3-13.0); fetches 383022 -> 138502; 0 allocations.
- Not done: non-indexed strips, tri lists (no reuse), cross-call cache.

## 6. Texture snapshot - VERIFIED cost, not changed
Default PS3_TEX_SNAPSHOT=1 hashes the 2 MB linear B8 0xA1 texture on every bind: 410 binds/frame = 820 MB. Intra-draw
dedupe (identical handles) halves it: 21-22 -> 10.6-10.8 ms (bench_texsnap_record). Next candidate.

## 7. Proposed runtime experiment (NOT run; needs separate authorization)
Build (writes only build\motorstorm-perf-b45919c; do NOT run gen_hle_nids.py, which rewrites the primary's
generated\ppu-hooked-staging\ppu_hle_nids.cpp):
  git -C ps3recomp-int worktree add --detach ../ps3recomp-b45919c b45919c   (instrumentation only; otherwise = run B source 496485b)
  cmake -S port -B build\motorstorm-perf-b45919c -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang-cl
    -DCMAKE_CXX_COMPILER=clang-cl -DPython3_EXECUTABLE=%PYTHON% -DPS3RECOMP_DIR=%CD%\ps3recomp-b45919c
    -DRECOMP_DIR=%CD%\generated\ppu-hooked-staging -DSPU_DIR=%CD%\port\spu -DPORT_SPU_INPUTS=%CD%\generated\decrypted\EBOOT.elf
  cmake --build build\motorstorm-perf-b45919c --parallel 2
  certutil -hashfile build\motorstorm-perf-b45919c\MotorStormPacificRiftRecomp.exe SHA256   (record before asking to launch)
Run: python ps3recomp-int\tools\startup_runner.py run --config tools\motorstorm_milestones.json
  --exe build\motorstorm-perf-b45919c\MotorStormPacificRiftRecomp.exe --arg generated\decrypted\EBOOT.elf
  --target garage_capture_complete --profile fast --timeout 150 --allow-extended --stop-on-fatal
  --stop-on-line "GcKernel::Present\(\) Timeout" --runs-dir generated\runs
Env = rtrb2's (FIRST_FRAME=1, FIRST_FRAME_AUDIO=native, PS3_DEV_SKIP_INTRO=1, PS3_FC_WATCHDOG_MS=3000, PS3_HDD0/1_ROOT,
  PS3_VFS_ROOT, PS3_VERBOSE=0, RSX_HEARTBEAT_MS=1000, RSX_RTVIS=06A1E400,0x800,max=400, RSX_RT_READBACK=1,
  RSX_RT_READBACK_LOG=160) + PS3_FTRACE=45:90:{run_dir}\ftrace.txt, PS3_FTRACE_MIN_US=200.
  The window ends at 135 s < 150 s timeout; the trace is written by the first span after the window (or at exit).
Output: generated\runs\<stamp>-perf-rsxcpu\ (+ ftrace.txt). Duration 150 s.
Stop: runner timeout, fatal line, Present timeout, GPU watchdog; manual stop if the window freezes > 30 s.
Host load: before the launch and every 5 s, `typeperf "\Processor(_Total)\% Processor Time" "\Memory\Page Faults/sec"
  "\Memory\Available MBytes" "\GPU Engine(*engtype_3D)\Utilization Percentage" -si 5 -sc 30 -o {run_dir}\host.csv`;
  no other builds/tests during the run; note other running apps.
Read: tools\ftrace_report.py ftrace.txt -> per stalled interval: RSX_CPU user/kernel vs wall, VTX_FRAME us, GPU_WAIT.
  CPU/wall ~1 and user-dominated = real work (find it); high kernel = faults/paging; CPU/wall << 1 = preempted/blocked.
A second launch (d4944b5, same env) would validate the vertex cache in-game (VTX_FRAME us/vertex); ask separately.

# T16 (2026-10-25, offline, no launch)

## Texture snapshot sharing - ec1a44f (VERIFIED offline)
Checks (code @ d4944b5):
1. Identity/address: the store keys by bound guest offset; get() matches (off, handle, nbytes). Dedupe key = (off, nbytes).
2. Dims/format/pitch/mips: the snapshot is raw bytes [off, off+face_bytes) of level 0, unpitched rsx_texture_layout; the
   upload reads the same w*h*bpp level-0 range (non-cube; cube is never snapshotted). Format/pitch/mips affect sharing only
   through nbytes. (Pre-existing, unchanged: a pitched linear texture would be under-captured; no such case observed.)
3. Generation: shared only from the LATEST earlier capture of that offset in the draw, so the handle is still the key's
   current generation. First version (any earlier match) diverged when sizes alternate at one offset; caught by the test.
4/5. Guest CPU and RSX (RT readback worker) writes: no FIFO command runs between units of one draw, so a second hash differs
   only if another thread writes mid-draw (a tear on hardware too); then one capture for both units is the consistent result.
   Between draws everything captures again (labels/get/flip can release the buffer).
6. Cache invalidation/LRU: skipping the capture skipped its LRU touch, which changed later key recycling (caught by the test);
   shared units now make the same touch. Eviction/torn/copies counts identical.
Test: tests/test_tex_snapshot.c, 84177 checks PASS (4000 random 16-unit draws, 20 offsets > 16 keys, 2 sizes, guest writes
between draws vs per-unit reference). Mutants (no LRU touch; no size check) FAIL.
Bench (garage shape, 3 x 31): per_unit median 20.1-25.7 ms -> per_draw 10.1-13.0 ms; 820 -> 412 MB hashed; handles identical.
Backend TU compiles (exit 0, only the file's existing -Weverything classes). merge-tree vs v0.17-integration clean.
Not done: cross-draw reuse (needs proof no releasing command lies between the draws).

## Profiler exe (Phase 1) - built, not launched
Exe: build\motorstorm-perf-b45919c\MotorStormPacificRiftRecomp.exe
SHA-256: eaeb305d187189eb85ddc2adcb500a2e642e32631f2ae8eaff0fa15077fa793e (397,548,544 B, 2026-10-25 10:26)
Source: detached worktree ps3recomp-b45919c @ b45919c; script scratch\t16\build_perf.cmd; logs scratch\t16\build_perf{,2}.log.
Config: Ninja Release, clang-cl 23.1.3 (build\llvm), /O2 /Ob2 /DNDEBUG, RECOMP_DIR=generated\ppu-hooked-staging (read only),
  SPU_DIR=port\spu, PORT_HLE_NIDS_GENERATE=ON (table generated into the build dir from b45919c, 1215 handlers).
  The shared staging table fails to link at b45919c (11 cellFiberPpu* handlers it lacks). The rtrb2 exe (e55d70f9) contains
  all 1215 generated names and none of the 11, so the generated table matches the earlier stalling runs. HYPOTHESIS-level
  check (string presence), not a byte comparison.
Offline: exe contains PS3_FTRACE, _MIN_US, _MERGE_US, _CAP. Profiler unit test re-validated in T15 (same source).
Env/outputs/host-monitoring/limits: as in section 7 (ftrace.txt in the run dir, typeperf host.csv, 150 s, same stop conditions).

# T17 Combined performance integration (2026-10-25, offline, no launch)

## Integration branch - VERIFIED
agent/perf-integration-307b08a (worktree ps3recomp-t17) = 307b08a + cherry-picks (-x, all clean):
9069985 (b45919c profiler), eea8f42 (a409590 bench), aec8c95 (d4944b5 vertex cache), fab7b2c (ec1a44f texsnap sharing),
then d6d4576 (T17: TEXSNAP/TEXSNAP_FRAME spans, GPU_WAIT a=3 frame-start drain, hashed/allocs counters,
bench_frame_prep_combined). git diff 307b08a..HEAD touches no rt_readback / exposure-probe / RSXI code; every removed
line is one of ours (wait_for_gpu wait, old snapshot loop, 3 read_vp_vertex calls, ftrace_report range).
Profiler kinds now cover: vertex expansion (VTX/VTX_FRAME), texture snapshot create+hash (TEXSNAP/TEXSNAP_FRAME),
D3D12 command recording (GPU_ENCODE), GPU waits incl. full drain (GPU_WAIT a=3), PRESENT, RSX_CPU (thread CPU vs wall).

## Offline tests - VERIFIED (base 307b08a vs t17)
- tools/test_*.py via scratch\t17\suite.cmd: 109/109 both, no per-test rc difference.
  Needs scratch-only CC shim (scratch\t17\cc_shim.cmd + posix_shim.h: -D_CRT_SECURE_NO_WARNINGS, setenv/unsetenv on
  _putenv_s) and an empty m.lib on LIB; without it test_draw_rejection / test_present_diag / test_xfer_diag fail to
  compile on BOTH trees (no gcc/mingw/WSL here). tools/regress.py not run (launches the game).
- CTest (scratch\t17\ctest.cmd, PS3RECOMP_BUILD_TESTS=ON, clang-cl Release): 19/19 both (build\t17-ctest-base, build\t17-ctest).
- Standalone: test_vp_vertex_cache (3000 draws), test_tex_snapshot (84178 checks), test_ftrace_rsx_cpu, test_frame_beat,
  test_video_stats: all exit 0. Backend TU compiles (only the file's existing warning classes).

## Combined bench - VERIFIED offline (not a game frame time; no FIFO walk, shaders, D3D12 or GPU)
scratch\t17\out\bench_frame_prep_combined.exe 31, 3 runs each; 619 draws, 578 indexed strips, 206 texsnap draws (204 x2).
Pre-check: both-on vertex bytes and snapshot copies/seq/torn identical to both-off.
  mode            median ms (3 runs)  worst max  vertex fetches  MB hashed  allocs/frame  cpu/wall
  neither 307b08a 37.5 / 37.7 / 38.8     42.8        383001          820          0          ~1.0
  vertex cache    28.1 / 28.5 / 29.1     33.7        138516          820          0          ~1.0
  snap sharing    26.6 / 27.1 / 27.6     34.1        383001          412          0          ~1.0
  both (T17)      17.2 / 17.7 / 18.0     22.1        138516          412          0          ~1.0
Private bytes +0 in every mode. Outputs: scratch\t17\bench_off.txt, bench_on.txt.
Profiler overhead: PS3_FTRACE=0:600:<scratch>\bench_ftrace.txt PS3_FTRACE_MIN_US=200 -> both 16.9 / 17.9 / 17.0 ms vs
off 17.2 / 17.7 / 18.0: within run-to-run noise. Micro: guard 0.19 ns off; 44 ns per span on; thread-CPU read 140 ns.
Trace: 0 dropped; kinds 15/16/17/18/19 present. (ftrace_report.py needs flips, so it does not summarise the bench trace.)

## Exe - built, not launched
build\motorstorm-perf-t17-d6d4576\MotorStormPacificRiftRecomp.exe
SHA-256 aca147b145b4c1dcad8b2fd41f8477995d96cbb31af1af0b7c25952d32007924 (397,560,320 B, 2026-10-25 11:29)
Source: ps3recomp-t17 @ d6d4576 (base 307b08a). Script scratch\t17\build_exe.cmd, log build_exe.log.
Config: Ninja Release, clang-cl 23.1.3 (build\llvm), MSVC 14.51 env, PORT_HLE_NIDS_GENERATE=ON -> ppu_hle_nids.cpp in the
build dir only; RECOMP_DIR=generated\ppu-hooked-staging (read only; its ppu_hle_nids.cpp mtime still 2026-10-21).
Contains PS3_FTRACE*, PS3_TEX_SNAPSHOT, RSX_RT_READBACK, RSXI strings.

## Proposed runtime command (NOT run; needs separate authorization)
python ps3recomp-int\tools\startup_runner.py run --config tools\motorstorm_milestones.json
  --exe build\motorstorm-perf-t17-d6d4576\MotorStormPacificRiftRecomp.exe --arg generated\decrypted\EBOOT.elf
  --target garage_capture_complete --profile fast --timeout 150 --allow-extended --stop-on-fatal
  --stop-on-line "GcKernel::Present\(\) Timeout" --runs-dir generated\runs
Env = rtrb2's (section 7) + PS3_FTRACE=45:90:{run_dir}\ftrace.txt PS3_FTRACE_MIN_US=200; typeperf host.csv; same stop
conditions and limits as section 7. Read with ps3recomp-t17\tools\ftrace_report.py (snap MB / snap ms columns).

## Primary worktree
ps3recomp-int never written (only git status/log read). It now carries the primary's own uncommitted edits, including
rsx_d3d12_backend.c (+1 include line 26, typedef ~310, vp_get_vs ~2002, vp_record_cb ~3644). No hunk overlaps ours;
the include block (ours line 23) is adjacent and will need a trivial manual merge. Not merged, not pushed.

## T17 preflight (2026-10-25 13:15, offline, no launch) - supersedes the Exe and runtime-command parts above
Byte comparison - VERIFIED. bench_frame_prep_combined --dump <vc> <sh> <file> 3, one process per mode, same seeded
inputs; 3 frames, guest rewrites of the texture plane (frame 1+) and vertex arrays (frame 2+) between frames. File =
per frame: input hash, all emitted vertex bytes, all 16 handles of every texsnap draw, the bytes each handle resolves to
at present, the whole store (keys, gens + bytes, tick/LRU, seq) and copies/reuses/evicted/torn/failed/allocs.
Excluded only: hashed, shared, fetches (the costs being reduced).
- First result: vertex cache identical; snapshot sharing differed in 6 bytes = `reuses` (409 vs 205/frame; shared units
  were not counted). Not read by the runtime; fixed anyway in 3d19969 (a shared unit counts as a reuse).
- After the fix: neither / vcache / share / both all 313,063,014 B, SHA-256
  dd075edbc6dc5aa612de1b0cf3807559252a3bbd96dd437e5e03931df024f1b5, cmp identical (scratch\t17\dump\sha256.txt).
  test_tex_snapshot 84178 PASS.
Exe (rebuilt, incremental, same dir): build\motorstorm-perf-t17-d6d4576\MotorStormPacificRiftRecomp.exe now = 3d19969
  (dir name kept); SHA-256 52c171bccd5862fee3ba39a4b48e6b2c58777913965cfd979119c709e24d35a9 (397,559,808 B, 13:09).
Old runtime proposal was wrong:
- garage_capture_complete is unreachable in profile fast (needs loadscreen_renderer_exited <- garage_world_read_complete,
  log lines off) and the env had no RSXI; the primary's capture/c38 runs ended on stop lines, not on that target.
- the runner starts from os.environ (inherits; the dry run found GCM_INTERACTIVE in this shell), kills by image name
  (would kill a primary run), and its taskkill /F skips the ftrace atexit dump.
- PS3_FC_WATCHDOG_MS does not exist in 307b08a-based source (inert); the runner's hard kill is 165 s, not 210/225.
Corrected launcher: scratch\t17\run_t17_profile.ps1 (parse OK; -DryRun preflight OK at 13:13; nothing launched).

## T17 runtime profile (2026-10-25 13:22, one authorized launch)
Run generated\runs\20261025-132231-perf-t17-ftrace; wrapper scratch\t17\runtime-20261025-132230. exe sha256 52c171bc...d35a9
(3d19969). termination milestone_reached (depth_surface_created at 46 s, RSXI capture 131-132 s); game exit_code 1 = runner
taskkill. Wrapper exit 4 is the empty Start-Process ExitCode quirk only: final cleanup found no process. Analysis:
scratch\t17\analyze_run.py.
- VERIFIED garage FPS: 11.68 heartbeat-average over 46-132 s (620-649 draws), per-second median 12.23; trace median frame
  81.1 ms (12.3 fps), guest flip-request interval median 82.2 ms. No heartbeat gap > 2 s.
- VERIFIED per garage frame (869 frames, 46-120 s, medians): vertex expansion 12.6 ms (305k verts), texture snapshot 11.3 ms
  (400 MB hashed/frame), D3D12 recording (render_frame->Present) 7.4 ms, frame-start GPU drain and all GPU waits 0 (never
  blocked), Present 0.19 ms. RSX thread CPU/wall 0.44 (GetThreadTimes 15.6 ms granularity).
- PARTIAL bottleneck: RSX thread idle ~55% of each frame, no ACQUIRE wait > 100 ms; main PPU thread 33% usleep polling.
  Frame rate is set by the guest flip rate, not by RSX/GPU work. Which wait the main thread polls on is unexamined.
- Stalls: 1379 ms at 45.3 s (first garage frame, user-CPU bound, recording 743 ms: pipeline creation, HYPOTHESIS); 603/633 ms
  at 60.5/63.1 s with ~50 ms CPU (blocked). Host CPU dips to 26% at sample 60; no paging pressure (min 32 GB free), GPU 3D <= 10%.
- Trace complete: 53774 spans, dropped 0, window 30-120 s written at window end.
- Comparison: the ~14 fps figure is the per-second peak of 20261025-102805-garage-capture-probe (307b08a, this host, 21 s of
  garage, median 13.0, avg 9.9 with RSXI+probe/watch env). Different exe, env (RSXI capturing, readback probes, FC watchdog)
  and window length: no causal claim. A same-revision A/B (vcache/share off vs on) is needed.

### T17 runtime profile - review corrections (offline, 2026-10-25; no further launch)
Supersedes the bottleneck and termination wording above. Script: scratch\t17\analyze_run.py (updated).
- Termination: the target milestone and the scheduled 1-frame RSXI capture both completed (milestone_reached, 131-132 s).
  The game did not exit by itself: the runner then force-killed it (taskkill /F; manifest termination.exit_code 1).
  Separately, the wrapper's exit 4 comes from Start-Process returning an empty ExitCode; its final cleanup found no process.
- Watchdog correction: PS3_FC_WATCHDOG_MS is implemented in port\frame_clock_watchdog.h (2026-10-23), which this exe
  compiles. The preflight claim that it was inert was wrong; this run simply had no frame-clock watchdog (prior runs: 3000).
- Method checks - VERIFIED from source (ps3recomp-t17 include/ps3emu/ps3_ftrace.h, libs/video/rsx_d3d12_backend.c):
  - Frame = RSX_CPU interval between two presents; VTX_FRAME/TEXSNAP_FRAME share its exact start/end (ft_rsx_frame).
    Their totals are per-interval accumulators over every draw (no MIN_US). GPU_ENCODE/PRESENT/DRAIN are counted when fully
    inside the interval; 1462 encodes vs 1461 presents, so no offscreen-only batch is mis-attributed.
  - Overlap: all 218 VTX and 396 TEXSNAP spans >= 200 us lie inside DRAIN spans, none inside GPU_ENCODE; GPU_ENCODE and
    PRESENT never overlap DRAIN. So vertex/snapshot time is FIFO-walk time, recording excludes it, and the parts add.
  - GPU waits: wait_for_gpu/move_to_next_frame emit GPU_WAIT only when the fence was not yet complete, and ps3_ft_span has no
    MIN_US filter. 0 spans = never blocked, not "below 200 us". The non-blocking Signal/GetCompletedValue cost is unmeasured.
  - DRAIN spans have the MIN_US filter (cellGcmSys.c:1799); sub-200 us drains are missing from "fifo".
  - CPU: GetThreadTimes deltas in 15.625 ms ticks (observed 0-4 ticks/frame); per-frame user/kernel are quantised, the
    74.7 s aggregate is not biased. Denominator = summed RSX_CPU wall of the 869 garage frames (46-120 s).
- Per garage frame (medians): FIFO drain 29.8 ms (of which vertex 12.6, snapshot 11.3), recording 7.4, Present 0.19.
  Measured busy (drain+recording+present)/wall = 0.46, CPU/wall = 0.44: consistent. The rest of the frame the frame clock is
  in its Sleep(4)/beat loop (port/main.cpp:205-227) with no flip to present - INFERENCE from the absence of other RSX spans.
- Slow frames 60.5/61.3/63.1 s (603/355/633 ms): no RSX span > 50 ms inside them, no flip request until the interval end,
  main PPU thread blocked <= 9% (VERIFIED). The guest issued no flip for 0.35-0.6 s while its main thread was running;
  what it ran is unknown. Host CPU dips to 26% at sample 60 (typeperf starts ~0.5 s before boot): weak correlation only.
- Main-thread usleep (VERIFIED from code + trace): 99% of main usleep time (15.6 of 48 s window 70-118 s, 26628 calls) has
  guest lr 0x0094CCA8, i.e. inside func_004B63F0 called from func_0094CC80. func_004B63F0 is a spinlock acquire: lwarx/stwcx
  0->1 on [r3], ~1000 plain-read spins, then sys_timer_usleep(250) (syscall 141, r3=0xFA), retry; func_004B63E0 releases
  (store 0). func_0094CC80(obj) takes lock obj+0xC, then obj+8, then releases both; func_0094CBD8 takes obj+8 then obj+0xC.
  Lock address in THIS run: not recorded (USLEEP spans keep only lr; HOTREAD needs 200k consecutive reads and never fired
  for this lr here). Earlier runs (rtrb2, other exe/host) logged it as 0x17FF8CEC and 0x16F3B21C (=1, held).
  Merged spans include the spin between sleeps and any re-acquire within 300 us, so 33% is time in the lock's back-off
  loop, not pure sleep (>= 6.7 s requested sleep).
- Holder of that lock: NOT established. No artifact records which thread holds obj+0xC. Separately, an unidentified PPU
  thread spins on 0x10CE8F40 (lr 0x005226E8, after func_0050C818) at ~200 HOTREAD reports/s (~4e7 reads/s) for the whole
  garage, dipping at 59-62 s; fios mediathread (tid 4) is the only PPU thread blocked only 1% (HYPOTHESIS that it is this
  spinner). SPU busy/wait spans are absent from this trace, so SPU-side holders cannot be checked.
- Conclusion (PARTIAL): presented FPS = guest flip rate (82 ms); the RSX thread is idle ~54% and never waits on the GPU or on
  a guest semaphore. That shows RSX/GPU work is not the immediate limiter. It does NOT prove guest-bound execution: the main
  thread spends a third of each frame contending for a guest spinlock with an unknown holder, and RSX->guest feedback (the
  sync-fence labels written by beat_drain at 59.94 Hz, flip/vblank events via event_queue_receive ~3.5% of main) is not
  excluded as a source of upstream pacing.

### Proposed same-exe A/B (NOT run; needs authorization)
No runtime switch exists today (VERIFIED: 3d19969 has no getenv for the vertex cache or sharing; both are unconditional
in upload_strip_vp_indexed / ps3_texsnap_capture_draw). Proposal, needs a small code change and one rebuild first:
- Add PS3_VP_VCACHE=0 (call vp_vcache_fetch directly instead of rsx_vp_vcache_get, rsx_d3d12_backend.c ~8634) and
  PS3_TEX_SNAPSHOT_SHARE=0 (skip the shared-unit branch, tex_snapshot.h:~160), both default 1, read once. Offline gate: the
  existing --dump byte comparison through the env paths, test_vp_vertex_cache, test_tex_snapshot, suite 109/109.
- The new exe (new SHA-256) is then the single exe for every arm; 52c171bc... cannot serve as its own baseline.
- Same wrapper and env, same host, only the two switches differ.
- Arms: A both off, B both on; optional C vcache only, D share only. Order A B B A (or ABBA x2) to cancel drift/thermal;
  one launch each, no retries; idle host, primary not running; same cache snapshot restored before each.
- Per arm: garage FPS (heartbeat 50-120 s), per-frame drain/vertex/snapshot/recording/Present, RSX CPU/wall, main lock
  back-off share (lr 0x0094CCA8), flip interval. Add PS3_FC_WATCHDOG_MS=3000 to all arms if desired, identically.
- Decision rule: claim an FPS effect only if B-A exceeds the A-vs-A spread; if FPS is unchanged while drain time drops,
  that is consistent with (not proof of) a limiter upstream of RSX work.

## T18 A/B preparation (offline; nothing launched)

- Commit `3b38721` (branch `agent/perf-integration-307b08a`, worktree `ps3recomp-t17`; not merged/pushed).
- Exe `build\motorstorm-perf-t18\MotorStormPacificRiftRecomp.exe`, SHA-256 `3e7de90914590c769c15e1897be3bc3f4885d7070d24e77d65021c1a4a8a724d` (BUILD_RC=0).
- Switches (default 1; `0` = original path; read once; printed as `[perf] PS3_VP_VCACHE=.. PS3_TEX_SNAPSHOT_SHARE=..`): `PS3_VP_VCACHE`, `PS3_TEX_SNAPSHOT_SHARE`.
- Diagnostics (default off; no synchronization change): `PS3_FTRACE_SYNC=1` keeps all DRAIN spans and adds LABEL (kind 20: NV406E / 0x1D70 / 0x1D74 / host buffer) and VBLANK (kind 21: tick / flip-completing vblank / TickFlip) instants; `PS3_FTRACE_USLEEP_REG=<n>` adds USLEEP_ARG (kind 22: GPR n at the start of each merged usleep run; r29 = spinlock address at lr 0x0094CCA8).
- VERIFIED offline: 4 switch combinations x bench `--dump`/`--dump-env` identical SHA-256 `dd075edb…f1b5` (313,063,014 B, = T17); test_tex_snapshot 84,275 checks (mutant caught); test_ftrace_sync 6; test_vp_vertex_cache, test_ftrace_rsx_cpu ok; suite 109/109 (43 SKIP tails, no rc change vs T17); CTest 19/19. Bench medians: none 35.9 ms, vcache 27.1, share 26.0, both 17.1.
- Not covered offline: GCM label/vblank hooks (GCM fixtures SKIP on this host); backend vertex-off loop (bench mirrors it); `GCM_FLIP_NEEDS_FIFO` path emits no VBLANK.
- Protocol: `scratch\t18\run_t18_ab.ps1 -Arm OFF|ON -Seq 1..4`, order OFF,ON,ON,OFF enforced; each run restores `generated\hdd1` to snapshot `generated\cache-snapshots\20261025-132231` (hash-checked; hdd1 backed up and restored after); identical env except the two switches; 150/165/210/225 s limits. Analysis `scratch\t18\analyze_ab.py` (window 50-118 s). Decision: an ON-OFF FPS difference is reported only if it exceeds the OFF-vs-OFF spread, and then only as consistent with (not proof of) an effect.
- Dry runs of all 4 arms: preflight OK, nothing launched, no cache touched; wrong sequence -> exit 5.

## T18 relink investigation and isolated build (offline; nothing launched)

- VERIFIED cause: concurrent session `d57e2d95` (T22 work) ran `generated\analysis\t22\build_exe.cmd`, which configures and builds `build\motorstorm-perf-t18`. Attempt 1 at 14:38:41 collided with the T18 build (`build_exe_collided.log`: ninja "failed recompaction: Permission denied"). Attempt 2 at 14:40:30, after the T18 build finished (14:40:14): the configure re-ran the SPU lift (`execute_process` in `PS3RecompSPU.cmake`), rewrote `generated_spu/*` (14:40:54-57) and `build.ninja` (14:40:57). Ninja then rebuilt 27 SPU objects + `spu_workloads.c` and relinked at 14:41:34 (`.ninja_log` lines 283-311; `t22\build_exe.log` [28/29]). Its dry run at 14:45:37 printed the new hash 17e9cd9f….
- The original exe (3e7de909…) was overwritten and is no longer available. HYPOTHESIS: the hashes would differ even with identical code, because the PE TimeDateStamp holds the link time (0x6ade070e = 14:41:34; no /Brepro). Whether the code also differs is unresolved.
- Isolated build: detached worktree `ps3recomp-t18iso` @ 3b38721 (clean) -> `build\motorstorm-t18iso-3b38721\MotorStormPacificRiftRecomp.exe`, 397,565,952 B, built 14:59:52, SHA-256 `3ee46f8f29d93ad09c3c691aec2575535866e5893aa2706f4fecb536b2ace114`. Fresh configure, same options (only PS3RECOMP_DIR differs); clang-cl 23.1.3, lld-link, CMake 4.3.1-msvc1, Ninja 1.13.2, Release /O2 /Ob2. Config in `scratch\t18iso\cmake_config.txt`; shared inputs (port/, ppu-hooked-staging, EBOOT.elf) hashed before and after: unchanged. The hash was the same at 15:02:25, build files and timestamps unchanged, no build process left; the exe is set read-only.
- Offline, against `ps3recomp-t18iso`: test_ftrace_sync 6 PASS, test_tex_snapshot 84,275 PASS, test_ftrace_rsx_cpu ok, test_vp_vertex_cache ok; 4 switch combinations + default dump identical (dd075edb…f1b5); suite 109/109, no rc change vs T17. (Bench timings were taken during the build, so they are not comparable.)
- Wrapper `scratch\t18iso\run_t18_ab.ps1`: the T18 wrapper with the isolated exe path and hash, outputs and hdd1 backups under scratch\t18iso, plus a second full SHA-256 check immediately before launch (a mismatch is caught -> hdd1 restored, exit 6). Limits and cache guarantees unchanged. All 4 dry runs OK; out-of-order run -> exit 5.

## T18 A/B results (4 authorized launches, 2026-10-25 15:48-15:58)

Exe `build\motorstorm-t18iso-3b38721\MotorStormPacificRiftRecomp.exe` (3b38721), SHA-256 3ee46f8f…e114, checked before each launch (my check + wrapper preflight + wrapper re-check right before Start-Process; all 4 matched). Runs: `generated\runs\20261025-154856-perf-t18-ab1-off`, `…155132-perf-t18-ab2-on`, `…155352-perf-t18-ab3-on`, `…155613-perf-t18-ab4-off`; wrapper dirs `scratch\t18iso\ab<N>-<arm>-<ts>\`. Each run: wrapper exit 0, termination milestone_reached (depth_surface_created at 38-40 s), RSXI capture complete at ~125 s, no wrapper kill, final cleanup none/ok, game exit code 1 (runner kill after the milestone), `[perf]` line matches the arm, 0 fatal/assert lines, trace dropped=0. generated\hdd1 restored after each run and identical to its pre-A/B state (`scratch\t18iso\hdd1_pre_ab.sha256`); hdd1 backups kept under scratch\t18iso. Analysis: `scratch\t18iso\analysis.txt`, `gaps.txt`, `gapctx.txt` (window 50-118 s).

| | OFF1 | ON2 | ON3 | OFF4 |
|---|---|---|---|---|
| FPS (heartbeat, all frames) | 13.23 | 12.86 | 12.41 | 13.25 |
| FPS excluding gaps >250 ms | 13.23 | 13.18 | 13.00 | 13.25 |
| flip interval median / p95 / p99 ms (excl. gaps) | 75.1 / 81.3 / 84.5 | 74.9 / 83.0 / 89.3 | 76.4 / 84.2 / 89.0 | 74.8 / 82.4 / 86.5 |
| gaps >250 ms in window | none | 1568 ms @100.3 s | 2996 ms @104.5 s | none |
| RSX prep (vtx+snap) median ms | 38.3 | 23.5 | 23.7 | 37.8 |
| FIFO drain per frame median ms | 43.3 | 29.4 | 29.7 | 43.0 |
| D3D12 encode median ms | 7.2 | 7.3 | 7.0 | 6.8 |
| RSX thread cpu/wall | 0.64 | 0.48 | 0.48 | 0.64 |
| main thread in lock back-off (lr 0x94CCA8) | 35.8 % | 32.8 % | 32.3 % | 35.7 % |
| GPU waits | 0 | 0 | 0 | 0 |
| host CPU % / GPU 3D % (median) | 33 / 0 | 32 / 1 | 35 / 1 | 31 / 1 |

- VERIFIED (reproducible, far above OFF-OFF spread): RSX frame prep -38 % (38.0 -> 23.6 ms; OFF-OFF 0.4 ms, ON-ON 0.2 ms), drain -32 %, RSX thread CPU/wall 0.64 -> 0.48. Consistent with the bench (not proof of causation).
- No FPS gain. Excluding gaps, ON is 0.05-0.25 FPS below OFF, and the ON-ON spread (0.18) is well above the OFF-OFF spread (0.02), so this is not distinguishable from noise. Flip-interval medians are the same (~75 ms) in all arms. The analyzer's all-frames figure (ON-OFF -0.60 FPS, "exceeds baseline") comes almost entirely from the one gap in each ON run, not from per-frame cost.
- PARTIAL (strengthened): RSX prep is not the frame-rate limiter in the garage. Removing ~14 ms of RSX prep per frame left the ~75 ms guest flip pace unchanged; the main thread still spends 32-36 % in the spinlock back-off.
- Frame gaps: all 4 runs have the same two garage-entry stalls (~0.62 s + 0.74-0.94 s at 38-40 s). Each ON run also has one mid-garage gap (1.6 s, 3.0 s). During it the RSX thread is idle (1 drain of 29 ms; no FIFO submissions), the main thread logs only 16-18 short spans (runs untraced), SPU taskset/HOTREAD activity on 0x10CE8F40 continues at its normal rate, host CPU drops to 16-17 % and page faults dip. The next frame has 790 draws instead of 630, which happens once in each ON run and never in OFF runs (OFF1 has one 649-draw frame). HYPOTHESIS: a guest-side content/streaming event whose timing varies. With n=2 per arm, it cannot be told whether the switches cause it. The T17 run (both on, older exe) had different gaps (603/358/636 ms at 60-63 s) and no 790-draw frame.
- Rendering: captured frames (f002910-f002959) have identical structure in all 4 runs (721 events, 619 draws, same event-kind sequence); no fatal errors. Offline dumps were byte-identical across arms. The dumped shader files differ in content in every run, OFF1 vs OFF4 included, so the switches can't be compared on them (not examined further). No regression observed; pixel output not compared.
- Sync diagnostics: 0 LABEL instants in all runs. The hooked NV406E/0x1D70/0x1D74/host-buffer writes were not hit in the garage, or the guest syncs through another path (unresolved). vblank-interval median differs (OFF 0.03 ms vs ON 12.9 ms): in OFF, vblank beats arrive in bursts behind the longer drains (observation; frame-clock semantics unchanged).
- Next step: profile the guest frame (main thread ~75 ms pace, spinlock holder, the 0x10CE8F40 spinner) rather than the RSX path. Separately, decide with more runs whether the mid-garage gap depends on the switches. Both need separate authorization.
