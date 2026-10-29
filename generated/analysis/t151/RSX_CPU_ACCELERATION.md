# T151: RSX CPU pipeline acceleration

Labels: VERIFIED (measured), PARTIAL (measured once, or synthetic), HYPOTHESIS (inferred), BLOCKED (needs a game run).
No game was launched. Cost breakdown: `RSX_CPU_COST_BREAKDOWN.md`.

## 1. Baseline

| | |
|---|---|
| Base | `80fe5de`, the tip of `integration/t146-unified-runtime` (T146 unified runtime, the build T149 measured) |
| ps3recomp worktree / branch | `ps3recomp-t151-rsx-cpu` / `agent/t151-rsx-cpu-acceleration` |
| Root-repo worktree / branch | `root-t151` / `agent/t151-rsx-cpu-acceleration`, from `main` `4bdeed3`; holds `port/` and these reports |
| Build copy | `port-t151/`: a copy of `root-t151/port`, because `port/CMakeLists.txt` reads `../generated` |
| Host | Ryzen 5 9600X, RTX 5060, Windows 11; clang-cl 23.1.3 with the game's backend flags |
| Bench configuration | "P1-like" = `RSX_VP_COMPACT=1 PS3_TEX_SNAPSHOT_EPOCH=1` (the performance preset's vertex and snapshot switches); "fat" = T146 defaults |

## 2. Profiling results (summary of the breakdown)

In game, P1 (T149 run, one run), per frame:
- **drain 18.9 ms:** vertex expansion 15.7, FIFO/state/other callbacks ≈ 3.2;
- **`render_frame` 9.7 ms:** record 6.0 (tex 1.4, pso 1.6, cmd 3.0), unsplit ≈ 3.4;
- **idle 54 ms.**

P0 (T146 defaults): drain 118.9 ms, of which the snapshot (T150's area) is ≈ 69 and fat vertex emit ≈ 43.

**Both the drain and `render_frame` run on the frame-clock thread**, so they are serial with each other and with the guest's fence waits.

## 3. Confirmed bottlenecks (outside T150's snapshot)

1. **Vertex emit (VERIFIED):** ≈ 14 ms in P1, ≈ 43 ms in P0.
   - Offline (compact) it splits into attribute fetch/convert ≈ 5.1 ms, index read/strip assembly/cache lookups ≈ 3.5 ms and writes ≈ 0.6 ms.
   - Each attribute fetch was an indirect call into another translation unit. That call re-read the attribute registers, switched on the type, called `cellGcmResolveLocated` and called `rsx_rd_bef` for each component.
2. **Frame-clock idle latency (VERIFIED from code, size BLOCKED):** `port/main.cpp` sleeps a flat `Sleep(4)`.
   - The kick event that the guest's reference poll raises when a fence is not ready has no waiter in the game.
3. **Lesser costs, each measured but not acted on (VERIFIED):** command recording (3.0 ms), PSO lookup (1.6 ms) and texture bind setup (1.4 ms).
   - The PSO lookup has 0 misses. Each lookup re-scans the fragment-program ucode 6–8 times: span, size, code hash, texture units, gamma/expand units and WPOS.

## 4. Implemented optimizations (all opt-in, defaults unchanged)

### 4.1 `RSX_VP_FAST_FETCH=1`: per-draw vertex fetch plan

- **ps3recomp commit:** `eda5223`.
- **What it does:** builds `include/ps3emu/vp_fetch_plan.h` once per draw.
  - It records the type, component count, stride and location of each active slot.
  - It resolves the address once per 1 MiB offset page. The real `cellGcmResolveLocated` maps whole pages linearly, and `tools/test_vp_fetch_plan.py` pins that.
  - Float32 and ubyte-normalised arrays are read inline with `rsx_fetch_attrib`'s exact expressions. Dividers and every other type take the original generic fetch.
  - Compact records skip the 256-byte template copy, since only the active slots are read. The exception is while `VTX_POS` is printing.
- **Off:** the race-path loop is the original loop, verbatim.
- **Eliminated work:** per attribute, two calls, the register re-reads, the type switch, the per-component calls and the per-vertex address resolve. Per conversion in compact mode, the template copy.

### 4.2 `PS3_FRAME_CLOCK_KICK=1`: frame clock woken by FIFO kicks

- **Root-repo commits:** `df0feb9`, plus `eb518cb` (fix: the log line's string literal had a newline in it, caught by the exe build) and `407dea1` (pins that line).
- **What it does:** the frame clock waits in the framework's `cellGcm_fifo_kick_wait(4)` instead of `Sleep(4)`.
  - The ceiling stays 4 ms.
  - A guest spinning on the reference register while the drain has not published its fence wakes the drain immediately. The kick is raised only when the fence is not yet published (`cellGcm_ref_on_poll`, at most once per 200 µs).
- **Unchanged:** the same thread runs the beat, flip present, drain and pump, in the same order. Guest FIFO order, semaphores and flips are untouched; only the moment the next drain pass starts moves earlier.

### Considered and not implemented

| Item | Why not |
|---|---|
| Indexed output (index buffer instead of de-indexing) | The writes it would save measure only ≈ 0.6 ms (compact), and it would add replay and record risk. |
| SIMD byte swap | Gain about 1 ms. 16-byte loads can cross the end of the guest arena unless they are bounds-checked. |
| Cross-draw vertex reuse | Needs guest-memory dirty tracking (T150's area). |
| FIFO predecode | The walk costs ≈ 1.9 ms. |
| PSO-lookup memo | ≈ 1 ms on the FIFO thread; next on the list (§8). |

## 5. Correctness evidence

**`RSX_VP_FAST_FETCH`:**
- `libs/video/tests/test_vp_fetch_plan.c`, run by `tools/test_vp_fetch_plan.py`:
  - 2.44 M vertices over 1600 random draws. They cover every attribute type, sizes 0–4, stride 0, both locations, dividers in both modes, indices up to `0xFFFFFFFF`, and arrays crossing 1 MiB pages under a page-remapping resolve. Results are byte-equal to `rsx_fetch_attrib` (full mode: 16 slots; compact: active slots).
  - A resolve that is not linear inside a page is caught (185 of 200 draws differ).
  - Five mutations are caught: no byte swap, no in-page delta (crash), no default write, dividers inlined, `×(1/255)` instead of `/255`.
- Pins in `tools/test_vp_fetch_plan.py`:
  - the switch reads exactly `"1"`, once;
  - the plan is built from the cache's active-slot rule;
  - the off loop is the original;
  - the real resolver's page linearity, for `ResolveLocated`, `ResolveIO` and `ResolveOffset`.
- `tools/test_vp_expand.py`: pin updated for the wrappers, PASS. `test_t119_pins.py`: 28/28.
- **GPU (D3D12 debug layer on, RSXI snapshots compared byte for byte):** 16 configurations × off/on/rerun-on, 48 runs. All on-arms are **identical** to off, with **0** debug-layer errors or corruption. Warning counts are equal off/on and inherited.
  - The configurations are:
    - the race path, fat;
    - the race path, compact;
    - the race path with the full performance preset (compact, epoch, SRV reuse, bind dedup, shader cache);
    - the race path with the visual set (`RSX_GUEST_SAMPLERS=15`, mips, depth state, FP precision, stencil exact);
    - the race path with GBV;
    - the T143 bench, plain and with the preset and samplers;
    - T141 (all feedback/MRT/zeta switches, and GBV + feedback + compact);
    - T137 MSAA (with feedback, and plain with compact);
    - T145 (all window switches + colour transfer);
    - T142 (linear feedback; MSAA);
    - T144 (stencil exact; depth state + compact).
  - Script: `tools/harness/t151/correct.sh`. Log: `logs/correct_r1.txt`.
  - Not exercised on the GPU: the ubyte attributes, because the bench's fragment program does not read them. The C test covers them bit for bit.

**`PS3_FRAME_CLOCK_KICK`:**
- `root-t151/tools/test_frame_clock_kick.py` pins:
  - the switch, read once;
  - `Sleep(4)` when off;
  - the loop order after the wait;
  - the framework half (wait on the auto-reset kick event, kick only when dry), when given the ps3recomp tree.
- The game effect is untested (BLOCKED).

**Suite** (`tools/run_all_t151.cmd --jobs 4 <ps3recomp-t151-rsx-cpu>`, log `logs/suite_r1.txt`): 133 PASS, 43 SKIP, 3 FAIL. VERIFIED.
- `test_rt_pool_srv_layout` and `test_vpc_watch` also fail on T146 (126 PASS / 43 SKIP / 2 FAIL); they are pre-existing.
- `test_spurs_kick_wake` failed only under host load (it ran beside the exe build, 424 s). It passes alone (`--only test_spurs_kick_wake --jobs 1`, 88 s, `logs/suite_r2_kick.txt`).
- The new and changed pins pass: `test_vp_fetch_plan`, `test_vp_expand`, and `test_frame_clock_kick` (root, with the ps3recomp tree: 0 failures).

## 6. Performance results

### `RSX_VP_FAST_FETCH`

Offline bench (`bench_draw_path 31 2000 8 64 24`), 4 interleaved rounds. Medians per round, ms per frame (frames 6–31):

| Arm (compact + epoch) | callbacks total | emit |
|---|---|---|
| base `80fe5de` | 10.19 / 10.27 / 10.46 / 11.11 | 9.05 / 9.09 / 9.29 / 9.58 |
| T151, switch off | 10.35 / 10.45 / 10.48 / 10.83 | 9.22 / 9.32 / 9.35 / 9.41 |
| **T151, `RSX_VP_FAST_FETCH=1`** | **6.79 / 6.83 / 6.87 / 7.21** | **5.59 / 5.62 / 5.70 / 6.05** |

- **Saved:** ≈ 3.6 ms per 2000 callbacks (−34% of callback time, −38% of emit). The off path is at parity with the base (within round noise).
- **Fat records (T146 default):** emit 22.4 ms both ways, so there is no gain. Fat is write-bound (256 bytes per expanded vertex).
- **Unchanged:** bytes uploaded (38.2 MB compact), allocations (none), early replays (0), draw records, and the GPU command stream (images byte-identical). GPU time was not separately timed.
- **In game (HYPOTHESIS):** P1's expand of 15.7 ms should drop by about a third, roughly 5 ms, on the frame-clock thread. The in-game fetch is likely costlier than offline, because the real `cellGcmResolveLocated` is used and guest memory is cache-cold.

### `PS3_FRAME_CLOCK_KICK`

Synthetic model `tools/bench_kick_model.c`: a guest submits a fence, then polls with a kick every 200 µs. The frame clock drains after each wait. 400 waits, 2 runs each:

| Arm | mean | p50 | p95 | max |
|---|---|---|---|---|
| `Sleep(4)` | 1698–1699 µs | 1522–1534 µs | 2182–2497 µs | ≤ 2713 µs |
| kick wait | 7–9 µs | 6 µs | 10 µs | ≤ 198 µs |

- **In game (HYPOTHESIS):** the saving per guest fence wait is up to the idle part of a tick. It applies only while the frame clock is idle (P1: 54 ms per frame idle), not while it drains.
- The number of reference waits per race frame is not measured. T149 saw a single site, `0x72E1E0`.

## 7. Integration-ready commits (handoff to T153)

| | `eda5223` (ps3recomp) | `df0feb9` + `eb518cb` + `407dea1` (root repo) |
|---|---|---|
| Base | `80fe5de` | `main` `4bdeed3` |
| Files | `include/ps3emu/vp_fetch_plan.h` (new), `libs/video/rsx_d3d12_backend.c`, `libs/video/tests/test_vp_fetch_plan.c` (new), `tools/test_vp_fetch_plan.py` (new), `tools/test_vp_expand.py` | `port/main.cpp`, `tools/test_frame_clock_kick.py` (new) |
| Switch | `RSX_VP_FAST_FETCH=1` | `PS3_FRAME_CLOCK_KICK=1` |
| Expected benefit | about −1/3 of VP vertex emit with compact records (P1-like); none with fat records | removes up to a tick (≈ 1.7 ms mean, model) per guest fence wait while the drain is idle |
| Tests | as §5 | as §5 |
| Known conflicts | `rsx_d3d12_backend.c` is also changed by T150 (`b513c55`, `dd0beee`). T151 touches only the VP vertex section (`vp_vx_begin`, the three VP expanders) and the include list. T150 touches texture snapshots; no hunks overlap. | `port/main.cpp` is also changed by T150's `port-t150` copy, in `VirtualAlloc` (write watch). T151 touches only the frame-clock loop; no overlap. T150's change is not in git yet. |
| Visual risk | none found: pixel-identical across 16 configurations | none: present/flip order unchanged |
| Memory-ordering risk | the plan resolves an address page once per draw. A concurrent remap of an IO page during one draw callback would be seen at page granularity rather than per vertex. That was already a race in the original. | earlier drains publish fences sooner; the order is unchanged. More frame-clock iterations while the guest spins: at most one per 200 µs kick. |

## 8. Remaining opportunities (ranked by measured cost)

1. **Make `RSX_VP_COMPACT` the default** (T119; VERIFIED in game by T122's exe C, drain 114 → 80 ms).
   - P0's fat emit of ≈ 43 ms becomes ≈ 14 ms, then ≈ 9–10 ms with fast fetch.
   - This is a default change and needs its own review and game A/B. It was not done here.
2. **Take `render_frame` off the FIFO thread.** Record the previous frame's draw records on a worker while the drain walks the next frame.
   - This is 9.7 ms (P1) or 14 ms (P0) per frame of serial work.
   - It needs double-buffered draw records and isolation of the texture cache, the RT pool and the descriptor state that drain callbacks touch. It is a substantial refactor, not attempted.
3. **GPU-side vertex fetch:** upload the referenced guest vertex bytes and an index buffer, and byte-swap/convert in the vertex shader.
   - This removes CPU conversion and de-indexing entirely (the remaining ≈ 5.7 ms compact, ≈ 22 ms fat offline).
   - It changes shader generation and the PSO input layout.
4. **PSO-lookup FP memo:** remember the last program's derived values (span, size, code hash, units, WPOS reads), checked by `memcmp`, as T119's VS memo does. About 1 ms on the FIFO thread.
5. **Split `render_frame`'s unattributed ≈ 3.4 ms** in game with `RF_PHASE_MS`. Offline it is 0.3 ms, so it is game-specific.
6. **Wake the drain on guest PUT stores** (the infamous port's put-store kick, T24 B5). The hook sits in the lifted PPU store path (T152's area).

## 9. Recommended runtime settings

Both are offline-verified and game-unverified. For a game A/B, on top of the performance preset:
- `RSX_VP_COMPACT=1 RSX_VP_FAST_FETCH=1` (fast fetch helps only with compact);
- `PS3_FRAME_CLOCK_KICK=1`.

Keep both unset by default until §10 has run.

## 10. Proposed game validation (needs authorization; not run)

**Exe:** `build/motorstorm-t151/MotorStormPacificRiftRecomp.exe`, 402,527,232 bytes, SHA-256 `a8fc3d09026ad8967508de0d484ab5d31e7329996f6da2d1b758e544473acbe5`.
- Built from ps3recomp `eda5223` and root `407dea1` (`port-t151` copy), using `tools/build_t151.cmd` (log `logs/build_t151b.txt`). It was built but not launched.

**Runner:** T149's (`t149/ab/run_t149ab.py`), same race, `RSX_FRAME_PERF=12,1,100000`. Two runs per arm, arms interleaved:

| Arm | Switches on top of the P1 performance preset |
|---|---|
| Q0 | none (P1 reproduced on this exe) |
| Q1 | `RSX_VP_FAST_FETCH=1` |
| Q2 | `PS3_FRAME_CLOCK_KICK=1` |
| Q3 | both |
| Q4 | Q3 + `PS3_CRITICAL_PATH_TRACE`, to read the ref wait at `0x72E1E0` |

**Measures:**
- race FPS and frame time;
- `expand_ms`, `drain_ms` and `other_ms`;
- the guest ref wait;
- with `RF_PHASE_MS=1`, `render_frame`'s phases.

**Pass criteria:**
- Q1's `expand_ms` falls with records and `upload_mb` unchanged;
- Q2's ref wait falls;
- no visual change: RSXI snapshots of a fixed frame match Q0.
