# T72: race terrain saturation (offline)

2026-10-26. Offline only. No launch, no build, no code change, nothing merged or pushed, no shared worktree touched.

**Input:** the T71 Run A captures, `generated/runs/20261026-152501-t71-camera-validate`, frames f004425–f004427.
- Exe: T64C `162afb4a…`, source `ps3recomp-t62` @ `c529ab0`.
- Env: `VP_NOFIXPROJ=1`; `RSX_RT_READBACK` **not set**.

**Tools in `t72/`:**
- `exposure_model.py`: 15/15 PASS over 3 frames;
- `zero_draws.py`;
- `c33_scan.py`.

## Result

**Updated after the T72 runtime validation (§10).**
- **Saturation mechanism: VERIFIED.** Every scene and reflection shader multiplies by VP `c33.x`, which sits at the formula maximum, 35.3 (0.3 + 0.21/0.006).
- **Hypothesis "`RSX_RT_READBACK=1` alone closes the exposure loop": REJECTED.**
  - The readback works: `0x07EBA600` is selected and applied every frame, and GPU luminance reaches guest memory (VERIFIED).
  - But `c33.x` stays at 35.29, and the image is unchanged.
- **New cause, PARTIAL:**
  - the exposure surface is zero-luminance in rows 6–15, because the lower ~55 % of the scene is never drawn (luminance 0);
  - the CPU samples 4 of its 5 points from rows 10–11.
  - So the game measures near-zero luminance with or without readback.
- **Not a shader, texture, format or blend defect.** Readback is still required, and is now verified as necessary but not sufficient.

## 1. Render pipeline (frame f004425; VERIFIED from RSXI)

| ops | target | programs | role |
|---|---|---|---|
| 5–196 | `0x07B78D80` 640×480 RGBA8 | terrain VS `CEED7030`/FP `07A9CEC1` (12 draws); objects VS `0E74E41D`/`2F867C86`/`94C50138` with FPs `07B4…`–`07B58…` | water reflection |
| 197–208 | `0x00750000` + MRT `0x01650000`, 1280×720 RGBA8 (`0x3148`, 2×AA) | terrain `CEED7030`/`07A9CEC1` | main scene |
| 236 | `0x02195900` 320×180 FP16 | `0074B181`: 4 taps of MRT1, averaged, squared, ×16 | luminance |
| 237–241 | down to `0x022C1600` 10×5 FP16 | `0074AB41` | downsample |
| **250** | **`0x07EBA600` 16×16 FP16** | VS `120B5D06` (tc0.z = **1/c33.x**), FP `0074C781` | **exposure result**: written each frame, sampled by **no** GPU draw in any of the 3 frames, so it is read on the CPU |
| 251–262 | bloom / composite / backbuffer | `0074D0C1`, `007400C1`, `0074BFC1`, `02193941`, `02537E81` | post-FX, HUD |

## 2. First verified point of saturation

**The terrain FP output, ops 197–208**, before any compositing.
- `0x00750000` and MRT1 `0x01650000` are already two-tone `000000`/`ffffff` after op 208 (MRT1 checked after op 242).
- **MRT1 white pixels = samples passed by ops 197–208:** 422533 = 422533 (f4425), 422509 = 422509 (f4426), 422523 = 422523 (f4427). Every written pixel is saturated; the black is unwritten clear colour.
- Later passes (bloom, composite) only propagate it.

## 3. Original shader calculation (terrain FP `07A9CEC1`, 21 instructions)

```
albedo = tex0(tc0.xy) * saturate(col0)                 col0 = vp c467 / c466
sun    = tex12(LUT(col0.w, saturate(dot(normalize(tc1), -sunDir)))).x * (4.5,4.24,3.95) * tc1.w
c      = albedo * tc0.z + sun
c      = lerp(c, fogColour (0.5,0.6,0.75), tex11(tc6.z).w)
MRT0   = c * tc6.y          tc6.y = vp c33.x  (exposure)
MRT1   = MRT0 * 0.0625
```

- **The exposure source:** VS `CEED7030` writes `o[13].y = vp_c[33].x`, and the FP's last ALU step multiplies by it.
- **The same applies to every other scene/reflection VS** (`0E74E41D`, `2F867C86`, `94C50138`, `158A5048`, `DBB8413B`): all 215 draws into `0x750000`/`0x7B78D80` carry the same c33.
- **Exposure FP `0074C781`** (fp c5 = (3,…), c6 = (0.3, 0.006, 0.7, 0.09)):
  - G = clamp(sqrt(lum × tc0.z), 0.006, 3), where tc0.z = 1/c33;
  - E = max(0.3/G × 0.7 − 0.7 + 1, 0.1) = 0.3 + 0.21/G.
  - So E(0) = **35.3**, E(0.1) = 2.4 and E(1) = 0.51.
- **c33 across every capture** (`c33_scan.py`), as (c33.x, c33.w):

  | capture | c33 |
  |---|---|
  | garage first frame | (3.401, 0) |
  | garage, later frames | rising 31.4 → 34.9 → 35.25 → 35.30, and (…, 50) |
  | all later garage, menu and race captures | **35.29–35.30** |
  | T71 | **35.218 / 35.225 / 35.232**, still rising |

  - It always converges to E_max, whatever the image: a dark garage, a black race (T68), a half-white race (T71).
  - So the CPU's input never reflects the render.
- **The CPU side** (STATUS T11–T13, rtrb watch/probe runs):
  - `func_004C3778` reads the G half of the exposure surface from guest memory;
  - with `RSX_RT_READBACK=1` the copy reaches the guest and is read one flip later;
  - without it, guest memory is never written.
  - **T71 had no `RSX_RT_READBACK` and logged no `[rtrb]` lines** (VERIFIED).

## 4. Texture and constant analysis

- **Terrain units (op 204):**
  - u0 albedo; u11 X16 256×1 (fog curve); u12 Y16X16F 32×512 (sun/scatter LUT); all `upload` sources and resolved.
  - u13 shadow `0x0B030000` is a null SRV. It is not read by `07A9CEC1`; no shadow draws in the race (T67).
- **Formats:** targets RGBA8 (A8R8G8B8, pitched). MRT1 encodes colour/16 as the game intends. No format or channel misinterpretation.
- **Blend:** off, `cmask` 15, on all terrain draws. No blending accumulation.
- **Bound from the captures:**
  - every written pixel has pre-exposure colour ≥ 16/35.2 = **0.454** per channel (MRT1 saturated);
  - MRT0 saturates above 0.028.
  - Plausible for fogged distant terrain (fog colour 0.5–0.75; sample depths 2600–10000).
  - At a closed-loop exposure (G ≈ 0.5–1 gives E ≈ 0.5–0.7), the same colours land in 0.23–0.7: unsaturated.
- **Not examined:** texel contents. RSXI holds no texture dumps for these units; not needed for the conclusion.

## 5. Main scene vs reflection

| | reflection 5–196 | main 197–208 |
|---|---|---|
| terrain programs | `CEED7030`/`07A9CEC1` | same |
| fp constants | identical | identical |
| terrain textures | identical | identical |
| object programs | 6 VS / ~20 FP, all read tc6.y = c33 | — |
| target | RGBA8 640×480 | RGBA8 1280×720 + MRT1 |
| exposure | c33.x = 35.218 | same |

**The shared defect is the single CPU-fed exposure constant**, so both passes saturate identically. Nothing else in common is abnormal.

## 6. Zero-sample draws (ops 197–201, 203; secondary)

- **Primitive restart: not a cause.**
  - The index stream has restart enabled at 0xFFFF and active.
  - The backend's CPU strip expansion honours it (`rsx_d3d12_backend.c:8553-8563` at `c529ab0`, `ps3_prim_stream_restart`).
- **Under the captured camera** (`zero_draws.py`, bbox corners plus 8 sampled vertices through c256–259 then c0–c3):

  | ops | result |
  |---|---|
  | **199, 200** | bbox entirely outside the frustum (y > w, x > w): legitimately invisible (VERIFIED) |
  | **198, 201** | all sampled vertices behind the camera (w ≤ 0) |
  | **197** | samples behind, or far above the screen (NDC y 32–44) |
  | **203** | samples off-screen right (NDC x 3.5–4.3) |

  - Terrain is chunked around the camera, so chunks behind or beside it are submitted and rasterise nothing.
- **Depth:** not implicated. Scene z is 0.998–0.999999 (far plane ≈ 10000) against a 1.0 clear with LEQUAL, and the visible chunks at the same depths pass.
- **Conclusion: PARTIAL.** Consistent with legitimately off-screen chunks; proven for 2 of 6. Eight samples per draw cannot exclude a sliver: ops 206 and 208 also have all samples behind, yet pass samples. A full-index evaluation would need the whole vertex buffer, which RSXI does not store.

## 7. Root cause and confidence

| claim | label |
|---|---|
| Saturation starts at the terrain FP output, caused by the ×c33.x factor | VERIFIED |
| c33.x = 35.2 equals the exposure formula's maximum (G clamped at 0.006), in every capture, independent of content | VERIFIED |
| The exposure surface `0x07EBA600` is written by op 250 and never GPU-sampled, so it is consumed by the CPU | VERIFIED |
| T71 ran without `RSX_RT_READBACK`, so the backend did not write it back | VERIFIED |
| The guest therefore read zero luminance | VERIFIED by the formula match; the guest bytes were not dumped |
| With readback, the loop lowers E to about 0.5–2.4 and the terrain shows textures and lighting | **REJECTED** by the T72 run (§10): readback delivers the data, but `c33.x` stays at 35.29 |
| The CPU's exposure samples land mostly in an unrendered (zero-luminance) part of the frame | **PARTIAL** (§10) |

Earlier "loading-screen brightness" observations were not used as evidence.

## 8. Correction

**No code change is needed, and none was made.**
- The fidelity-preserving fix already exists: the generic render-target write-back `RSX_RT_READBACK=1`.
- **It is in the T64C exe:** `c529ab0` contains `5b1988f`'s successors `1fd750a` (format decode fix) and `61fed2d` (watch/probe).
- **It restores the RSX semantics the game relies on:** render targets live in guest-visible memory.
- **Selection is generic,** with no address or shader rule. A written, never-sampled surface ≤ 64 KB in FP16×4 qualifies, and `0x07EBA600` is 2 KB FP16×4.
- **Not done:**
  - no exposure clamp, no c33 override, no shader edit;
  - not made the default. That is a framework policy change with performance cost, for a later decision after the race run confirms it.
- **Offline tests:** `t72/exposure_model.py` reproduces the formula and checks c33, the c33 sharing and the white-pixel/sample identity: 15/15 PASS. The existing `tests/test_rt_readback.c` covers the readback path (275 checks, STATUS T13).

## 9. Recommended runtime validation (needs authorization)

**One run:** the T71 Run A configuration (T64C exe, private HDD, ≤205 s, same path, no driving) plus:
- `RSX_RT_READBACK=1`;
- `RSX_RT_READBACK_WATCH=07EBA600`;
- `RSX_RT_READBACK_LOG=160`.

No rebuild.

**Success checks:**
1. `[rtrb]` selects and applies `0x07EBA600`.
2. c33.x in the RSXI frames drops well below 35.3.
3. `0x750000` and MRT1 show graded colour (more than 2 unique values, and not white == occlusion).
4. The backbuffer shows textured terrain and sky.
5. No new timeout.

**Run B** (the `dfb9e2f` exe without `VP_NOFIXPROJ`) remains separately pending. It could carry the same env.

## 10. Runtime validation with readback (T72, one authorized session)

**The session:**
- **Run:** `generated/runs/20261026-160135-t72-exposure-readback`; controller log in `t72/runtime-20261026-160135/`; stdout in `t72/launch_stdout.txt`.
- **Script:** `t72/run_t72.py`. It is `t71/run_t71.py` with the env additions below, the 8th RSXI target `07EBA600`, its own run name and trace-config copy. The diff against T71 is exactly those lines.
- **Exe:** T64C `162afb4a…`, hash checked in preflight. No rebuild.
- **HDD:** fresh private `t72/hdd0|hdd1`, with sha256 identical to T71's.
- **Env:** T71 Run A (`VP_NOFIXPROJ=1`, WWS AOT off, no `TEX_SAVE`, no `RT_CLEARDBG`), plus `RSX_RT_READBACK=1`, `RSX_RT_READBACK_WATCH=07EBA600` and `RSX_RT_READBACK_LOG=160`.
- **Path:** the same navigation. LOAD RACE at 65.7 s, PostLevelLoad at 151.8 s.
- **Capture:** RSXI frames **f005625–f005627**, complete at 187.5 s.
- **Stop:** the controller stopped after the RSXI race capture (no driving), at 188 s. Termination `exited_error` (exit 1), the same as T71. No leftover process.

| # | check | result |
|---|---|---|
| 1 | readback identifies `0x07EBA600` | **VERIFIED.** `rt:create` at flip 5515 (16×16, DXGI 10); `young` at 5515–5516; **selected** at gen 3, flip 5517. Never evicted, sampled or skipped. Over the session: `queued=2401 applied=2401`, with zero stale, aborted, unmapped or no_mem. |
| 2 | GPU luminance reaches guest memory | **VERIFIED.** Every watched apply is `result:applied nz=512/512`. Decoded pixel (0,0) (G = luminance, R = exposure; table below) matches E = 0.3 + 0.21/G to within 0.0005 on every logged apply. |
| 3 | `c33.x` decreases | **NO.** It is **35.2915 / 35.2922 / 35.2929** in f5625–f5627, about 110 flips after the first apply, and still creeping toward 35.3. The value is identical on all scene/reflection draws of each frame. |
| 4 | graded terrain pixels | **NO.** MRT1 after op 242 is 2 values; white px 422162 = the samples passed by ops 202–208 (4491 + 340156 + 7524 + 28417 + 6872 + 34702), exactly as in T71. |
| 5 | reflection and object shading | **NO change.** `0x07B78D80`: 57 % covered, white or black, the same as T71. |
| 6 | recognisable Kanaloa Bay | **NO.** The backbuffer equals T71's: a white upper band, a black lower half, two white terrain patches and the HUD (`t72/snaps/f5625_snap10_end_op9999_bb_00000000.png`). |
| 7 | stalls and frame time | **No significant change.** Race heartbeats: T71 4.8 fps over its last 10.5 s; T72 4.6 fps over its last 10.8 s (both WWS-limited, about 5 fps). PT stall lines: 33 (T71: 34), all but 7 at boot, as in T71. No `[rtrb]` no_slot or no_mem. |
| 8 | GPU timeout, crash, device removal | **None.** 0 Present-timeout, device-removed, DXGI-error or fatal lines; no fc-watchdog report. |

**Exposure progression** (guest bytes at `0xC7EBA600` pixel 0,0, from the `[rtrb] watch` lines; the watch log budget ended after n=65):

| apply n | flip | luminance G | exposure E (GPU) |
|---|---|---|---|
| 1 | 5517 | 1.0059 | 0.5083 |
| 2 | 5518 | 1.0938 | 0.4919 |
| 4 | 5520 | 0.9829 | 0.5132 |
| 8 | 5524 | 0.8535 | 0.5459 |
| 65 | 5581 | 0.6738 | 0.6113 |

The GPU side computes a closed-loop exposure of about 0.5–0.6. The CPU-fed constant does not follow it.

**Why `c33` stays at its maximum:**
- **The exposure surface is only partly lit (VERIFIED).** The f5625 snapshot after op 250 has rows 0–5 at about (E 0.61, G 0.67) and rows 6–15 at (E ≥ 1, **G = 0**). That is exactly the FP's output for zero luminance (E = 35.3).
  - Op 250 does cover the full 16×16: a quad (0..1)·2−1, c467 = (2, 1, 0, 0), viewport and scissor 16×16.
  - So these rows are computed, not left unwritten.
- **Their luminance is genuinely zero (VERIFIED).**
  - The luminance target `0x02195900` is 99.4 % non-zero in the top 7/16 of the frame and **0 %** from about 50 % of the height downward.
  - The scene `0x750000` matches this: a black lower half, apart from two terrain patches.
- **The CPU samples the black part (VERIFIED offsets, value read not instrumented in this run).**
  - `func_004C3778` reads the G half at +0x242, +0x52A, +0x552, +0x592 and +0x5EA (STATUS, T11–T13). Those are pixels (8,4), (5,10), (10,10), (2,11) and (13,11).
  - One sample is in the lit rows; four are in rows 10–11, where G = 0.
  - This matches the earlier garage watch run, where only +578 (0x242) read non-zero.
- **Conclusion: PARTIAL.** With 4 of 5 samples at zero luminance, the CPU's target stays at the maximum, so readback cannot lower `c33`. The CPU-side reduction (average, minimum or filter) is not decoded, and its read values were not logged in this run.

**What leaves the lower half unrendered: HYPOTHESIS, the next lead.**
- The lower screen of a Kanaloa Bay start should be ground and water. In this frame:
  - terrain ops 197–201 and 203 pass 0 samples (§6);
  - the quarter-res water ops 212–221 (fp `02B9EC81`, **stencil test on**, ref 64) pass **0** samples;
  - op 225 (stencil test on) passes 0;
  - the main-scene water ops 226/227 pass only 2370 and 979 samples.
- This points to the missing water/near-ground coverage, possibly linked to the known PSO depth/stencil defect (T67 (a)) or the water feedback hazard (T67 (b)). Unproven.

**Remaining visual defects** (exposure not restored, so all of them still apply):
1. Exposure is pinned at its maximum because the frame's lower half has no luminance. Readback is necessary but not sufficient.
2. Water and near-ground coverage is missing (0-sample stencil-tested water ops, 0-sample terrain chunks).
3. Everything drawn is saturated white (a consequence of 1); textures cannot yet be judged.
4. Already known: PSO depth/stencil state (T67 (a)), the water RT feedback hazard (T67 (b)), no shadow pass, about 5 fps.

**Artifacts:**
- `t72/analysis_20261026-160135-t72-exposure-readback.txt` (`t68/analyze.py`);
- `t72/snaps/f5625_*.png`: scene, luminance, exposure surface, reflection, backbuffer;
- raw BMPs in the run's `rsxi/frames/`;
- the `[rtrb]` lines in the run's `stderr.log` (234 lines).

**Recommended next step (offline first, no launch):**
- Explain why the stencil-tested water ops 212–221/225 pass 0 samples. Compare the guest stencil state and the stencil clear value with the host PSO (T67 (a) says the PSO ignores stencil).
- Decode the CPU reduction after `func_004C3778` to confirm how 1 lit and 4 dark samples give E_max.
- Keep `RSX_RT_READBACK=1` in later race runs: without it all five samples read 0.
- Any further launch needs separate authorization.
