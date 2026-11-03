# T141: RSX blending, transparency and render-target feedback

Date 2026-10-28. Worktree `ps3recomp-t141`, branch `agent/t141-rsx-blending-feedback`. Not merged or pushed. No game build or launch.

## 0. Base, branches and commits

- **Base `876a403`** (the T137 tip). It already contains:
  - T113 `2562ba8` (FP span, exposure);
  - T120 `235b3e6` and `169e618` (`RSX_RT_WINDOW`, `RSX_DEPTH_STATE`, RSXI `mrt_regs`);
  - T115 `17b16cb` as `4a74174`;
  - T133 `816a4af`;
  - T137 `5d65601`, `f6f9a48` and `876a403`.
- **Not combined:** T115B `65d2695`, T116 `30b817b`, T117 `fd97181`, T119 `693169a` and T122 `2b639c2`. Each changes `rsx_d3d12_backend.c` (§9).
- **Push guard:** `origin` push is `DISABLED` (checked). Nothing was pushed.

**Commits (local):**

| Commit | Content |
|---|---|
| `7b5fcda` | `libs/video/rsx_blend_feedback.h` and its WARP test (`test_t141_blend_feedback_warp.c`) |
| `fab1e88` | `rsx_msaa.h`: T137's sample-image depth conversion uses the exact depth24 |
| `8301ea6` | backend: `RSX_RT_FEEDBACK`, `RSX_ZETA_EXACT`, `RSX_MRT_STATE` (all opt-in) and `D3D12_GBV` |
| `07b453f` | real-backend harness `test_t141_backend.c` and `tools/test_blend_feedback.py` |

## 1. Captured RSX evidence

**Sources:**
- Race capture I (`t113/runtime-I…/rsxi/frames/f006502`, 665 draws).
- Capture G (frames f006264 and f006314).
- Tools: `t141/tools/ops.py` and `feedback_tally.py`.
- Log: `logs/feedback_I.txt`.

| Item | Captured value | Status |
|---|---|---|
| **Feedback draws** | **op 594** `fp_022CD841`, cmd `0x04EFF0`: unit 2 reads the scene `0x00750000` (2524×710 `0xA5`) while writing it. Unblended, depth test without write, stencil test on | VERIFIED |
| | **ops 595–598** `fp_070B0701`, cmd `0xA4CAAC`: unit 4 reads the scene while writing the scene plus MRT1 `0x01650000`. Blend `0x01261185` | VERIFIED |
| | Same pattern in both G frames (ops 480–484 and 483–487), so it occurs every race frame | VERIFIED |
| Feedback read position | both programs sample at `pos.xy × (1/1262, −1/710) + offset`: the pixel's own position, plus a computed offset in 595–598 (refraction-style) | VERIFIED (shader code) |
| What the guest expects | the scene as the earlier draws left it. 595–598 each read what the previous one wrote | HYPOTHESIS on RSX cache behaviour, but the only ordering that gives a defined result |
| Op 667 | `fp_0074BFC1` keeps unit 6 bound to its own 80×45 target. No shader dump exists, so whether it fetches that unit is unknown | open |
| **Blend states** | 644 draws unblended | VERIFIED |
| | `0x0122418B` ×14: colour SRC_ALPHA, INV_SRC_ALPHA, ADD; alpha INV_DEST_ALPHA, ONE | VERIFIED |
| | `0x01261185` ×6, ops 595–600 (water and shore, writing scene + MRT1): ONE, INV_SRC_ALPHA (premultiplied) for both colour and alpha | VERIFIED |
| | `0x01211085` ×1, bloom op 661: colour ONE, ONE; alpha ONE, ZERO | VERIFIED |
| Colour mask | 0xF on all 665 draws | VERIFIED |
| Logic op | not recorded by RSXI | UNKNOWN |
| Alpha test | off on all draws; cut-outs use KIL (T133) | VERIFIED |
| **MRT** | ≈420 scene draws write `0x00750000` + MRT1 `0x01650000`. `fp_07200641` exports 4 colours with 2 targets bound | VERIFIED |
| `COLOR_MASK_MRT` / `BLEND_ENABLE_MRT` values | not in any capture (I/G predate T120's `mrt_regs` record) | UNKNOWN |
| Game's MRT setters (lifted PPU) | `0x00733C40` writes `COLOR_MASK` (0x324) and `COLOR_MASK_MRT` (0x370) in one packet, copying target A's nibble to B–D (3 callers). `0x00733A10` writes `BLEND_ENABLE` (0x310) = arg&1 and `BLEND_ENABLE_MRT` (0x36C) = arg&0xE (no direct caller; reached indirectly) | VERIFIED (code). Runtime arguments UNKNOWN |
| **Depth as colour** | ops 577 (`fp_0B027F41`), 599–600 (`fp_07200641`, shore) and 651 (`fp_0074CE81`, velocity) read zeta `0x00ED0000` as `0xA5` 2524×710 | VERIFIED |
| Guest depth decode | each program fetches `.wxy` (A, R, G), applies `floor(x·255 + 0.5)` and weighs them 2⁻⁸, 2⁻¹⁶, 2⁻²⁴. The shore program turns the result into a world position (inverse projection, w = 10.0001 − 9.99997·d) | VERIFIED |

## 2. Blend and MRT state mapping

| Aspect | Renderer before T141 | Finding |
|---|---|---|
| Target A blend (factors, equations, separate alpha) | 1:1 (`rsx_blend_key`, `test_d3d12_blend_state`) | correct |
| Targets B–D blend | **mirror target A**. `IndependentBlendEnable` is never set, so D3D12 uses `RenderTarget[0]` for every target | wrong whenever `BLEND_ENABLE_MRT` differs from target A. In the race this concerns MRT1 in ops 595–600 (value unknown) |
| Targets B–D masks | mirror target A | **correct for MotorStorm's setter** (it copies A's mask) |
| Disabled attachments | MRT offsets of 0 are not bound (`dr_num_rts`) | correct |
| Format conversion | all targets use target A's DXGI format | matches RSX (one surface format) |
| Shader output routing | FP `t0..t3`. Extra exports beyond the bound targets are dropped by D3D12 | correct |
| Depth/stencil with MRT | shared DSV; T120 `RSX_DEPTH_STATE` | unchanged |

**`RSX_MRT_STATE=1`** (`8301ea6`):
- When the guest wrote the registers, targets B–D take their own write mask (nibble A,R,G,B → D3D R,G,B,A) and blend enable.
- `IndependentBlendEnable` is set only then.
- The key bits sit in the colour-mask argument above [3:0]. They are 0 while the registers are unwritten, so the pipeline key and the description are unchanged.
- **Limitation:** the factors are keyed only with target A's enable. A target B blended while target A is not is drawn unblended and logged (`[mrt]`).

## 3. Feedback hazard analysis (ops 594–598)

1. **Surface read:** the scene `0x00750000`, 2524×710 `0xA5`. This is its 2-sample layout; single-sample it binds as 1262×710.
2. **Surface written:** the same surface (and MRT1 in 595–598).
3. **Previous version expected:** yes. Each draw reads the scene before itself, and 595–598 read each other's output.
4. **Snapshot required:** yes. D3D12 leaves an SRV read of a bound render target undefined.
5. **Existing snapshot bypassed:** yes. `rtwin_refresh` is skipped for a bound target (`rt != cur_rt`), so the `RSX_RT_WINDOW` window is never filled and is read while still in COPY_DEST, giving black. Without a window, the SRV is the bound resource itself.
6. **T120 window and valid pixels:** the window is the right size. The defect is that it is never refreshed, not that it masks pixels.
   - **New T120 edge case (VERIFIED in the harness):** a unit the program does not fetch, left bound at another size, claims the target's one window size for the frame. The real read then falls back to the whole surface and its 1280-vs-1262 stretch.
7. **T122 snapshot epoch:** it applies to uploaded guest textures (the CPU hash). Render-target reads (`rt_exact`) never take that path, so it has no effect here.
8. **T137 MSAA layout:** with `RSX_MSAA=1`, a bound antialias-3 target is already re-expanded before every read (T137). `RSX_RT_FEEDBACK` leaves that path alone (`ms_left` counter, 0 copies in the MSAA arm).

**Fix: `RSX_RT_FEEDBACK=1`.**
- At replay, just before a draw that fetches a unit over one of its own colour targets, the backend copies the target into its window (or into a whole-target copy when there is no window). The copy sequence is RT→COPY_SOURCE, copy, →RENDER_TARGET.
- The copy is repeated only if a draw went into the target since the last one.
- No GPU wait; copies and barriers only (pinned).

**Old-path evidence (GPU-based validation):** the read is a D3D12 error ("Incompatible texture barrier layout": 1 on WARP, 7 in the real backend harness). The pixel values on the RTX 5060 vary from run to run: 214–84,777 pixels read the draw's own writes.

## 4. Depth-as-colour findings

**Guest format (VERIFIED):**
- A Z24S8 word is depth24 << 8 | stencil, so A8R8G8B8 reads give A = [23:16], R = [15:8], G = [7:0], B = stencil.
- The guest programs above decode exactly this layout.

**The defect (VERIFIED, exhaustive on WARP over all 2²⁴ codes):**
- The backend conversion `(uint)(d·16777215.0 + 0.5)` runs in float. From 2²³ upward, floats are 1 apart, so `k + 0.5` rounds half-to-even.
- **4,194,304 codes are wrong:** every odd k ≥ 2²³ comes out k + 1 (127 of them carry into the A byte).
- **The far plane** (k = 0xFFFFFF) comes out 2²⁴, written as A = FF, R = G = 00. The guest decodes 0.99609375 instead of 0.99999994.
- T137's clamp fixed only the far plane.

**Real GPU (VERIFIED):**
- The RTX 5060 harness shows the far plane as R,G = 00,00 before and FF,FF with the fix.
- Depth 0.65 is stored as `0xA66665`, because float32(0.65) = 0.6499999762. The old conversion reads it as `…6666`, the exact one as `…6665`.

**What the far-plane error means for the guest:**
- In the shore program's reconstruction, w goes from 1.3·10⁻⁴ to 0.039. A cleared (far) depth behind water is therefore placed about 300× closer, roughly 25 m instead of the far plane.
- How this shows up on screen is HYPOTHESIS (§8).

**Fix:**
- **`RSX_ZETA_EXACT=1`:** `min((uint)round(saturate(d)·16777215), 0xFFFFFF)`. Exact for all 2²⁴ codes on WARP. On hardware it depends on D3D's UNORM→float conversion being within half an ulp; a worse device can be off by 1 in the low byte, never at the far plane.
- **`RSX_MSAA`'s sample images** use the same exact expression (`fab1e88`), so the fix also applies to the 2-sample path.
- Stencil and the multisampled and non-multisampled paths are all covered.

## 5. Implemented corrections (all opt-in; the disabled path is unchanged)

| Switch | Corrects | Evidence |
|---|---|---|
| `RSX_RT_FEEDBACK=1` | ops 594–598 read the scene before each draw instead of black (with `RSX_RT_WINDOW`) or an undefined read-while-bound | **VERIFIED mismatch, fixed offline** |
| `RSX_ZETA_EXACT=1` | far plane `0xFF0000` → `0xFFFFFF`; odd depth codes exact | **VERIFIED mismatch, fixed offline** |
| `RSX_MRT_STATE=1` | per-target `BLEND_ENABLE_MRT` / `COLOR_MASK_MRT` when written | semantics VERIFIED (code, WARP). In-game effect needs the register values |
| `D3D12_GBV=1` | diagnostic: GPU-based validation | — |

**Pins (`tools/test_blend_feedback.py`):**
- each switch is read once;
- the MRT key only takes effect with the switch;
- T120's mask line is kept verbatim;
- no `wait_for_gpu` in the feedback code;
- the old zeta shader is kept when the switch is off.

## 6. Pixel-level test results

**WARP, debug layer and GBV (`test_t141_blend_feedback_warp`, `logs/bfwarp_gbv.txt`): 41/41.**
- **Depth:** 0 of 2²⁴ codes wrong with the exact conversion, versus 4,194,304 wrong with the old one; stencil exact in both.
- **Feedback** (blend ONE, ONE; 32 → 64 → 128): 96×64 and 101×67 (a resize), full and partial viewport, every channel exact (inside 128, outside 32). 0 debug-layer/GBV errors.
- **Bound-target read:** reported by GBV.
- **MRT, 4 cases, every pixel exact:**
  - unwritten registers (B and C mirror A);
  - B = R|A unblended with C masked off (128,64,64,128 / 64,64,64,64);
  - the game's setter;
  - `BLEND_ENABLE_MRT = 0`.
  - Separate alpha (ZERO, ONE) keeps alpha at 64.

**Real backend (`test_t141_backend`, RTX 5060):**
- 8 frames with the race's moving viewport. The middle quad region is 221,056 px at frame 5 (`logs/fb_backend.txt`).
- 0 debug-layer errors in every arm.

| Arm | Middle half | Far plane (R,G) |
|---|---|---|
| none (T113 default) | 210,708 at 128, 9,958 at 96 (T120's stretch), 239 at 160 (reading its own writes) | 00,00 |
| `RSX_RT_WINDOW=1` | **221,056 at 32 (black feedback)** | 00,00 |
| `RSX_RT_FEEDBACK=1` | 211,216 at 128, 9,840 at 96 (stretch, no window) | 00,00 |
| `RSX_RT_WINDOW=1 RSX_RT_FEEDBACK=1` | **221,056 / 221,056 at 128** | 00,00 |
| `RSX_ZETA_EXACT=1` | as none | **FF,FF** |
| all four switches + `RSX_DEPTH_STATE` | 221,056 at 128 | FF,FF |
| GBV, none / GBV + feedback | 7 GBV errors, 84,777 px at 160 / 0 errors, deterministic | — |

**T137's race-shaped antialias-3 harness, rebuilt on this tree (`logs/msaa_harness_fb.txt`):**
- With 1 sample and `RSX_RT_WINDOW=1`, the 223,020 black pixels become 0 with `RSX_RT_FEEDBACK=1`. The feedback quad reads the white/red it should.
- The `RSX_MSAA=1 RSX_GUEST_SAMPLERS=15` arm is pixel-identical with and without the switch (0 copies). Its downsample still equals the resolve (max diff 0).

**Regression and build:**
- Suite `run_suite_t141`: **40/40 PASS** (`logs/suite_t141.txt`).
- `test_blend_feedback`: 13/13.
- Backend TU: 0 errors, no new warning class.
- Audit: 25 inherited BLOCKs, none in T141 files (`logs/audit_c*.log`).

## 7. Performance

**Copies:**
- The race has 5 feedback reads per frame, each after a write, so 5 copies of the 1262×710 window: ≈17 MiB copied, ≈34 MiB of traffic.
- On an 890M that is roughly 0.3–0.6 ms (estimate, not measured).
- **Barriers:** about 4 per copy (≈20 per frame).
- **GPU waits:** none.

**VRAM:**
- With `RSX_RT_WINDOW`: 0 extra; the window is reused.
- Without it: one whole-target copy per sampled target (3.5 MiB for the scene).

**Pipelines:**
- `RSX_ZETA_EXACT` swaps a shader, adding 0 pipelines.
- `RSX_MRT_STATE` adds variants only for distinct `COLOR_MASK_MRT`/`BLEND_ENABLE_MRT` values. In-game count unknown, plausibly 1 per A state.
- **T116:** its disk cache keys on the full pipeline description, including `IndependentBlendEnable`.

**Harness timing** (300 frames, median from frame 50; `logs/perf_harness.txt`):

| GPU | Frame (window, without → with feedback) | Record | All switches |
|---|---|---|---|
| RTX 5060 | 6.9 → 6.9 ms | 1.1 → 1.1 ms | record 1.3 ms |
| AMD iGPU | 7.0 → 7.1 ms | 2.5 → 2.4 ms | — |

The harness is wait-bound, so the copy's GPU cost is below its resolution. This needs runtime measurement.

## 8. Remaining surf and water issues

| Artifact | Concrete candidates | Status |
|---|---|---|
| **Dark water dots** | (a) ops 594–598 read black (`RSX_RT_WINDOW=1`) or an undefined read-while-bound (default). On the RTX 5060 harness the default path returned the draw's own writes for 239–84,777 px; on AMD the behaviour is unknown. (b) Shore/velocity depth decode off by +1 on odd codes. (c) NaN export (T133) | (a) is a VERIFIED defect with a plausible link; that it causes the dots is HYPOTHESIS |
| **Bright surf band** | (a) Far plane decoded as 0.996: water over cleared depth gets a ~25 m depth difference, which drives the shore/foam terms of `fp_07200641` (ops 599–600, blended ONE, INV_SRC_ALPHA). (b) MRT1 blended in 595–600 if the guest's `BLEND_ENABLE_MRT` is 0 (MRT1 feeds exposure). (c) T120 depth state | HYPOTHESIS; (a) is the strongest, test with arm C |
| Water reflections | read the scene through ops 594–598 | same as dots (a) |
| Transparency | blend factors map 1:1; only MRT B–D differ | see §2 |

No artifact is claimed to be fixed. They may have separate causes.

## 9. Integration dependencies and conflicts

- **Needed for the visible result:** `RSX_RT_WINDOW=1` (T120) together with `RSX_RT_FEEDBACK=1`. Without the window, T120's 1280-vs-1262 stretch remains in feedback reads.
- **T113:** FP span untouched.
- **T115 / T133:** independent. T133's samplers (`RSX_GUEST_SAMPLERS=15`) are recommended in the A/B.
- **T115B (texture cache):** RT reads do not go through its upload cache. Expect a textual conflict in the SRV pass.
- **T116:** compatible (full-description key). Its in-memory key must keep the full `cmask` u32, not `& 0xF`.
- **T119 / T122:** textual conflicts in the replay loop (barrier counting). T122's `RSX_GPU_SYNC` barrier counter should include `fb_refresh`'s transitions.
- **T120 follow-up (open, not changed):** units that the program does not fetch should not claim the per-frame window size.
- **T137:** compatible; the MSAA path is unchanged except for the exact depth conversion.

## 10. Controlled runtime A/B plan (needs authorization)

**Setup:**
- Build the T141 tip (`07b453f`).
- Use the same save and race as T113/T137.
- Common switches: `RSX_TEX_MIPS=1 RSX_GUEST_SAMPLERS=15 RSX_DEPTH_STATE=1 RSXI=1` with snapshots at the race frame.

| Arm | Adds | Answers |
|---|---|---|
| A | `RSX_RT_WINDOW=1` | baseline: black feedback |
| B | A + `RSX_RT_FEEDBACK=1` | do the water dots or reflections change? |
| C | B + `RSX_ZETA_EXACT=1` | does the surf band change (ops 599–600)? |
| D | C + `RSX_MRT_STATE=1` | MRT1 / exposure. RSXI records `mrt_regs`, which settles the setter arguments |
| E | D + `RSX_MSAA=1` | T137 on top |

**Measure per arm:**
- race FPS and frame-time spread (`ana_t122.py`);
- the `[fb]` line;
- the debug layer (`D3D12_DBG=1`) on one short run;
- `D3D12_GBV=1` on a single frame.
