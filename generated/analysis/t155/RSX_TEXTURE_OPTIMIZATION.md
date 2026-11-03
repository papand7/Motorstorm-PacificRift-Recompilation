# T155: `RSX_TEX_SLOTS`, a texture upload table that holds the heavy scene

2026-10-29. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. Root cause: `HEAVY_SCENE_TEXTURE_ROOT_CAUSE.md`. No game launch beyond the one diagnostic run; the game A/B is only proposed (`GAME_AB_PLAN.md`).

## 1. Change

| Item | Value |
|---|---|
| commits (ps3recomp `agent/t155-rsx-heavy-texture`, from T154 `e8e972a`) | `746ff2c` `RSX_TEXREC_STATS` (diagnostic, read-only) → `f514913` `RSX_TEX_SLOTS` + `libs/video/tests/test_t155_texslots.c` → **`c1512fb`**: keeps the T119/T115 source pins (frame-perf wrapper unchanged, scan-loop pin) |
| switch | `RSX_TEX_SLOTS=<n>`, 96..1024, read once. **Unset = 96 = the old linear scan and first-free replacement.** Recommended: `1024` |
| exe for the A/B | `build/motorstorm-t155` at `c1512fb`, `MSPR_WWS_AOT=ON`, sha256 **`d8483b4a3ed18907b232ca2e8b18a648980a6f53f860241e5a6ffb6559ef1c6c`**, pinned as `ab/exe_f` (not launched) |

**Design.**
- **Capacity.** The slot array (`vp_tex[]`) and its SRV region are sized for 1024 slots, so `RT_SRV_BASE` and the regions after it move up by 928 descriptors. That is not guest-visible. `n` slots are used.
- **Lookup (n > 96).** A key index (4,096 buckets keyed by the bound offset, chained per slot) returns the one slot the old scan would match: same key, w, h, fmt, cube and pitch, and a live resource. The match body is the original one, so the same "bound this pass", checksum, stale re-upload and level-change rules apply.
- **Replacement (n > 96).** A slot with no resource first, else the least recently bound slot (`s_vtx_last_use`, the pass that last bound it) **among slots not bound in this pass**. When every slot is bound in this pass, it returns -1 as before.
- **Lifetime is unchanged.**
  - A slot is only released or overwritten while the pass being recorded does not reference it.
  - Every pass starts with `wait_for_gpu()`, so no earlier submission is in flight.
  - The upload buffer of a slot is written at most once per pass, because a slot bound in this pass is never chosen.
- **Unchanged:**
  - the per-pass "bound" reset and the first-bind checksum of every kept texture in every pass, so guest, DMA and SPU writes between passes are still picked up;
  - `RSX_TEX_CACHE` exact hashing, `RSX_TEX_MIPS`, texture snapshots (T122/T150), RT and zeta sampling, feedback, MSAA, SRV formats, swizzle and samplers.
- **Cost:** one predictable branch per lookup when unset. When set, per-slot state is 4 small arrays; GPU memory holds up to n textures plus their upload buffers, as before but no longer bounded at 96 (§5).

## 2. Offline correctness (VERIFIED; all with the D3D12 debug layer and info queue, 0 errors)

**Heavy-frame harness** `tools/harness/t155/correct_texslots.sh`. RSXI snapshots of render passes 8–15, i.e. guest frames 2 and 3, all 4 passes each. Compared per pass by `tools/cmp_snaps_t155.py`.

| Case | Reference (off) | Tested (on) | Result |
|---|---|---|---|
| 80 textures (fit 96), 6,900 draws, 4 passes | default | `RSX_TEX_SLOTS=1024`, + rerun | 8/8 passes identical ×2 |
| 80 textures, full rewrites inside pass 2 of every frame | default | 1024 | 8/8 identical |
| 300 textures | 1024 + `TEX_NOCACHE=1` (re-upload at every first bind of a pass, so it can never be stale) | 1024, + rerun | 8/8 identical ×2 |
| 300 textures, rewrites inside pass 2 | 1024 + `TEX_NOCACHE=1` | 1024 | 8/8 identical |
| 300 textures, default 96 slots (sensitivity check) | as above | default | **2 of 8 passes differ** (100,320 binds without a slot). Expected: the bug being fixed |

- The test samples unit 0 in every draw, so a stale or missing texture changes pixels. The rewrite case differs from the unmutated reference by 165,164 pixels, which shows the rewrites are visible.
- **Lifetime:** the mutation case shows a texture rewritten between two passes of one guest frame is re-uploaded (100 stale re-uploads per frame, the rewritten share) and never served stale. The `TEX_NOCACHE` comparison checks reuse against a no-reuse reference.

**Existing GPU regression set** (`tools/harness/t155/correct.sh` = T153's `correct.sh` on the T155 tree; off = `RSX_NONE=1`, on = `RSX_TEX_SLOTS=1024`):
- 16 configurations × off / on / rerun_on: `bench_draw_path` (fat, compact, perf preset, visual switches, GBV) and `test_t143_bench` (descriptor reuse / bind dedup);
- `test_t141_backend` (RT window, **RT feedback**, zeta exact, MRT, depth state; GBV) and `test_t137_msaa_backend` (**MSAA**);
- `test_t145_backend` (shader window, feedback, MRT, colour transfer), `test_t142_backend` (**RT sampling**, linear feedback, MSAA) and `test_t144_stencil_backend` (**depth/stencil**).

Result: **32/32 on-arms identical to off on every captured pass**, 0 debug-layer errors, and the same inherited warning counts off and on. Rerun on `c1512fb`: the same 32/32, 48/48 runs with 0 errors (`logs/correct2.txt`); heavy-frame set also identical (`logs/cmp_snaps_t155_2.txt`).

**ps3recomp suite** (`tools/run_all_t155.cmd --jobs 6`): 134 PASS / 43 SKIP / 5 FAIL on `f514913`.
- `test_rsx_frame_perf` and `test_t115_pins` were source pins of the wrapper and the scan loop. They were fixed in `c1512fb`, which keeps the T119 wrapper text and accepts the new loop header in the T115 pin; both PASS.
- `test_spurs_wws_concurrency` failed under load and passes alone; SPU code is untouched.
- `test_rt_pool_srv_layout` and `test_vpc_watch` are the known T146 failures.
- Net: equivalent to T154 (137 / 43 / 2).

## 3. Offline performance (synthetic, `test_t155_texslots`; 3 repeats, no debug layer, T153 preset; per guest frame after 2 warm-up frames)

| Case | Metric | 96 slots (default) | `RSX_TEX_SLOTS=1024` |
|---|---|---|---|
| **heavy**: 6,900 draws (4 passes), 300 textures | texture recording ms (mean, range) | 278.8 (268.6–297.5) | **3.8 (3.7–3.9)** |
| | µs per bind | 10.10 | 0.138 |
| | RSX record ms / RSX wall ms | 288.7 / 350.7 | 13.3 / 72.8 |
| | evictions / re-creations / SRVs per frame | 360 / 264 / 360 | 0 / 0 / 0 |
| | binds without a texture | 16,584 | 0 |
| | decoded MB per frame | 22.1 | 0 |
| **mutation**: heavy + 100 textures rewritten in pass 2 | texture ms | 272.9 (269.1–279.2) | 18.6 (18.4–18.9), re-uploading exactly the 100 rewritten textures (stale 100, decode 8.2 MB) |
| **cache hit**: 6,900 draws, 80 textures (fits) | texture ms | 2.83 (2.70–3.08) | 2.03 (1.80–2.25) |
| **light**: 2,000 draws (1 pass), 80 textures | texture ms | 0.80 (0.76–0.83) | 0.58 (0.54–0.61) |

- There is no regression where 96 was enough: the indexed lookup is cheaper than the 96-slot scan.
- **Upload bytes:** 0 per frame once resident, against 22 MB per frame of re-decode in the default. Re-uploads happen only for textures whose bytes changed.
- **Feedback workloads:** correctness only (§2). RT-sampled units never reach this path, so their cost does not change.
- **The synthetic is harsher than the game.** It has 360 evictions per frame against the game's 227, and the device's resource creation costs differ. The game's 208 ms is **not** extrapolated from these numbers.

## 4. Expected game effect (HYPOTHESIS until the A/B)

- In the diagnostic heavy frame, the work this removes is:
  - 96 ms of resource creation;
  - 31 ms of decode;
  - about 70 ms of the 78 ms not split out (the Releases and re-plans that go with the 227 misses);
  - 0.5 ms of SRV creation.

  If the working set fits in 1024 slots, texture recording should fall from about 208 ms to the light-scene rate per bind, a few ms.
- **The heavy scene will then be bound by what remains:** expand about 50 ms, the rest of record and rf, and the PPU. Its FPS is unknown until measured; only the A/B can say.
- **Visual change (accuracy fix):** the 3,542 binds per heavy frame that sampled nothing will be textured. Objects that rendered black or untextured in the heavy scene should now render correctly.

## 5. Risks and mitigations

| Risk | Mitigation / status |
|---|---|
| working set > 1024 | `[tex-rec] bound=` and `noslot=` per pass in the A/B show it; the cap is a constant |
| GPU memory (Radeon 890M shares system memory) | each kept slot holds the texture and its upload buffer, as before. The heavy-frame working set is unknown (the diagnostic saw only that it exceeds 96); the A/B reports `bound`. If needed, the next step is releasing upload buffers after their copy completes (not done here) |
| stale texture after a guest write | first-bind checksum per pass kept; mutation tests identical to the never-reuse reference |
| use-after-free of an evicted slot | replacement only among slots unbound this pass; GPU idle at pass start |
| default behaviour | unset = 96, linear scan; only the SRV region offsets move; the 32-arm regression set is identical |

## 6. Integration

- **ps3recomp branch `agent/t155-rsx-heavy-texture`:** `746ff2c`, `f514913`, `c1512fb`. Not pushed or merged.
- **Switches:**
  - `RSX_TEX_SLOTS=1024` is the candidate for the performance preset after the A/B;
  - `RSX_TEXREC_STATS=1` is a diagnostic.
- **Defaults are unchanged.**
- **Root branch `agent/t155-rsx-heavy-texture-report`:** reports and tools.
