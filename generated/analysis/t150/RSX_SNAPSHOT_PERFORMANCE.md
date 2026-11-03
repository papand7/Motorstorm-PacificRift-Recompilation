# T150: MotorStorm Pacific Rift, RSX texture snapshot and frame processing

Labels: VERIFIED, PARTIAL, HYPOTHESIS, BLOCKED. No game launch, no push, no merge, no GitHub operation.
Per-stage numbers: `RSX_FRAME_COST_BREAKDOWN.md`.

## Answer in brief

1. **The 79 ms is one hash.**
   - It is the full hash of a single 2 MiB linear texture that never changes, captured on about 1,065 draws per frame: about 2.1 GB hashed per frame, with 0 copies (VERIFIED, T149 P0 trace).
   - No copy, allocation, lock or address translation contributes.
2. **T122's `PS3_TEX_SNAPSHOT_EPOCH` already removes it** (69 → about 1.3 ms in game, T149 P1).
   - Its skip is sound by code review: a drain pass reads `put` once, and the epoch is bumped at every point where the guest can observe RSX progress or where the RSX side writes guest memory.
   - It reuses a capture even if the guest wrote the texture inside the epoch. That is a legal hardware outcome, but it is not identical to the default path.
3. **New, opt-in `PS3_TEX_SNAPSHOT_WWATCH=1`** (ps3recomp `b513c55` and `dd0beee`, plus the `port-t150` reservation flag):
   - Windows write-watch tells the store exactly whether any byte of a texture's pages was written since its last capture.
   - It makes **the same copy decisions as the default hash path**, with identical handles on every capture in the differential test, and skips only the hashes whose answer was already known.
   - Synthetic race workload: 53 ms → 1.8 ms per frame alone, **0.10 ms combined with the epoch** (PARTIAL: synthetic).
4. **Validation:** stale reuse is tested directly. Every capture is compared with the guest bytes at capture time, and three seeded bugs are each caught.
5. **After the snapshot, the renderer is not the frame's gate** in the performance preset: idle 54 ms of an 87 ms pass. The next costs are fat vertex expansion (about 43 ms; T119 compact fixes it) and command recording (3–6 ms).
6. **No default changed. No game FPS is claimed.** A four-arm A/B is prepared (§12) and needs authorisation.

## 1. Baseline and source commit

- **ps3recomp:**
  - worktree `ps3recomp-t150-rsx-performance`, branch `agent/t150-rsx-snapshot-performance`;
  - base **`80fe5de`**, the T146 unified runtime tip (`integration/t146-unified-runtime`), the same base T149 used.
- **T147:** its tip `d76e08e` is **not** an ancestor of `80fe5de` (10 commits apart), so T147 is not included, as the brief specifies.
- **Commits:**
  - `b513c55`: write-watch store, stats, tests, bench;
  - `dd0beee`: differential handle-equality check.
- **Port:** `port-t150/` is a private copy of `port/` (precedent: `port-t106aot/`). Its one change is that `alloc_guest_vm` adds `MEM_WRITE_WATCH` to the arena reservation when `PS3_TEX_SNAPSHOT_WWATCH=1`; otherwise the reservation is unchanged. `port/` itself is untouched.
- **Absent from the base:** T144 lane handoff and T147 visual presets. Neither is used here.

## 2. Profiling methodology

- **Game evidence (existing, no new launch):** T149's four race runs (2026-10-28):
  - `[rsx-frame-perf]` per pass;
  - the critical-path trace, with per-draw `TEXSNAP` spans (`a` = KB hashed, `b` = copies);
  - phases from `[PT]`.
  - Medians over the race window come from `t150/ab/ana_t150.py`.
- **New instrumentation (off by default):** `PS3_TEX_SNAPSHOT_STATS=<ms>` prints one line per window with, per frame:
  - captures, split into epoch skips, write-watch skips, hash reuses and copies;
  - MB hashed and copied; buffer allocations;
  - time in the write-watch lookup, the hashes, the copies and the whole capture loop;
  - write-watch checks and dirty pages; evicted, torn and failed counts;
  - every key captured in the window (offset, KiB, captures per frame), which gives unique addresses, sizes and hash calls per texture.
  - Timers are taken only when the switch is set.
- **Double counting:** `TEXSNAP` spans are per draw and do not nest. They sit inside `expand_ms` and `DRAIN` and are counted once.
- **Offline:**
  - `t150/probe/wwatch_probe.c`: which writes write-watch sees, and what it costs;
  - `tests/bench_tex_snapshot.c`: the race-shaped workload;
  - `tests/test_tex_snapshot_wwatch.c`: correctness.

## 3. Explanation of the 79 ms cost

| Component | Measured | Evidence |
|---|---|---|
| captures per frame | about 1,065, each the same 2 MiB key | P0 trace: 7,000 `TEXSNAP` spans/s, `a = 0x800` each; T122 saw about 1,300 |
| copies | 0 | `b = 0` on every span |
| bytes hashed | about 14 GB/s, or 2.1 GB per frame | spans × 2 MiB |
| time | 45% of wall time on the drain thread, ≈ 69 ms per frame (79 ms in the cpath summary, which uses longer frames) | span durations, about 60 µs each |
| allocation, locks, translation | none on this path: buffers are kept, capture is single-threaded, and the address is `vm_base + off` | code |

The texture is linear B8/G8B8 and at least 64 KiB, which is the mode-1 snapshot class. Its guest bytes never change during the race.

## 4. Snapshot lifecycle analysis

- **Store:** 16 keys (guest offset) × 4 generations, LRU over keys.
- **Default capture:** hash the guest bytes, then either reuse the latest copy if the hash is equal, or copy into the next generation and hash the copy (`torn` if the two hashes differ).
- **Present:** uploads from the handle's copy, falling back to guest memory and counting `evicted` if the copy was recycled.
- **The race:** all captures hit the same key and generation. The buffer is allocated once, so nothing is created or destroyed per frame and pooling has nothing to save.

## 5. Redundant-work findings

- **A. Per-frame deduplication.** All the redundancy is the same key captured again with unchanged bytes. Deduplicating units within one draw saves nothing: each draw captures 2 MiB, i.e. the texture once.
- **B. Write tracking.** There was no guest-memory dirty tracking. Guest stores are raw host stores (`vm_base + ea`), so instrumenting them is impractical. Windows write-watch tracks at the OS level, with one private reservation and no aliasing views. The probe (`t150/probe/wwatch_probe.c`, all OK) confirms it sees:
  - user stores;
  - stores from other threads;
  - `memcpy` from another thread (the SPU DMA and render-target write-back paths);
  - CRT `fread`;
  - `ReadFile`, both cached and `FILE_FLAG_NO_BUFFERING` (device DMA).
- **C. Hashing efficiency.** The hash already runs at about 33 GB/s (4 independent FNV-style lanes), near memory bandwidth, so a faster hash would not change the picture. Removing the hash is what pays. The default path's reuse rests on 64-bit hash equality. Write-watch skips are exact, and never reuse on a collision that changed bytes.
- **D. Lifetime.** Nothing to pool (§4).
- **E. Render-target feedback.** RT → texture feedback (T141) is a GPU-side copy, not this guest-memory snapshot. Render-target write-backs into guest memory are host `memcpy`, so write-watch sees them, and they also bump the epoch.

## 6. Existing T122 epoch analysis

- **Present in T146 (`54a25df`): yes.**
  - It is off by default and part of the T146 performance preset (T149 P1).
  - What it skips: the hash of a key already captured in the current sync epoch.
- **Is the skip correct? VERIFIED by code review, with one qualification.**
  - A drain pass reads `put` once (`cellGcmSys.c`, one `vm_read32(GCM_CONTROL_GUEST_ADDR)` before the walk). Every guest write ordered before that `put` store is therefore in the first capture of the epoch.
  - The epoch bumps at:
    - every pass start;
    - every JUMP's published `get`;
    - every impure packet, i.e. any non-3D subchannel, channel methods, NOTIFY, reports and semaphores;
    - every render-target write-back.
  - Between bumps the guest learns nothing about RSX progress, and the RSX side writes no guest memory.
  - **Qualification:** a guest write made during the pass, after `put`, is not seen by later draws of the same epoch. On hardware that is a race whose outcome may be either value, so the result is legal, but it differs from the default path, which would capture the new bytes.
  - `tools/test_tex_snapshot_epoch.py` pins the bump sites and mutates each one (PASS on the T150 tree).
- **T141 feedback:** unaffected, since feedback does not go through this store, and write-backs bump.
- **T142 texture windows:** the captured span comes from the bound format, size, mips and pitch (`tex_src_span`). A window that changes it changes `nbytes`, and every path, epoch included, recaptures on a size change.
- **Write paths:**
  - CPU and SPU-DMA writes inside an epoch: reused, which is the qualification above.
  - Writes in a later epoch: seen.
  - GPU-generated RTs reach guest memory only through write-back, which bumps.

## 7. Implemented optimizations

| Commit | Switch | What it does |
|---|---|---|
| `b513c55` | `PS3_TEX_SNAPSHOT_WWATCH=1` (backend **and** the port's reservation read it) | `ps3emu/tex_wwatch.h`, described below. The store (`tex_snapshot.h`) records the generation at the start of each capture and reuses the latest copy, without a hash, when no page of the same key and size has a newer stamp. |
| `b513c55` | `PS3_TEX_SNAPSHOT_STATS=<ms>` | the §2 instrumentation |
| `dd0beee` | none | the test requires identical handles to the hash-only store |

**How `ps3emu/tex_wwatch.h` works:**
- It harvests a range with `GetWriteWatch(WRITE_WATCH_FLAG_RESET)`, in chunks no larger than its result array, so every dirty page is returned and reset atomically.
- It stamps each dirty page with a new generation, kept in a 4 MiB table of its own. A reset made for one texture therefore never hides a write from another texture that shares the page.
- Whatever it cannot answer falls back to the old path: an unwatched arena, a failed call, a page size other than 4 KiB, or a stamp wrap.

**Properties:**
- **Ordering:** the epoch check stays first, so with both switches on, the T122 behaviour is unchanged.
- **Default path:** only counter increments are added. Behaviour and output are unchanged.

## 8. Correctness validation

| Test | Result |
|---|---|
| `tools/test_tex_snapshot_wwatch.py 8` | **PASS**. See the list below. |
| `tools/test_tex_snapshot_epoch.py` (T122 pins, store, race model) on the T150 tree | **PASS**: 65 checks, 0 failures |
| `t150/probe/wwatch_probe.c` | **PASS**: every write path in §5 B seen; costs in §9 |
| Regression suite (`run_all` on the T150 tree vs the T146 base) | see §8a |

**What `test_tex_snapshot_wwatch.py 8` covers:**
- **Every capture verified:** 44,982 checks, each comparing the capture against the guest bytes at capture time.
- **Cases:**
  - no write → reuse;
  - write → recapture;
  - same-value write → hash reuse;
  - another thread's store; `fread`;
  - two textures sharing a page; an alias at another offset;
  - a size change; key eviction;
  - frame boundaries with the epoch on;
  - an unwatched arena, which falls back.
- **Differential run:** 8 seeds × 4,000 steps against the hash-only store; **identical handles, copies and reuses**, with 51% fewer bytes hashed.
- **Mutations caught:**
  - the store ignores the generation;
  - the source trusts the OS bits only;
  - the source harvests only one page.
- It also re-runs `test_tex_snapshot.c` and the switch pins (port included).

**Why rendered output cannot change:** a write-watch skip means no byte of the range was written since the latest capture began. The default path would therefore hash equal and return the same handle, and the upload reads the same bytes (VERIFIED by the differential test). Texture windows, mips, MSAA, depth-as-colour, samplers and bindings all consume the handle's bytes, which are identical. No barrier or synchronization is touched.

### 8a. Regression suite

VERIFIED. `t150/tools/run_all_t150.cmd --jobs 6 ps3recomp-t149-base ps3recomp-t150-rsx-performance` (the T146 base `80fe5de` against T150 `dd0beee`). Timing-sensitive tests ran serially. Logs are in `t150/logs/suite/` and `logs/suite_run.txt`.

| Tree | PASS | SKIP | FAIL |
|---|---:|---:|---:|
| T146 base `80fe5de` | 134 | 43 | 2 |
| T150 `dd0beee` | 135 | 43 | 2 |

- **Per test:** identical verdicts on all 179 shared tests. The extra PASS is the new `test_tex_snapshot_wwatch`.
- **Both FAILs are inherited** and fail on the base too: `test_rt_pool_srv_layout` and `test_vpc_watch`. They are not suppressed.
- **Renderer tests (PASS in both trees):**
  - T110: sampler xlate, attr0 gate, rtpool victim, WARP;
  - T115 and T115B: mips, cache, WARP;
  - T119: compact, VS memo, draw split;
  - T120 state decode;
  - T122: `test_tex_snapshot_epoch` and the C `test_tex_snapshot.c`;
  - T133 image quality;
  - T137: MSAA logic, WARP with the debug layer;
  - T141 blend/feedback WARP;
  - T144 stencil WARP;
  - T145 shader window WARP.
- **Not in this suite:**
  - GBV runs: no D3D12 call changed.
  - T142 and T143 harnesses: they are not in the T146 tree list. The store change sits behind the same handle API.
  - T147: not part of the base.
- **SKIPs** are the 43 POSIX/Metal fixtures, skipped in both trees.
- **Tree state:** the suite rewrites `scratch/ppu_conformance*`. Both trees were restored to HEAD afterwards.

## 9. Synthetic performance results

`tests/bench_tex_snapshot.c`, 31 frames × 7 repetitions, idle machine (no build or game running), medians. Not game FPS.

| Arm | capture ms/frame | p90 | stdev | MB hashed/frame | copies/frame |
|---|---:|---:|---:|---:|---:|
| off | 53.05 | 53.94 | 0.20 | 2140.2 | 1.00 |
| epoch (T122) | 1.18 | 1.29 | 0.003 | 46.5 | 1.00 |
| write-watch (T150) | 1.78 | 2.02 | 0.009 | 0.5 | 1.00 |
| both | **0.10** | 0.14 | 0.001 | 0.5 | 1.00 |

**Probe costs:**
- A clean 2 MiB `GetWriteWatch(RESET)` costs 2.1 µs; a dirty one costs 9.7 µs. Hashing the same 2 MiB costs about 60 µs.
- The first guest store per page after a reset costs about 0.33 µs; a store without a reset costs 0.008 µs.
- The writer arm pays about 20 µs per frame for a 256 KiB texture rewritten every frame.
- **Memory:** +4 MiB stamp table (only with the switch on). GPU time: unchanged, since the uploads are the same.

**Validation layers:** not exercised. No D3D12 call changes, and the store has no GPU path.

## 10. Remaining RSX bottlenecks

From the T149 race runs (`RSX_FRAME_COST_BREAKDOWN.md`):

| Cost | T146 defaults | Performance preset | Owner / next step |
|---|---:|---:|---|
| texture snapshot | ≈ 69 ms | ≈ 1.3 ms | this task: epoch (T122) and/or write-watch (T150) |
| vertex expansion (rest of `expand_ms`) | ≈ 43 ms (fat 256-byte vertices) | ≈ 14 ms (compact) | T119 `RSX_VP_COMPACT` (present, opt-in); next would be the indexed-vertex dedup (T119 §12) |
| command recording `cmd` | 6.4 ms | 3.0 ms | |
| texture / PSO binding | 1.6 / 1.5 ms | 1.4 / 1.6 ms | T143 SRV reuse / bind dedup |
| submit + wait + present | ≈ 0.4 ms | ≈ 0.3 ms | none: the GPU is not the gate |
| frame-clock thread idle | 4.3 ms | **54 ms** | the renderer is not the gate in the preset |

**Present and active in the performance preset (T149 P1 env):**
- T119 compact + VS memo (`RSX_VP_COMPACT`, `RSX_VS_MEMO`);
- T122 epoch;
- T143 SRV reuse and bind dedup;
- the shader cache.

T116's state was not checked separately (HYPOTHESIS: covered by the T146 integration).

**Prioritisation:** with the preset on, the renderer works about 29 ms of an 87 ms pass. Its work is serial with the guest frame (T149's 26 ms ref wait), but the frame's largest gate is the PPU frame thread's own compute (56 ms). Of the renderer costs, fat expansion (default config) is the largest, and it is already solved by an opt-in.

## 11. Runtime configuration

| Switch | Default | Effect |
|---|---|---|
| `PS3_TEX_SNAPSHOT` | 1 | the snapshot class (unchanged) |
| `PS3_TEX_SNAPSHOT_EPOCH=1` | off | T122 epoch skip |
| `PS3_TEX_SNAPSHOT_WWATCH=1` | off | T150 write-watch skip. Needs the `port-t150` reservation (the same variable); without it, prints the "on" line, fails its first lookup, and hashes as before |
| `PS3_TEX_SNAPSHOT_STATS=<ms>` | off | `[tex-snapshot-stats]` lines |

**Build:**
- `t150/tools/build_t150.cmd` builds `build/motorstorm-t150`;
- clang-cl 23.1.3 Release;
- the T146 cache options (as T149);
- from `ps3recomp-t150-rsx-performance` and `port-t150`.
- Result, exe hash and suite: §11a.

### 11a. Build and suite results

VERIFIED.
- **Build:** `t150/tools/build_t150.cmd`, rc = 0. Log: `t150/logs/build_t150.txt`.
- **Compiler:** Clang 23.1.3 (clang-cl, MSVC-like), Release.
- **Sources:**
  - ps3recomp `ps3recomp-t150-rsx-performance` at `dd0beee`; base `80fe5de` = T146; T147 not included;
  - `port-t150` = `port/` plus the `PS3_TEX_SNAPSHOT_WWATCH` reservation flag.
- **Exe:** `build/motorstorm-t150/MotorStormPacificRiftRecomp.exe`, 383.9 MB, sha256 `36f2aa78e4f53b7075ce7084e2a725df44c873643dcf23e0c6fa8a0c7d45f942` (`logs/exe_sha256.txt`).
- **A/B pin:** the exe is pinned as `t150/ab/exe_b/` (`run_t150ab.py prepare b`). `dryrun D` passes preflight and shows the expected env. Nothing has been launched.
- **Switches:** all T150 switches are off by default. With them unset, the exe behaves as T146 (arm A).
- **Suite:** §8a.

## 12. Proposed game A/B test (needs authorisation)

- **Runner:** `t150/ab/run_t150ab.py`, generated by `make_runner.py` from T149's runner, with the same route, intro skip, controller, stop at race entry + 90 s and 440 s cap.
- **Every arm:**
  - sets T146's defaults explicitly;
  - adds `PS3_TEX_SNAPSHOT_STATS=1000`;
  - keeps the T149 diagnostics and the critical-path trace (host 175–240 s).
  - `ana_t150.py` reports `trace_covers_race` (race entry ≤ 165 s; T149's arms entered at 149–154 s).

| Arm | Env |
|---|---|
| A | T146 baseline |
| B | A + `PS3_TEX_SNAPSHOT_EPOCH=1` |
| C | A + `PS3_TEX_SNAPSHOT_WWATCH=1` |
| D | A + both |

- **Runs:** 2 per arm, interleaved A B C D A B C D, so **8 launches**, sequential, with no build running.
- **Collected per run:**
  - FPS and frame-time percentiles (`ana_t122`);
  - `[rsx-frame-perf]` medians;
  - `[tex-snapshot-stats]`: hash time, counts, write-watch state, torn/evicted;
  - phases and critical path (`ana_t149`);
  - host CPU per role (trace);
  - CELLMARK frame dumps for a visual comparison (gameplay is not deterministic, so frames are compared visually, not by pixels);
  - D3D12 warnings from `stderr.log`.
- **Pass criteria for C/D:**
  - the snapshot ms per frame falls as §9 predicts;
  - `torn`, `evicted` and `failed` are no higher than A;
  - write-watch `state=1` with `unknown=0`;
  - no visual difference in the dumps.

```
py -3 generated/analysis/t150/ab/run_t150ab.py prepare b
py -3 generated/analysis/t150/ab/run_t150ab.py launch A a1     (then B b1, C c1, D d1, A a2, ...)
py -3 generated/analysis/t150/ab/ana_t150.py <rtdir> <run_dir>
```

## 13. Integration instructions

1. Cherry-pick ps3recomp `b513c55` and `dd0beee` onto the next unified baseline. They touch only `tex_snapshot.h`, the new `tex_wwatch.h`, the backend's snapshot init/stats, and new tests.
2. Apply the `port-t150/main.cpp` hunk (`alloc_guest_vm`: `MEM_RESERVE | wwf`) to `port/main.cpp`.
3. Run `python tools/test_tex_snapshot_wwatch.py 8` and `python tools/test_tex_snapshot_epoch.py`.
4. Keep both switches opt-in until the §12 A/B passes.
   - **Write-watch** is the safer candidate for a default: it is output-identical to the current default path.
   - **The epoch** has the qualification in §6.
