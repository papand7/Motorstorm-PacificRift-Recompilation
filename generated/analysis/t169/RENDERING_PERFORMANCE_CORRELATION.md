# T169: rendering and performance correlation

**Update (runtime):** D1 and F1 ran with no correction active, because `RSX_VISUAL_PROFILE` never reaches the game's D3D12 path. See `GAME_VALIDATION_PLAN.md`. Runtime status here stays unverified.

**Result: no correctness fix here is demonstrated to save host work. Most add a small, bounded cost.** Fix them for correctness, and don't expect FPS. The one candidate saving is unmeasured.

Costs below are from B3's state (capture census) and WARP fixtures, so they aren't frame times. GPU frame time, fence waits and memory in game weren't measured: no launch was authorised, and WARP timing says nothing about a GPU.

| Issue | Classification | Extra host work caused by the mismatch? | Cost of the fix | Offline A/B shows both? |
|---|---|---|---|---|
| sRGB off | **Confirmed visual defect only** | No | Pipeline identities 150 → at most 152 in B3. First compile on WARP 5.9 → 7.5 ms (one sample each) | Visual yes; no saving |
| Samplers | **Confirmed visual defect only** | No. Fixed samplers bind nothing | 27 descriptors, 234 table changes in B3 (0.25 per draw). No redundant binds: the code skips unchanged units | Visual yes; cost counted |
| Missing mips | **Suspected shared cause** | Possibly: sampling level 0 when minified costs GPU texture-cache misses. **Theoretical** | +29.6 % texture bytes (18.2 → 23.6 MiB); +3–9 % on cache-miss upload (T115) | Visual yes; saving not measurable on WARP |
| Depth writes, compare | **Suspected shared cause** | Possibly: wrong depth state changes what later draws reject. WARP's PS invocations were equal (16, 16), so **no saving shown** | None per draw; PSO variants | Visual yes; performance no |
| Stencil | **Confirmed visual defect only** | Op 915 shades its full screen either way in this frame's state; not measured | PSO variants | Visual from captures |
| MSAA | **Confirmed visual defect only** | No | 2× targets, expand copy | Logic and WARP pass (T137); cost not measured here |
| `0xBF` velocity | **Confirmed visual defect only** | No | Not implemented | No |
| 190–216 ms heavy-scene texture recording | **No demonstrated relationship** | T155: slot table and hashing. None of these states feed it. Mips enlarge the hashed span, so cost could rise | N/A | No |
| Texture cache invalidation | **No demonstrated relationship** | Black surfaces had no binding failures (`noslot=0`, `stale=0`, T165) | N/A | No |
| Shader variants | **No demonstrated relationship** | Sampler and mip changes make **no** new shader (fixture: 2 distinct PS across 5 configs). Only the transfers do, by design | Small | Yes |
| GPU waits | **No demonstrated relationship** | T167: remote-session present | N/A | No |
| Duplicate draws | **No demonstrated relationship** | T168: 0 confirmed. Records aren't packets | N/A | No |

**Confirmed visual and performance defect:** none. **Confirmed performance defect only:** none from this work.

## Fixture matrix (`test_t169_visual_ab_warp`, deterministic pixels, one timing sample)

| Config | Mean | Phase spread | \|Δ base\| | Compile ms | New PS | Samplers | Upload B |
|---|---|---|---|---|---|---|---|
| Baseline | 17.75 | 55 | 0 | 5.92 | 1 | 0 | 256 |
| Colour only | 34.50 | 122 | 16.75 | 7.52 | 1 | 0 | 256 |
| Samplers only | 17.75 | 55 | 0 | 5.61 | 0 | 1 | 256 |
| Both | 34.50 | 122 | 16.75 | 7.50 | 0 | 1 | 256 |
| Both + mips | 34.00 | 0 | 28.75 | 7.36 | 0 | 1 | 508 |

Draw counts are identical across configs by construction. The additional shadow row is `test_decal_depth`: 8 pixels covered in both, on opposite sets. Compile times are a single run, not a benchmark; the pixel values are the deterministic part.

**Why colour-only's spread rises:** the encode lifts both stripes apart, and it's still unfiltered level 0. It's expected, and it shows that colour correctness alone could make grain more visible until mips are on. That's a reason to validate them together.

**Instrumentation overhead:** `[vis-draw]` costs one stderr line per draw. Don't time runs with it on. Off, it costs one branch per draw and a few counter increments.

**Comparability rule for the game A/B:** same shader-cache state, local session (no remote `Present` mode), and count `wait_ms ≈ 84` frames before comparing.
