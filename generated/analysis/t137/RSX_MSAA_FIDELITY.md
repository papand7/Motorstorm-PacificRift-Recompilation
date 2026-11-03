# T137: RSX 2× MSAA and visual fidelity

Date 2026-10-28. Worktree `ps3recomp-t137`, branch `agent/t137-rsx-msaa-fidelity`. Not merged or pushed. No game build or launch.

## 0. Base and branches

- **Base `816a4af`** (the T133 tip). It is explicitly composed of:
  - T113 `2562ba8` (fragment-program span, exposure);
  - T120 `235b3e6` and `169e618` (`RSX_RT_WINDOW`, `RSX_DEPTH_STATE`);
  - T115 `17b16cb`, cherry-picked as `4a74174` (`RSX_TEX_MIPS`);
  - T133 `816a4af` (`RSX_FP_PRECISION`, RSXI `aa_ctl`).
  - T110 guest samplers came in with T113's chain.
- **Not combined** (each touches `rsx_d3d12_backend.c`; reviewed for conflicts in §8):
  - T115B `65d2695`;
  - T116 `30b817b`;
  - T117 `fd97181`;
  - T119 `693169a`;
  - T122 `a0670df`.
- **Commits:** see §11.

## 1. RSX multisample state evidence (race capture I, f006502; G f006314 agrees)

| Item | Captured value | Status |
|---|---|---|
| Scene colour `0x00750000` | `SET_SURFACE_FORMAT 0x3148`: A8R8G8B8, Z24S8, linear, **antialias 3 = DIAGONAL_CENTERED_2**; 1280×720, pitch **10240** (2560×4); 428 draws, ops 167–612 | VERIFIED |
| MRT1 `0x01650000` | same format; MRT B of the scene, then its own target for ops 620–651 | VERIFIED |
| Zeta `0x00ED0000` | bound by every antialias-3 pass (460 draws) | VERIFIED |
| Other targets | bloom/luminance chain, shadow (`0x0B830000`) and UI: antialias 0 | VERIFIED |
| Guest reads | the scene and MRT1 read back as 2524×710 `0xA5`/`0xBF` (pitch 10240), and the zeta as `0xA5` 2524×710: the **sample layout** (pixel x's samples at texels 2x, 2x+1) | VERIFIED |
| Resolve | the game resolves itself. Op 657 `fp_0074B441` draws the scene into the 1-sample `0x01DD0000` with one bilinear tap per sample pair (unit 0 FILTER `0x02022000` = LINEAR), plus MRT1 velocity | VERIFIED |
| `ANTI_ALIASING_CONTROL` (0x1D7C) | the game links the libgcm setter. Lifted code next to `func_0073473C` builds `enable \| a2c<<4 \| a2one<<8 \| mask<<16`. A state-block emitter (`func_007360E0`) writes 0x1D7C from a struct. **No capture holds the runtime value:** RSXI records it from T133 on, and nothing has been captured since | value UNKNOWN |
| Alpha test | off on all 665 draws. Foliage uses shader `KIL` at alpha < 0.5 (T133) | VERIFIED |
| Alpha to coverage, sample mask | depend on 0x1D7C | UNKNOWN |
| Sample positions and order | not in any register | HYPOTHESIS |

Tools: `t137/tools/aa_tally.py` and `expand_cost.py`, plus T133's `tex_tally.py`.

## 2. Register decoding and sample layout (`libs/video/rsx_msaa.h`)

**Antialias modes:**
- 0 is 1 sample.
- **3 is 2 samples, laid side by side: a W×H surface occupies 2W×H texels.**
- 4 and 5 are 4 samples on a 2W×2H grid; not implemented.

**`ANTI_ALIASING_CONTROL` fields:** [0] enable, [4] alpha to coverage, [8] alpha to one, [31:16] sample mask. Reset value `0xFFFF0000` (RPCS3's init).
- As in RPCS3:
  - the sample count follows the surface;
  - alpha to coverage applies only with enable set;
  - the mask always applies.
- **Alpha to one** has no D3D12 pipeline field: it is recorded in the key, not applied.

**Differences from D3D12 MSAA and their likely visual consequences:**

| # | RSX | D3D12 / implementation | Consequence |
|---|---|---|---|
| D1 | samples are memory, readable as texels | opaque 2-sample resource; the guest sees a **sample image** rebuilt from it | exact layout; costs a pass per changed read (§7) |
| D2 | DIAGONAL_CENTERED_2 positions and order undocumented | `D3D12_STANDARD_MULTISAMPLE_PATTERN` (±0.25 diagonal); RSX sample 0 (left texel) = the host sample with the smaller x | HYPOTHESIS. Box resolves (the game's) do not depend on it; a point read of one sample sees the other diagonal half-pixel |
| D3 | enable = 0 semantics | rasterises with 2 samples anyway (RPCS3 behaviour) | HYPOTHESIS until 0x1D7C is captured |
| D4 | alpha-to-coverage dither | the implementation's own pattern (WARP: alpha 0.5 lights 4 of 8 samples) | coverage pattern may differ from RSX |
| D5 | alpha to one | not applied (counted in the key) | blended alpha may differ if the game sets it |
| D6 | 4-sample modes | not implemented | not used by the race |

## 3. D3D12 resource architecture (`RSX_MSAA=1`)

- **Colour.** Each antialias-3 colour target keeps its 1-sample `res`, which every existing consumer reads: snapshots, composite, dumps, 1-sample passes. It gets a **2-sample twin `ms`** that antialias-3 passes render to.
- **Depth.** The zeta gets a 2-sample twin. When there is no zeta, a 2-sample shared depth buffer is used. Depth and colour sample counts always match.
- **Pipeline key.**
  - The guest-FP key's top byte carries the sample count, alpha to coverage, the host sample mask and alpha to one (`dr_ms_key`, OR-ed onto T120's `dr_depth_key`).
  - Pipelines get `SampleDesc {2, standard}`, `SampleMask` and `AlphaToCoverageEnable` from the key.
  - A 2-sample pass has no 1-sample fallback pipeline, so such a draw is skipped and counted (`skipped_draws`).
- **Guest reads.** A guest texture over an antialias-3 surface binds a **sample window**: a texture of exactly the guest's size (2524×710 in the race). The expand pass renders it directly from the 2-sample twin; there is no copy.
  - A read of exactly 2W×H binds the whole sample image, created only on demand.
  - A zeta read as A8R8G8B8 becomes a 2W×H per-sample depth/stencil image.
- **Transitions:**
  - `ms` to `res` is a lazy `ResolveSubresource`, on `res`'s next transition or direct read (the RSXI snapshot paths, composite, dump, present probe: `ms_sync`). No race read needs one.
  - `res` to `ms` is a broadcast pass when `res` holds writes `ms` lacks (guest-memory initialisation, a 1-sample pass, a copy).
  - A sample image is rebuilt only when its surface changed. A target bound at the time is always rebuilt, so a feedback read sees the draws before it.
- **No GPU wait anywhere in the 2-sample code** (pinned):
  - resources are created once per surface size;
  - replaced windows go through T120's deferred `rtwin_retire`;
  - zeta twins go through the zeta graveyard.
- **SRV heap:** new regions `MSRT_SRV_BASE` and `MSZ_SRV_BASE` sit before the draw windows (layout pins pass).
- **RTV and DSV heaps:**
  - a 3×32-entry RTV heap: twins, whole images, windows;
  - a 9-entry DSV heap: zeta twins plus the shared buffer.

## 4. Implemented behaviour

| Area | Behaviour | Status |
|---|---|---|
| 2× colour | antialias-3 targets render with 2 samples | VERIFIED offline |
| Depth/stencil | per-sample depth test and stencil in a 2-sample zeta; per-sample zeta-as-colour image | VERIFIED offline |
| Guest resolve | the game's own bilinear tap on the sample window equals `ResolveSubresource` (max diff 0) | VERIFIED offline, **needs `RSX_GUEST_SAMPLERS`** (below) |
| Feedback reads | a draw reading its own bound 2-sample target sees the prior draws | VERIFIED offline |
| Resize | race-like moving viewports (1259–1265 × 708–712) and texture windows (2518–2530 wide): no recreation of twins, no wait | VERIFIED offline |
| A2C / sample mask | from `ANTI_ALIASING_CONTROL` only when the guest sets it; never forced | VERIFIED offline (synthetic); game value UNKNOWN |
| Zeta-as-colour far plane | with `RSX_MSAA=1` the depth is clamped to 0xFFFFFF. Before, depth 1.0 was encoded as `0xFF0000`: the conversion's `+0.5` rounds 1.0·16777215 to 2²⁴ in float | VERIFIED offline (a pre-existing defect; fixed only under the switch) |
| `RSX_MSAA` unset | every path, shader and pipeline as before | VERIFIED (pins, suite) |

**Dependency, VERIFIED:** the race's downsample samples unit 0. Without `RSX_GUEST_SAMPLERS` unit 0 is the fixed **point** sampler (T133), so the tap picks one sample and the image gets no smoothing; the harness "on" arm shows 0 mixed pixels. `RSX_MSAA=1` must run with `RSX_GUEST_SAMPLERS=15`.

## 5. Synthetic pixel comparisons

**`test_t137_msaa_warp.c`** (WARP, debug layer): **49/49**.
- A rectangle ending at x = 1.5 lights texels 0, 1, 2 and leaves texel 3 dark. That is pixel 1's left sample only (RSX sample 0 = left).
- The resolve gives 255 / 128 / 0, and the guest bilinear tap equals it.
- Depth 0.25 with stencil `0x5A` reads `40 00 00 5A` on covered samples and `FF FF FF 00` on uncovered ones.
- The 1-sample conversion repeats each pixel on both texels.
- Also passing: broadcast, sample mask (RSX sample 0 lands on texels 2x only), and A2C (alpha 0 / 0.5 / 1 lights 0 / 4 / 8 of 8 samples).
- 8 frames at 4 sizes.

**`test_t137_msaa_logic.c`:** 27/27. It covers:
- grids;
- `0x1D7C` decode and reset value;
- key bits (and that they are clear of `rsx_ds_key`);
- the read window, including the race's 2524×710 over 2560×720;
- the texel-to-sample map.

**Real backend, offline** (`test_t137_msaa_backend.c`, project flags, RTX 5060, `D3D12_DBG=1 D3D12_IQ=1`, RSXI at frame 5 with viewport 1260×708):
- **Scene:**
  - pass A (antialias 3): a white triangle with a diagonal edge at z 0.3 and a red quad at z 0.7, then a feedback quad sampling the bound target;
  - pass B: the guest downsample into a 1-sample target;
  - pass D: the zeta read as A8R8G8B8 (NEAREST);
  - pass C: the display.

| Arm | Resolve of RT_A (white / red / mixed) | Guest downsample RT_B | Feedback quad | Zeta image |
|---|---|---|---|---|
| 1 sample, `RSX_RT_WINDOW=1` | 269,578 / 399,482 / 0, plus **223,020 black** | same | **black**: a bound target's window is never refreshed | baseline |
| 1 sample, no window (T113 default) | 391,571 / 499,594 / 915 | 27,103 black at the right edge, 6,291 blurred (the old 1280-vs-2524 scaling) | content kept | n/a |
| **`RSX_MSAA=1` + guest samplers** | 391,539 / 499,707 / **834 mixed (edge)** | **identical to the resolve (max diff 0)**; 834 edge pixels at ≈50% (255,127,127), every other pixel equal to the 1-sample result | content kept | interior identical; 416 edge pixels carry the other sample's depth (0.65 vs 0.85) |
| `RSX_MSAA=1`, no guest samplers | 834 mixed | 0 mixed (point tap) | content kept | same |

Logs: `t137/logs/backend_arms.txt`, `backend_compare_gs.txt`, `backend_compare_nogs.txt`, `backend_off_nowin.txt`; tool `t137/tools/msaa_backend.py`.

**Regression and build:**
- **Offline suite** (`t137/tools/run_suite_t137.cmd ps3recomp-t137`): **39/39 PASS**. It includes T113 `test_fp_span` and `test_exposure_writeback`, T120 `test_rt_window` and `test_depth_state`, T115, T133 and `test_msaa`.
- **TU:** `rsx_d3d12_backend.c` compiles with 0 errors and no new warning class.
- **Audit:** `--staged` reports the 25 inherited BLOCKs and none in a T137 file (`logs/audit_staged.log`).

## 6. Debug-layer validation

- **WARP test:** 0 error or corruption messages.
- **Backend harness, every arm:** 0 errors or corruption. The 16–24 warnings are id 820 (clear value differs from the creation value); they are identical with `RSX_MSAA` off and pre-existing.
- **Counters** at frame 8:
  - binds 7, allocs 1, broadcasts 1;
  - resolves 1 (the RSXI snapshot only);
  - window expands 14, zeta images 7;
  - skipped draws 0, failures 0.
- **Not run:** GPU-based validation, the integrated game (no launch).

## 7. Performance and memory

**VRAM** (race surfaces, RGBA8 and D24S8):

| Surface | Size |
|---|---|
| 2 colour twins | 14.1 MiB |
| 2 sample windows of 2524×710 | 13.7 MiB |
| zeta twin | 7.0 MiB |
| zeta image (2W instead of W) | +3.5 MiB |
| **Total** | **≈ 38 MiB** |

The 2-sample shared depth buffer (7 MiB) exists only when a pass has no zeta.

**Work per race frame** (`expand_cost.py` on captures I and G):
- 9–13 reads of 2-sample targets, giving **8 window rebuilds, 5 of them feedback reads** (ops 594–598 read the bound scene);
- 2 zeta images;
- 0 resolves;
- 0 broadcasts after the first frame.
- That is about **140 MiB of extra traffic per frame**. On an 890M (≈ 90 GB/s effective, shared) that is **≈ 1.5 ms**: an ESTIMATE, not measured.
- The 2-sample rasterisation itself (the scene's 460 draws at twice the colour and depth samples, with compression) is **not measured**; it needs the runtime A/B.

**CPU and frame time:**
- **Harness** (RTX 5060, 300 frames, median from frame 50 on): frame 6.9 ms in both arms; CPU record time 1.6 → 1.8 ms; submit and present unchanged; no new waits.
- **First broken design found by the estimate:** before window-direct expansion, the "rebuild then copy" path cost about 2× the traffic, so it was replaced.
- **GPU synchronisation:** no `wait_for_gpu`, none per resize (pinned). Utility passes add only barriers.
- **720p/60 on an 890M:** feasible on paper (≈ 1.5 ms of reads plus 2× fill on the scene passes). It must be measured at runtime (§9).

## 8. Integration dependencies

- **Prerequisites:** `RSX_GUEST_SAMPLERS=15` is required for the visible result. `RSX_TEX_MIPS=1` is independent but addresses the texture grain (T133).
- **T116 PSO cache:** the guest-FP key's top byte (bits 56–60: samples, A2C, mask, A2One) must be part of the cache key, alongside T133's precision mode.
- **T122:** utility passes (expand, broadcast, zeta image) issue barriers and draws inside the replay. Lazy resolves happen on transitions. There is no fence use. T122 should review the barrier batching.
- **T120:** the sample-window path replaces `RSX_RT_WINDOW`'s window for antialias-3 reads.
  - **Found (VERIFIED offline):** with `RSX_RT_WINDOW=1` and 1 sample, a draw that samples its own bound target reads a never-refreshed window and gets black. `rtwin_refresh` is skipped for bound targets.
  - The race does this at ops 594–598 (`fp_022CD841` and `fp_070B0701`; the latter is blended, with computed-offset reads of the scene).
  - T120's code is untouched here. The fix belongs to T120: refresh through a COPY_SOURCE round trip, as `ms_expand_refresh` does.
- **T115B, T117, T119:** expect textual conflicts in `rsx_d3d12_backend.c`; there is no logical overlap. T117 must keep T113's END-based span (pinned).
- **T133:** the base. `aa_ctl` decoding comes from T133.

## 9. Runtime A/B plan (needs authorization)

**Build and route:**
- One exe from the T137 tip.
- T113 runner, the same route and capture time.
- RSXI with `RSXI_SNAP=passes` plus `RSXI_VP_CONSTS=32`, `RSX_FRAME_PERF=12,10`.
- Run order A B C D D C B A.

| Arm | Env |
|---|---|
| A | none (renderer as T113) |
| B | `RSX_TEX_MIPS=1 RSX_GUEST_SAMPLERS=15 RSX_RT_WINDOW=1 RSX_DEPTH_STATE=1` |
| C | B + **`RSX_MSAA=1`** |
| D | C + `RSX_FP_PRECISION=1` |

**Checks:**
1. **Arm A RSXI:** the `aa_ctl` value and `set` flag (decides A2C, mask and D3 in §2), and the per-FP `prec` counts.
2. **Arm C `[msaa]` line:**
   - `skipped_draws` 0, `failures` 0, `zeta_single_after_2s` 0, `reads_outside_image` 0;
   - window expands ≈ 8 and zeta images ≈ 2 per frame.
3. **Edges:** for fixed crops (palm fronds, horizon, bike outline), count mixed edge pixels and measure the frame-to-frame flicker of cutout coverage, B against C.
4. **Feedback ops 594–598:** compare B (black window) with C. This is a water/surf candidate (§10).
5. **Cost:** `[rsx-frame-perf]` frame and record time, GPU time, and the VRAM delta, B against C, on the 890M class iGPU.

## 10. Remaining visual discrepancies

| Symptom | Evidence | Status |
|---|---|---|
| Unstable foliage edges / missing smoothing | 2× restored (§5); cutout shimmer also needs T133's mips + guest samplers | fixed offline; runtime UNVERIFIED |
| Speckled water, grainy sand | texture minification (T133: no mips, point unit 0) | T133 switches; not an MSAA problem |
| **Dark water dots** | the scene's feedback reads (ops 594–598) see a **black** window under `RSX_RT_WINDOW=1` (VERIFIED offline). Zeta-as-colour reads (the shore `fp_07200641` and velocity) encode the far plane as `0xFF0000` without `RSX_MSAA` (VERIFIED offline). NaN export (T133) remains | the first two are candidates; neither is shown to be the cause (HYPOTHESIS) |
| Bright surf band | MSAA does not change it in the synthetic tests. Candidates are T120's depth state / MRT1 blend and the far-plane encoding. **No claim that MSAA fixes it** | open |
| A2C, sample positions and order, alpha to one | §2 | HYPOTHESIS / UNKNOWN |
| 2-sample zeta read by a 1-sample pass, or as depth | not implemented (no depth resolve); counted (`zeta_single_after_2s`, `depth_reads_of_2s`). The race never does it | open |
| PS3 parity | no hardware reference capture | not claimed |

## 11. Commits

- `5d65601`: rsx_msaa.h and the WARP test.
- `f6f9a48`: the backend `RSX_MSAA=1` path and the backend harness.
- `876a403`: window-direct expansion, lazy full image, RSXI `msaa_samples`/window note, T120-preserving key and clear, logic test, pins, harness feedback and zeta passes.

## Summary

**Implemented (opt-in, `RSX_MSAA=1`, offline-verified):**
- antialias-3 surfaces render with 2 samples, including depth and stencil;
- the game reads them in RSX's side-by-side sample layout, so its own downsample does the resolve, exactly;
- feedback and zeta-as-colour reads stay correct;
- no GPU waits, debug layer clean, the old path unchanged.

**Requires:** `RSX_GUEST_SAMPLERS=15`.

**Unverified:**
- the in-game result and cost;
- the game's `ANTI_ALIASING_CONTROL` value (and so A2C);
- RSX sample order;
- the surf band and water dots. Two concrete defect candidates were found for the dots; neither is proven.
