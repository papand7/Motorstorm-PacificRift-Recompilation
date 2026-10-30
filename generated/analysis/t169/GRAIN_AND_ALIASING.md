# T169: grain and aliasing

**Update (runtime):** D1 and F1 ran with no correction active, because `RSX_VISUAL_PROFILE` never reaches the game's D3D12 path. See `GAME_VALIDATION_PLAN.md`. Runtime status here stays unverified.

**Primary cause: missing mip chains, with unit 0's point sampling on the cutouts (mismatch VERIFIED, T133 and B3; fixture effect VERIFIED; game untested).**

| Candidate | Finding | Label |
|---|---|---|
| Incorrect mip selection | 1,949 of 2,463 sampled uploads ask for a mip filter; host has level 0 | VERIFIED mismatch |
| Point sampling | 501 unit-0 bindings ask for linear mip filter and get point | VERIFIED mismatch |
| LOD | Bias -0.797 is the game's; at level 0 it has no effect | VERIFIED |
| Compression, swizzle | No defect found (T107, T115, T133) | Not a cause so far |
| Shader precision | FP precision clamp exists, off; race usage still unmeasured | HYPOTHESIS |
| Depth precision, z-fighting | No evidence either way | Unresolved |
| Alpha test | Off; cutouts are shader KIL at alpha < 0.5 (T133) | VERIFIED, so unit 0 sampling drives them |
| Dithering | None found in the shaders read | HYPOTHESIS |
| Shadow sampling | The decal maps are smooth with linear filter; **not** a grain source seen here | Weak |
| Missing MSAA | Scene asks for 2 samples, gets 1 | VERIFIED; causes edge stairs, not surface grain |

**By spatial behaviour:**
- **Follows texture coordinates, worse with distance:** sand, foliage, sea (T133 crops, B3 `frame_002`). Consistent with minification. Fixture: a stripe texture flips by 55/255 across sub-texel phases at baseline, and by 0 with guest samplers + chain.
- **Screen-space:** nothing found. No screen-locked pattern seen in the frames viewed.
- **Follows shadow boundaries:** the streaks in decal delta, see `SHADOW_RENDERING.md`. Separate defect.
- **Under camera movement:** not measured. It needs two frames of a moving camera with the same exposure; the captures' cameras aren't matched.

**Ragged edges:** cutout edges are a mix of no mips + point sampling + no coverage AA. `aa_ctl` is `0xFFFF0001` on the scene: AA enable set, alpha-to-coverage bit clear, so coverage-from-alpha isn't what's missing. `RSX_MSAA=1` is a real 2-sample implementation with a sample-expanded copy for the guest's own downsample (T137). No FXAA or blur was added.

**Game-validated:** none.
