# T169: sampler translation

**Update (runtime):** D1 and F1 ran with no correction active, because `RSX_VISUAL_PROFILE` never reaches the game's D3D12 path. See `GAME_VALIDATION_PLAN.md`. Runtime status here stays unverified.

**Implemented:** profile bits 0x02 (`RSX_GUEST_SAMPLERS=15`) and 0x04 (`RSX_TEX_MIPS=1`), independent of colour. Default unchanged, because neither was ever isolated in game. T110's translator needed no fix.

**Audit, register to D3D12 (`rsx_sampler_xlate.h`, `gs_*`, VERIFIED by code and `test_sampler_xlate`):**

| Item | Finding |
|---|---|
| Min/mag/mip | Decoded correctly; convolution (min 7, mag 4, one binding in B3) approximated as linear, PARTIAL |
| Wrap/clamp | Correct, except MIRROR_ONCE_BORDER, unused here |
| LOD bias | Correct: `0x1F34` = -0.797 |
| Min/max LOD | Correct: 0..15, or base level for non-mip filters |
| Anisotropy | Follows guest; every captured binding is 1× (T133), so none is forced |
| Mips | Only the guest's chain; none invented |
| Cache key | Holds every decoded field; append-only, no fence needed |
| Binding | Guest sampler only on a bound unit the program samples |

**Captured state (B3, sampled units only, 612 draws with shaders):**

| Guest | Host default | Bindings |
|---|---|---|
| min4 mag2 wrap, bias | linear_wrap, level 0 | 1,129 |
| min4 mag2 clamp | linear_wrap, level 0 | 760 |
| min4 mag2 wrap, bias | **point_clamp** (unit 0) | 501 |
| min2 mag2 clamp | linear_wrap | 20 |

So the wrong address mode isn't only unit 0: **760 bindings ask for clamp and get wrap.**

**Offline A/B (`test_t169_visual_ab_warp`, 4 sub-texel phases):**

| Config | Mean | Phase spread | Upload bytes |
|---|---|---|---|
| Baseline | 17.75 | 55 | 256 |
| Colour only | 34.50 | 122 | 256 |
| Samplers only | 17.75 | 55 | 256 |
| Both | 34.50 | 122 | 256 |
| Both + mips | 34.00 | **0** | 508 |

**Samplers alone don't remove the shimmer.** They need the chain. With this fixture the guest's and fixed samplers also match at level 0, so samplers-only shows no pixel change there. Their effect shows in the clamp test: 252 of 255 error across the decal map's far edge, and T133's unit-0 cutout test.

**Sampled while disabled:** 5 bindings have CONTROL0's enable bit clear. The host samples anyway. Effect unknown.

**Game-validated:** nothing in isolation. T145 ran samplers in all arms with no off arm.
