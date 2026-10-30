# T169: blocky shadows

**Update (runtime):** D1 and F1 ran with no correction active, because `RSX_VISUAL_PROFILE` never reaches the game's D3D12 path. See `GAME_VALIDATION_PLAN.md`. Runtime status here stays unverified.

**Likely cause: decal boxes drawn with the wrong depth state and wrong address mode. Mismatches VERIFIED, fixture VERIFIED, link to the screenshot a strong HYPOTHESIS. Game untested.**

## What these draws are (VERIFIED, B3 ops 569–583)

15 draws of `fp_022C20C1`, 18 vertices each, front-culled, blended (`0x0122418B`), each with its own stencil ref. For each pixel the shader:
1. Reads scene depth from unit 0: `0x00ED0000` as A8R8G8B8, nearest.
2. Reconstructs position and projects it to a map's UV.
3. Reads unit 1, an **8×8 or 16×16 B8 map**, ADDRESS `0x60030303` (clamp), and outputs alpha `1 − z`.

These are projected low-resolution darkening volumes, not a classic shadow map. They change 87 % of B3's pixels (p1 ratio 0.70).

## Mismatches

| State | Guest | Host default | Evidence |
|---|---|---|---|
| Depth compare | GREATER (4) | LESS_EQUAL | Pipeline code; RSXI `depth.func` |
| Depth writes | Off | **On** | Same |
| Stencil | Test on, per-box ref | **None** | Same |
| Unit 1 address | Clamp | Wrap | RSXI `host_sampler` |

**Fixture (`test_decal_depth`, WARP, debug layer on):** with back faces partly behind a scene plane:
- Guest state shades exactly the inside pixels and keeps scene depth.
- Legacy state shades **the opposite pixels** and overwrites depth there.

**Fixture (`test_decal_clamp`):** with captured words, past the far edge, wrap brings in the opposite edge: error up to 252/255; clamp stays within the last texels.

**Image evidence (`logs/decal_delta.png`, ×4):** the pass's delta shows sharp box faces around the quad and a striped pattern over the terrain. B3's `frame_002` shows the same rectangles on the sand and streaks on the bank. Inverted coverage explains faces. Wrap past the map's edge could explain repeating stripes.

**Alternative for the stripes:** they resemble iso-depth contours, so a depth-decode fault isn't excluded. The decode is byte-exact in code (A = [23:16], R = [15:8], G = [7:0]) apart from a far-plane round-up that `RSX_ZETA_EXACT` fixes. Not proven by replay: vertex outputs aren't captured.

## Depth state goes wider than shadows

| Request in B3 (928 draws) | Count |
|---|---|
| Stencil test on (host: none) | 885 |
| Test on, write off (host writes) | 299 |
| Compare not LEQUAL | 16 |
| Any difference | **904** |

Depth written by decals then reaches later draws and every depth-as-colour read.

**The velocity pass is a verified consequence:** op 915 tests stencil NOTEQUAL. Host has no stencil, so the full-screen draw erases all vehicle velocity written by ops 597–914 (snap18 has vehicles, snap19 is all zero).

## Not checked

- Unit 11, sampled by this shader, wasn't captured (mask `C03F`).
- The separate `0x0B830000` reflection-size pass.
- `RSX_DEPTH_STATE`'s existing WARP and pin tests pass (see `REGRESSION_VALIDATION.md`), but it has **never run in game**, and T145's arms didn't include it.
- `test_shadow_*` covers depth-compare units, not these decals. A passing synthetic test isn't evidence about real maps.

Shadows are neither disabled nor reduced.
