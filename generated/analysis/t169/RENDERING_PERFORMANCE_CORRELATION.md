# T169: rendering and performance correlation

## D2 and F2 in game

**Result: the F2 set costs about 6–7 % on normal race frames and about 54 % more PSO-miss time. The draw load matches, and no correction saved host work. T167's slow mode and fence waits weren't involved.**

Same exe, local session, debug layer on in both, so absolute figures are pessimistic. Frames are aligned to the first race frame. Times in ms.

| Window | n | FPS | p50 | p95 | p99 | Draws | Record | PSO | Cmd | Wait | PSO miss ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D2 race | 501 | 10.6 | 94.0 | 135.1 | 201.5 | 4,496 | 47.8 | 11.5 | 33.5 | 0.1 | 3,868 |
| F2 race | 457 | 9.6 | 98.4 | 145.7 | 245.7 | 4,549 | 58.0 | 17.5 | 37.1 | 0.1 | 5,951 |
| D2 700–2000 draws | 151 | 16.4 | 44.9 | 50.4 | 201.5 | 1,821 | 23.9 | 10.5 | 12.1 | 0.0 | 1,435 |
| F2 700–2000 draws | 150 | 15.6 | 45.1 | 51.9 | 225.7 | 1,823 | 28.7 | 13.4 | 13.8 | 0.0 | 1,832 |
| D2 3500–5000 | 123 | 10.5 | 95.1 | 100.3 | 102.4 | 4,549 | 49.6 | 5.1 | 41.9 | 0.1 | 41 |
| F2 3500–5000 | 81 | 9.9 | 100.6 | 107.6 | 174.8 | 4,643 | 55.3 | 6.2 | 45.8 | 0.1 | 30 |
| D2 5000–7000 | 124 | 8.4 | 108.1 | 128.8 | 150.8 | 5,582 | 62.9 | 11.9 | 46.9 | 0.1 | 743 |
| F2 5000–7000 | 125 | 7.6 | 114.8 | 136.9 | 185.7 | 5,585 | 75.1 | 17.1 | 52.8 | 0.1 | 1,254 |
| D2 7000+ | 43 | 7.3 | 134.3 | 145.4 | 218.8 | 7,312 | 71.6 | 8.7 | 58.2 | 0.1 | 55 |
| F2 7000+ | 43 | 6.7 | 143.9 | 176.0 | 245.7 | 7,314 | 83.2 | 11.4 | 66.3 | 0.1 | 112 |

| Correlation | D2 | F2 | Reading |
|---|---|---|---|
| Guest draw counts | Median per bin matches F2 within 1 outside the 3500–5000 bin (shift of F2's cut-off window) | Correlation 0.976 by frame; 173 of 457 identical | Same work; timing offsets explain the rest. `RSX_DEPTH_STATE` adds no draws |
| PSO misses | 128 | 129 | Same count; cost per miss up about 50 % (HYPOTHESIS: larger compile from the sRGB rewrite plus the sampler root signature) |
| Shader compiles in the diagnostic window | 2 | 2 | No difference there |
| Samplers | 0 new, 0 binds | 19 new, 490,454 binds (`[vis-work]`) | Bind work; `cmd` rises about 4–8 ms |
| Uploads in the window | 1,073; 450.5 MB | 1,079; 469.9 MB | +4.3 % bytes |
| RT transitions, copies | 0 feedback copies | 5,152 feedback copies | Extra GPU copies; GPU time not measured |
| GPU | No timestamps | No timestamps | **Inconclusive**. `wait` about 0.1 ms means the frame doesn't block on the fence |
| Fence waits | 0 frames at `wait_ms`≈84 | 0 frames | T167's slow mode absent |
| Memory (sampled) | 687 MB | 703 MB | +2.3 %, one sample each |

**T168 distinction:** this is draw-record CPU cost, not duplicate draws. Packet-level duplicates weren't measured here. **Baseline caution:** D1 and F1 ended on the RSXI timeout at about 272–288 frames and never reached the 5,000+ draw scenes, so they can't be compared overall. Their p50 near 50 ms matches D2's first 100 frames (45.3). Scene-matched per-switch cost is **inconclusive** because F2 changes 8 switches.

## Offline analysis, before D2 and F2

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
