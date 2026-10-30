# T165: vehicle black surfaces, root cause status

2026-10-30. Offline only: no launch, merge or push. **The root cause is not confirmed.** The leading candidate is below, with what it needs to be proven.

## Which run produced the screenshot

| Item | Value | Label |
|---|---|---|
| File | `Pictures/Screenshots/Screenshot 2026-10-30 114320.png`. Assumed to be the supplied one: newest file, shows the start grid. 914×358, so fine detail cannot be judged | PARTIAL |
| Run | Written at 11:43:20, inside `perfnext-TT3` (11:40:29–11:43:47), about race entry + 34 s | VERIFIED timing; the link to the run is inferred from it |
| Exe | `exe_n`, sha256 `0304156b…3449b3`, D3D12, ps3recomp `a049b1e` | VERIFIED |
| Arm T switches | `RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1 RSX_TEX_WWATCH=1 RSX_TEX_BUDGET_MB=1024`, so **after** the residency fix | VERIFIED |
| Off in that run | `RSX_COLOR_XFER`, `RSX_GUEST_SAMPLERS`, `RSX_TEX_MIPS`, `RSX_DEPTH_STATE`, `RSX_ZETA_EXACT`, `RSX_RT_FEEDBACK` | VERIFIED (`runner_argv.json`) |

## What the screenshot shows

| Class | Observation | Label |
|---|---|---|
| Black opaque pixels | Wheels, frames and much of the buggy bodywork are near-black. Riders and some paint (blue, pink, yellow) keep their colour, so whole-vehicle texture loss is unlikely | PARTIAL |
| Transparent pixels | No sand is clearly visible through solid bodywork. "Missing-looking" areas read as dark opaque or open frames at this resolution | PARTIAL |
| Discarded fragments | Ragged, speckled edges on bodies. Could be alpha test, or unfiltered sampling | HYPOTHESIS |
| Missing triangles | None provable | not established |
| Over-brightness | Sand and sky saturate while vehicles go black: too much contrast, not one wrong material | VERIFIED as appearance |
| Separate defects, not vehicle | Blocky rectangular shadow patches on the sand; a solid blue rectangle at top centre | cause unknown |

## Leading candidate: colour transfers off (HYPOTHESIS, strong)

The guest asks for sRGB texture decode and sRGB output on the main scene. The default D3D12 path applies neither, so lighting runs on gamma-encoded values.
- **Requested:** `srgb_output=1` on the main scene (T145: every draw on `0x00750000`) and gamma mask 7 on units 2/14/15 (race capture A1, 16 of 22 draws `srgb_output=1`, all `host_xfer=none`).
- **Mechanism:** RSX gives `encode(decode(t)·L)`; ours gives `t·L`. The curves are exact (`tools/lit_transfer_model_t165.py`); the WARP fixture confirms the transfer code itself.
- **Prediction, using the captured VP c40 = 4.5 and c41 ≈ 0.28** (their reading as sun and ambient is a HYPOTHESIS):

| Albedo | Light | RSX | Default | Default / RSX |
|---|---|---|---|---|
| 0.20 | 0.05 | 0.021 | 0.010 | 0.47 |
| 0.50 | 0.05 | 0.104 | 0.025 | 0.24 |
| 0.50 | 0.28 | 0.272 | 0.140 | 0.52 |
| 0.20 | 4.50 | 0.422 | 0.900 | 2.13 |

Shaded surfaces come out 2–4× too dark and lit ones up to 2× too bright. One cause would explain both black vehicles and the blown-out beach.

**Weak support:** T145 arm D1 (`RSX_COLOR_XFER=7`) has lower saturation than A1 in the last flyover frame: 6.1 % vs 15.3 % of pixels ≥ 250. The frames are not at matched moments, so this does not prove it. T145 made no visual claim either.

**Contributors, not separated:** unit 0 point/clamp with no mips (T162 D2) could give the ragged edges, and tiling UVs clamped to a dark edge texel could give patches. HYPOTHESIS.

## Checked and not the cause, within the evidence

| Candidate | Result | Limit |
|---|---|---|
| 96-slot overflow | The screenshot is from the 1,024-slot arm, and the defect is still there. Arm T does texture the flyover banner that arm E leaves washed out (frames 8–11), so residency is a real but separate defect | "no slot" count not logged in T3 (`RSX_TEXREC_STATS` off), budget eviction not measured |
| Null SRVs read as black | 22 race and 1,058 garage null bindings: the program samples none of them (`tools/null_census_t165.py`) | no vehicle programs in these captures |
| Sign expansion not applied | 0 units request it in those captures | same |
| Shadow compare translation | `test_fp_shadow_compare` passes | correct shadow-map contents not checked |

## Not established

No capture contains a vehicle draw (T162; still true). So the program, texture, alpha, depth and cull state of the affected draws are unknown, and the isolations A–F cannot run offline. See `GAME_TEST_PLAN.md`.

## Commits

ps3recomp `b1eb158` on `agent/t165-vehicle-render-fix` (base `a049b1e`). Root: branch `agent/t165-vehicle-render-report` (base `main` `4bdeed3`).
