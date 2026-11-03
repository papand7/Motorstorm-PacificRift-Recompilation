# T119: renderer performance, per-draw work in the D3D12 VP path

Date 2026-10-27. Worktree `ps3recomp-t119`, branch `agent/t119-renderer-performance`. Nothing merged, pushed, built as a game exe or launched. All numbers below are **offline and synthetic**; no FPS claim is made.

## 1. Base and commits

| | Commit | What |
|---|---|---|
| Base | `2562ba8` | T113 tip (runtime-verified exposure/shoreline fix). Ancestry: T113 ← `74fd084` ← `19d6b6d` ← T110 `e3b961d`. T113 worktree clean, not modified. |
| 1 | `3c1dc21` | `RSX_DRAW_SPLIT=1`: per-stage timers inside the indexed draw callback (`ps3emu/draw_split.h`), `bench_draw_path.c`, `test_draw_split.c` |
| 2 | `a1875dd` | 10 per-draw/per-bind/per-record `getenv` calls read once (8 switches) |
| 3 | `be4f4e7` | `vp_get_vs` memo of the last lookup (`ps3emu/vp_vs_memo.h`), `RSX_VS_MEMO=0` disables |
| 4 | `693169a` | `RSX_VP_COMPACT=1` (off by default): compact indexed strip/fan records (`ps3emu/vp_compact.h`) |

Private tooling: `generated/analysis/t119/tools/` (`tu_t119.cmd`, `build_bench.py`, `bb.cmd`, `patch_*.py`, `run_suite_t119.cmd`, `diag/getenv_count.*`); logs, binaries and scratch variants under `logs/`, `bin/`, `scratch/`.

## 2. Profiling architecture (VERIFIED by reading the code)

- `RSX_FRAME_PERF` (`ps3emu/rsx_frame_perf.h`), one line per guest frame:
  - `drain_ms`: all of `cellGcm_rsx_process_fifo`, i.e. method decode plus the draw callbacks.
  - `draw_cb_ms`: inside the draw callbacks. `expand_ms` = `draw_cb_ms` − `flush_ms` (early replays started from a callback) − `vs miss_ms` (VS compiles).
  - `rf_ms`: `render_frame` passes, split into `record_ms` (`tex`, `pso`, `cmd`), `submit_ms`, `wait_ms` (GPU drain and next-frame wait) and `present_ms`.
  - `other_ms`: wall time minus drain minus passes outside the drain, i.e. the RSX thread's idle time.
  - Nesting: `flush_ms` and VS misses lie inside `draw_cb_ms`. `rf_in_drain` lies inside `drain_ms` and is subtracted before `other_ms`. No double counting.
- **New `RSX_DRAW_SPLIT=1`** (needs `RSX_FRAME_PERF`) splits `expand_ms` into 12 disjoint `__rdtsc` intervals:
  - `entry`, `room` (make_room), `count` (count/reserve), `emit` (index fetch, assembly, fetch/convert, write);
  - `post`, `fields`, `vs`, `extra`, `texsnap`;
  - `cb_fp`, `cb_vp`, `cb_rest` (the three parts of `vp_record_cb`).

  Early replays and VS compiles inside a stage are subtracted. VERIFIED: the split total equals `expand_ms` (39.18 vs 39.2 ms). Off by default: one branch per stage.
- **Not covered** (from the brief's list of 12): guest PPU, SPU jobs, and GPU execution. There are no timestamp queries; see §8.

## 3. Offline harness (VERIFIED working)

`libs/video/tests/bench_draw_path.c` links the real backend TU (exact game flags) with `rsx_commands.c`, the vertex fetch/compact code, both decompilers and `rsx_texture_layout.c`. It stubs the cellGcm hooks and drives the backend callbacks on the host D3D12 hardware device (CPU: Ryzen 5 9600X, 6 cores / 12 threads).

A frame, shaped after the race RSXI capture `t87b-race-stall f004062`:
- 2000 indexed `TRIANGLE_STRIP` callbacks of 256 u16 indices with a 0xFFFF restart every 5 indices;
- stride-28 vertices: a0 float3, a2/a3 ubyte4, a8 float2;
- 8 batches per BEGIN/END, each with new object constants and 4 texture binds;
- a colour+depth clear, then a flip.

Result: **613,797 expanded vertices and 150 MB/frame**, matching T106's 617k / 151 MB.

## 4. Decomposition of `expand_ms` (VERIFIED offline, 2000 callbacks/frame)

Base T113 tree: `expand_ms` 38–41 ms (19.5 µs per callback).

| Stage | ms/frame | Evidence |
|---|---|---|
| emit: writing 256-byte vertices into the upload heap | **~13** | Writing to cacheable scratch instead: emit 22 → 9 ms. Plain or streaming SSE stores: no change, so it is bandwidth-bound, ~11.5 GB/s. |
| emit: index fetch, assembly, attribute fetch/convert | ~9 | the same scratch variant |
| uncached `getenv` (4 per callback; 2 per texture bind outside the callbacks) | **~12** | Count shim: 10,000 calls/frame. `cb_rest` 7.5 → 0.7 and `cb_fp` 4.0 → 0.16 ms once cached. |
| VS lookup: end-bit scan + byte FNV of the VP | 2.5 (64-instr VP) to 13.9 (512-instr VP) | VP length sweep |
| FP constant extraction (`fp_extract_consts`) | ~0.15 | `cb_fp` after caching |
| everything else (room, count, fields, extra, texsnap, 8 KiB CB copy) | ~2 | split |

- **T114's 6–20 ms conversion estimate holds** for the conversion itself (~9 ms here; T114's `bench_vp_expand` S5 gives 6.7 ms at 4 attributes on this machine). The 256-byte writes cost more than the conversion.
- **The in-game 107 ms is not reproduced** (offline 38–41 ms). Ruled out offline:
  - game-sized environment: +10%;
  - T106's diagnostic environment: ~0;
  - 6 or 11 CPU-burner threads: +0–5%;
  - VP/FP length: covered by the sweep.

  HYPOTHESIS for the rest: real attribute count/types and cache footprint, a longer race VP, upload-heap contention with the GPU's reads, and the T109 tree measured by T106 versus T113. The runtime run with `RSX_DRAW_SPLIT=1` (§11) settles this.

## 5. Implemented optimizations

All four commits change no game-visible behaviour (the compact path is opt-in and bit-identical, §7).

**getenv caching (`a1875dd`).**
- Sites read once: `NO_ALPHATEST`, `VP_NOFIXPROJ` and `VP_FIXPROJ` (`vp_record_cb`); `FP_CONSTBUF` ×2 (`vp_get_fp_pso`, per replayed record); `VP_ATTRS`; `VTX_DUMP` ×3 (tris and both quad expanders, the latter **per quad**); `MOVIE_BIND` and `TEXFMTDBG` (`bind_texture`).
- Only `np_psnr.c` sets environment variables at run time, and only its own keys.

**VS memo (`be4f4e7`).** It keeps the last program's start, its bytes through the end bit, its hash and its slot. A hit requires the same start, a `memcmp` match and the cache still holding that hash at that slot, so the answer equals the full lookup by construction. Program changes per record in RSXI: race 8 in 317, garage 53 in 657.

**Compact records (`693169a`, `RSX_VP_COMPACT=1`).**
- Record layout: one 256-byte template of all 16 slots, then only the active slots per vertex.
- Input layout: VP PSOs take ATTRi from input slot i.
  - Fat records bind 16 views at +16i, stride 256: the same bytes as the old single view.
  - Compact records bind each active slot at its offset in the record, shifted back by `(rec/256)·stride` so the draw keeps `StartVertexLocation = rec/256`. Constant slots use stride 0 on the template.
- Unchanged: the `DrawInstanced` call and the RSXI query bracketing it. Reservation stays in 256-byte units. Merges never join a compact record. Every other record site clears the fields.
- Only indexed strips/fans, i.e. the race path. The non-indexed and tris/quads paths stay fat.

## 6. Before/after (synthetic; median / p95 / max over 20–31 frames)

| Build | `expand_ms` | Notes |
|---|---|---|
| T113 base (`bin/base`) | 38–41 (per-frame range) | |
| + instrumentation (1) | 37.9 median (max 40.1) | |
| + getenv (2) | 27.4 median (max 29.0) | −28% |
| + VS memo (3) | 25.9 (64-instr VP); 25.6 (512-instr VP, was 37.8) | |
| + `RSX_VP_COMPACT=1` (4) | **10.0 / 11.1 / 11.8** | fat in the same exe: 26.6 / 28.1 / 28.9 |

- With compact records: upload 150 → **38 MB/frame**, early replays 1 → 0, `draw_cb_ms` (with replay) 36.8 → 15.1 ms, replay `record_ms` 3.7 → 3.5 ms (the 16 view binds cost nothing measurable).
- Memory: +16 KiB static (memo) and +8 bytes per draw record. The vertex-buffer need falls by about 74%.

## 7. Correctness tests

- **`test_vp_compact.c`:** 28.8 M slot fetches, with D3D12 input-assembler addressing, are identical between the fat and compact layouts.
  - Coverage: random 1–15-slot sets, NaN/denormal bit patterns, records deep in the buffer half.
  - Five broken variants all fail it: no slot advance, wrong template offset, wrong source slot, missing start shift, `vpc_want` passthrough.
- **`test_vp_vs_memo.c`:**
  - One-byte rewrites at every program offset, the end bit, bytes past it, start/size/slot changes.
  - 120,000 random lookups with rewrites, reloads, store resizes and evictions equal the unmemoised model.
  - Two broken variants fail it (643 and 1 failures).
- **`test_draw_split.c`:** passes.
- **`tools/test_t119_pins.py`:** 7 pins and 21 mutations, all pass. The mutations reintroduce each `getenv`, break the memo order or copies, and remove compact layout, replay, record or reservation details.
- **GPU image equivalence (D3D12 debug layer on, 0 errors):** frames dumped by the backend are byte-identical between fat and compact:
  - 1200 draws (neither replays early): 6/6;
  - 2000 draws with the compact run forced to replay at the same record: 6/6;
  - the 16-slot layout with fat records only: identical to the old single view.
- **Finding (VERIFIED, pre-existing, not T119's):** an early replay changes this harness's image (2000 draws, fat: whole-image differences against an unsplit frame). With compact records, race-sized frames no longer replay early. Flagged for T120. The cause is not investigated (HYPOTHESIS: state not carried across the split pass).
- **Suite** (`logs/suite_t119.txt`, T113 and T119 trees):
  - 86 PASS, 2 SKIP; the same 3 FAIL in both trees: `test_vpc_watch`, `test_rt_pool_srv_layout` (inherited) and `c_fp_span` (my runner's link line).
  - T119 updates one inherited pin: `test_geom_expand`'s model of the indexed strip reservation, which now goes through `vpc_want`.
- **TU with the exact game flags:** rc 0, warnings 2944 → 2996, no new warning class.
- **Audit:** `--staged` shows the same 25 inherited BLOCK items at every commit; `--tree` on the staging copy of the 10 changed files passed.

## 8. Shader/PSO and GPU (Phases 5–6)

- **VERIFIED:** T116's `rsc_pso_key` hashes every input element's `InputSlot` and `AlignedByteOffset`, so compact-mode PSOs get their own keys and no stale cached PSO is reused.
- **VERIFIED in harness:** no VS compile after frame 1 (`vs=0/2000` misses) and no PSO miss after frame 1.
- **HYPOTHESIS:** whether compiles still occur during racing (T106: stalls at race frame ~543) needs the runtime run with T116's cache.
- **Not done:**
  - GPU timestamp queries: no GPU time is measured.
  - Barrier/occupancy analysis.

  T106 measured the RSX thread busy 130 of 134 ms (CPU-bound). Compact records also cut the GPU's vertex reads by 74%.

## 9. Expected runtime impact (HYPOTHESIS until §11)

Offline, per-draw CPU work in the draw callbacks drops 38–41 → 10–12 ms per race-shaped frame, about 3.5×.

If the in-game 107 ms is dominated by the same stages (the split will show it), the RSX drain could shrink by several tens of ms per frame. The RSX thread was the saturated stage in T106 (B arm: 4 ms idle).

The next bound would be SPU/PPU work: the T106 ref throttle waits 45–80 ms. No FPS figure is claimed.

## 10. Integration

`git merge-tree`, read-only:

| Branch | Result |
|---|---|
| T115B `65d2695` | clean |
| T118 `74fd084` | clean |
| T116 `30b817b` | conflict (1 hunk in the backend) |
| T117 `fd97181` | conflicts (10 hunks) |

The T113 base alone produces the same T116/T117 conflicts (both branch from T110 `e3b961d`), and no hunk touches T119 code.

Suggested order:
1. T113 + T116 (resolve its one hunk) and T117.
2. Then T119, which then merges as cleanly as it does on T113.
3. Then T115B.

Coordinate with T120: no visual or exposure semantics changed.

## 11. Controlled race A/B plan (not run: needs authorization)

- **Executable:** one exe, built from the integrated tree including T119 `693169a`.
- **Same for every arm:**
  - T106 route and window: race entry +10 to +80 s, stop at +90 s;
  - SPURS defaults, resolution, `PS3_TEX_SNAPSHOT`, shader-cache setting, fresh HDD copy, pad automation;
  - `RSX_FRAME_PERF=12,10 RSX_DRAW_SPLIT=1`.

| Arm | Env |
|---|---|
| A0 (optional) | the T113 exe `generated/analysis/t113/exe` (no T119: `getenv` caching cannot be switched off) |
| A | `RSX_VS_MEMO=0` |
| B | defaults (memo on) |
| C | B + `RSX_VP_COMPACT=1` |

- **Order and count:** A B C C B A, 2 runs per arm.
- **Measure:**
  - average FPS; frame interval median, p95, p99 (excluding the known compile stalls, reported separately);
  - `[rsx-frame-perf]`: `drain`, `expand`, `flush`, `rf`, `record`, `wait`, `other`, `upload_mb`, `verts`, `draw_calls`, early replays;
  - `[rsx-draw-split]` stages; VS/PSO misses; SPU busy lanes and ref throttle.
- **Visual equivalence:** `CELLMARK_DUMP` frames A vs C. Expect identical images except where A replays early and C does not (§7 finding). Check by luminance sequence and per-frame diff, not by eye.

## 12. Remaining bottlenecks

- The 107 vs 40 ms gap: settle it with the runtime split.
- Conversion (~9 ms offline): fetch and convert run through a per-attribute function pointer, with `rsx_fetch_attrib`'s generic switch per component.
- 256-byte writes on the non-indexed, tris and quads paths (not compact yet).
- Indexed rendering: about 205 unique per 309 expanded vertices, i.e. a further third of the vertex bytes. Not done; compact first.
- Texture binds read guest memory for `TEX_PROBE`/`MOVIE_BIND` only when those switches are set; now cheap otherwise.
- GPU timing is not instrumented.

## 13. Classification summary

- **VERIFIED (offline):**
  - the decomposition in §4;
  - `getenv` costs about 12 ms per synthetic frame;
  - the 256-byte writes are bandwidth-bound;
  - the four commits' before/after;
  - compact = fat bit-for-bit (CPU model and GPU images);
  - the early-replay image difference exists;
  - T116 key compatibility; merge-tree results.
- **PARTIAL:**
  - race representativeness of the synthetic frame (shape matches; data, attributes and VP are synthetic).
- **HYPOTHESIS:**
  - why the game measures 107 ms;
  - runtime FPS impact;
  - the cause of the early-replay difference.
