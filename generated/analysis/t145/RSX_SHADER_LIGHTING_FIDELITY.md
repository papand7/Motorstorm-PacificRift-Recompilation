# T145: RSX shader, material and lighting fidelity

Offline analysis, then one authorised runtime A/B (2026-10-28, 4 launches, §10). No merge, no push.

- Worktree `ps3recomp-t145`, branch `agent/t145-rsx-shader-lighting-fidelity`.
- Base `e9f3237` (T142 tip, which includes T141 `07b453f`).
- Commits `49fc83f`, `1dff0eb`, `f7f9366`.
- Evidence comes from:
  - the T113 race RSXI captures I (`t113/runtime-I-20261027-182926`, frames f006502 and f006527) and G;
  - lifted PPU code (`generated/ppu`);
  - WARP and real-backend tests in this tree.

Labels: VERIFIED, PARTIAL, HYPOTHESIS. No visual claim is made without a runtime A/B.

## Summary

- **Runtime A/B (§10):**
  - VERIFIED: with `RSX_SHADER_WINDOW=1`, all three WPOS programs compile, are remapped to the guest window `0x12D0`, and all 7 WPOS draws per frame carry `wpos_remap=1`. No PSO failures and no new debug-layer messages (80 warnings per run in every arm, 0 errors).
  - NOT VERIFIED: any visible improvement. In the captured race phase, the scene and water WPOS draws change 0 pixels in every arm. The surf draws change about 213–235 k pixels in every arm. The dominant surf artifact (foam painted over the foreground beach) appears with and without the fix.
  - `RSX_COLOR_XFER=7` runs in the race (arm D) with no validation errors. Arm C (both switches) did not reach the race within the 440 s cap; the cause is unknown.
  - Frame time is within single-run noise (debug layer on).

- **VERIFIED defect, fixed (opt-in): WPOS in the wrong window.**
  - What RSX does: WPOS is expressed in the `SET_SHADER_WINDOW` system (height, origin, pixel centre), with w = 1/w.
  - What the backend did:
    - The D3D12 guest-FP path read WPOS as `SV_Position` (top-left origin, clip w).
    - It never parsed `SET_SHADER_WINDOW` (method `0x1D88`).
  - What MotorStorm does:
    - Its render-target setup writes `height | 0x1000`, i.e. origin bottom, half centre.
    - Three race programs (7 blended scene draws per frame) build a screen UV from WPOS as `(720 − y)/710`.
    - On D3D12 those lookups into the scene copy, the scene and the scene depth are therefore **vertically mirrored**.
  - The fix is `RSX_SHADER_WINDOW=1`.
- **VERIFIED from captures: the race asks for colour transfers, and the default path applies none.**
  - 634 of 1582 draws ask for sRGB output (`SET_SHADER_PACKER`).
  - 769 draws fetch sRGB-flagged textures (`gamma_mask 7`, mostly DXT1).
  - Both cover nearly every main-scene draw.
  - Without them, lighting is computed on sRGB-encoded values. A correct implementation already exists (T110 `RSX_COLOR_XFER=7`, WARP-verified) but has never been run in game.
- **VERIFIED from the ISA layout, latent: `SRC2.abs` (bit 18) is ignored by the decoder.** Race use is unknown, because the captures hold no ucode. Not changed.
- **Shader coverage:** no unsupported opcode in any of the 739 captured program dumps.

## 1. Shader instruction coverage (Phase 1)

Audited files:
- `rsx_fp_decompiler.c` (2006 lines; NV40 fields per nouveau `nvfx_shader.h` and RPCS3 `RSXFragmentProgram.h`);
- the dumped race HLSL.

| Area | Finding | Label |
|---|---|---|
| Opcodes | All opcodes in the race captures are handled. There are 0 `TODO` lines in 739 dumps across captures F–I. DDX/DDY/TXD/DP2A/SFL/STR are not translated, but no race program uses them. | VERIFIED |
| Source modifiers | SRC0 abs is bit 29 and SRC1 abs is bit 18; both are handled. Negate is bit 17, applied after abs. **SRC2 abs (bit 18 of word 3) is never decoded**: `decode_src(w3, 0, …)`. This affects MAD, LRP and DP2A with \|src2\|. | defect VERIFIED (layout); race impact unknown |
| Result scale / saturate | SRC1[28:30] ×2/×4/×8 and ÷2/÷4/÷8 are applied before saturate. The precision clamp is opt-in (`RSX_FP_PRECISION`, T133). | VERIFIED |
| Swizzle and write mask | The result is broadcast and the mask picks matching lanes. An empty mask means xyzw (RPCS3 `GetMask`). | VERIFIED |
| Predication | `exec_if` lt/eq/gt, the condition swizzle and CC0/CC1 are implemented as a per-lane select; `set_cond` is implemented. 104 of 149 race FPs are predicated. | VERIFIED (code) |
| Flow control | IFE, LOOP, REP and BRK are handled. CAL and RET are skipped, but none appear in the race. | VERIFIED |
| Register files | h and r are kept as separate arrays, with the alias sync from T-era fixes. 120 race FPs need the sync. Writes to h registers are **not rounded to fp16**; RPCS3 behaves the same. | PARTIAL |
| Exports | The export register file follows `SHADER_CONTROL` bit 0x40. The race uses 16-bit exports (0x40 clear) everywhere. Under 16-bit exports, h4/h6/h8 count as MRT targets B–D, whether or not those targets are bound. | VERIFIED |
| NaN at export | A non-finite export is replaced by 0 per lane. This is host policy, not RSX behaviour. | HYPOTHESIS |
| RSQ / DIVSQ / LIF | Sign-ignoring sqrt; DIVSQ returns 0 where the numerator is 0 (RPCS3). | VERIFIED |
| Inputs | Colour inputs are saturated. TC0–9 are perspective-corrected by SRC2 bit 31 (80 race FPs). FACING is used by 6 race FPs. **WPOS: see §3.** | VERIFIED |

## 2. Race shader inventory (Phase 2)

The full table is `RACE_SHADER_INVENTORY.md` (hashes and metadata only), generated by `tools/inventory.py` and `tools/inventory_md.py`. The raw data is `inventory_I.json` and `inventory_G.json`.

**Fragment programs (capture I, 2 frames):**
- 149 FPs and 1582 draws.
- Instructions per program: 1 / 51 / 227 (min / median / max).
- Texture units fetched per program: 0 to 12.
- Feature counts:

| Feature | FPs |
|---|---|
| predicated | 104 |
| fp16/fp32 alias sync | 120 |
| more than one export | 119 |
| sRGB-output draws | 114 |
| gamma-unit fetches | 93 |
| perspective texcoords | 80 |
| LG2/EX2/POW | 65 |
| `_bx2` fetches | 52 |
| kill | 30 |
| LOD bias / level | 27 |
| DIVSQ | 7 |
| facing | 6 |
| RSQ | 3 |
| **direct WPOS reads** | **3** |
| depth export | 0 |

**Vertex programs:** 34, with 2 / 27.5 / 78 instructions (min / median / max).

**Passes in frame f006502:**

| Target | Format | Draws | Role (inference) |
|---|---|---|---|
| `0x00750000` | A8R8G8B8, antialias 3, with MRT `0x01650000` | about 430 | Main scene. Every draw asks for sRGB output; most fetch gamma DXT1 textures. |
| `0x07B78D80` | 640×480 A8R8G8B8 | 166 | Secondary view (HYPOTHESIS: reflection/environment); also sRGB with gamma fetches. |
| `0x02195900` → `0x022C1600`, `0x07EBA600` | FP16 (`0x0B`) chain, 320×180 down to 10×5 | — | Luminance/exposure chain. No sRGB (excluded by the format). |
| `0x07EBAE00` / `0x07EF3200` / `0x07F2B600` | 320×180 | — | Bloom/blur. |
| `0x01DD0000` | 1280×720 | — | Composite. Reads the scene with gamma 0, i.e. encoded values. |

**Shadow frame f006527:**
- 755 draws into the shadow atlas `0x0B030000`: 3 FPs of 1–4 instructions, 188 of them alpha-tested (DXT gamma fetch).
- 135 draws into `0x00ED0000` (depth pre-pass).
- The scene samples the shadow atlas as a depth texture on 415 draws, plus 167 on `0x07B78D80`.

## 3. Verified translation defects (Phase 1, 3, 5)

### D1: WPOS ignores `SET_SHADER_WINDOW` (VERIFIED)

**RSX rule.** The `0x1D88` word is:
- height in bits [11:0];
- origin in bits [15:12] (0 = top, 1 = bottom);
- pixel centre in bits [19:16] (0 = half, 1 = integer).

WPOS is (x, y, z, 1/w) in that system (NV_fragment_program `f[WPOS]`; RPCS3 rebuilds it from `gl_FragCoord` and this register).

**Backend.** Nothing in the tree parsed `0x1D88`: no match for it in `libs/`. WPOS was emitted as `input.position`.

**Guest (static, lifted code):**
- The ICE/GcContext render-target builder `func_007367FC` does `r9 = r5 | 0x1000` and stores it at `+0x50`, where r5 is the height also used for log2(h) in the surface format.
- `func_007360A0` emits `0x00041D88`, followed by that word.
- This is the only `0x1D88` header in the lifted code.
- Result: origin bottom, half centre, height = surface height (720 for the scene).

**Race programs (capture I):**

| FP | Instructions | Draws | Builds UV from WPOS and samples |
|---|---|---|---|
| `0x070B0701` | 190 | ops 595–598, MRT, blended | u1 = scene copy `0x0243AB00` (640×360) |
| `0x07200641` | 227 | ops 599–600 | u4 = scene depth `0x00ED0000` (zeta as colour) |
| `0x022CD841` | 40 | op 594 | u2 = scene `0x00750000` |

- All three use the constant `(1/1262, −1/710, 0.000195, 1.01408)`, i.e. uv.y = (720 − WPOS.y)/710.
- That maps the screen top to v = 0 only under the bottom origin.
- With `SV_Position` (top-left), every lookup lands on the vertically mirrored row.

**Also wrong:** WPOS.w was clip w, not 1/w. The race programs read only .xy, so this has no race impact (VERIFIED from the masks).

### D2: `SRC2.abs` dropped (VERIFIED from the layout, latent)

- The bit position is the same in nouveau (`NVFX_FP_OP_SRC2_ABS (1 << 18)`) and RPCS3 (SRC2 `abs:1` after `neg`).
- Not fixed. The race captures hold no ucode, so whether any program sets the bit is unknown.
- Fix recipe: `decode_src(w3, w3 & (1u << 18), &s2)`, opt-in, after the ucode is captured (see §10).

### D3: the guest's colour transfers are not applied by default (VERIFIED request, PARTIAL effect)

- Per draw, RSXI's `dr_color_xfer` reports what the guest asks for:
  - capture I: `srgb_output` on 634 of 1582 draws, fetches of gamma units on 769;
  - capture G: 1238 and 1468 of 2992;
  - `expand` (UNSIGNED_REMAP_BIASED): 0.
- This answers T108 Q6 ("does MotorStorm ask?"): yes, on nearly every scene draw.
- The FP compile applies the transfers only with T110's `RSX_COLOR_XFER=<mask>`, which defaults to none (`host_xfer:"none"` in every draw).
- Effect (arithmetic, HYPOTHESIS for the picture): lighting runs on encoded texels and the result is stored unencoded. For albedo a and light factor L:
  - ours = a·L;
  - RSX = enc(dec(a)·L) ≈ a·L^0.45.
  - L = 0.25 gives 0.25·a instead of 0.53·a, so shadows are too dark.
  - L = 2 gives 2.0·a (clipped) instead of 1.37·a, so highlights are overbright.
  - The rendering therefore has too much contrast.
- This is guest state, not a gamma tweak. It still needs a runtime A/B, because no native reference exists.

## 4. Implemented corrections (Phase 6)

All of these are behind `RSX_SHADER_WINDOW=1` (read once, off by default).

- `libs/video/rsx_shader_window.h` (header-only):
  - `rsx_sw_key`: 0 if the register was never written or holds an undefined origin/centre.
  - `rsx_fp_wpos_reads`: ucode scan, the same walk as `rsx_fp_texture_units`.
  - `rsx_fp_apply_shader_window`: rewrites `(input.position).` to `(_rsx_wpos(input.position)).` and adds `float4(p.x[-0.5], H - p.y[-0.5] | p.y[-0.5], p.z, 1.0 / p.w)`.
  - Perspective texcoords (`_rsx_inv_w(input.position)`) are untouched.
  - It refuses without mutating when there is no room, the key is invalid, or the text was already rewritten.
- `rsx_commands.[ch]`: `NV4097_SET_SHADER_WINDOW`, plus `shader_window` and `shader_window_set`.
- `rsx_d3d12_backend.c`:
  - Draw records copy the register.
  - Both guest-FP lookups set `s_fp_wpos_req = dr_wpos_req(dr)`.
  - Only programs that read WPOS take the window into their pipeline key. This is a separate reject step, so T110's pinned key line is verbatim.
  - The text is rewritten after the sRGB-output rewrite.
  - `[WPOS]` is logged per compile (first 16).
  - RSXI draw events gain `shader_window`, `shader_window_set` and `wpos_remap`.
- **Cache keys:** new `VPFPEntry.wpos_key`. With the switch off it is always 0, so every pipeline and every HLSL text is byte-identical to the base. The on-disk shader cache (T116/T117) is not in this base; it keys on HLSL text, so the rewritten text would be a new key automatically.
- One-shot patch: `tools/patch_t145.py`. It reproduces the committed backend, commands and header files byte for byte (checked against a clean `e9f3237` copy).

## 5. Pixel-level test results (Phase 7)

**WARP + debug layer + GPU-based validation** (`libs/video/tests/test_t145_shader_window_warp.c`; real decompiler output): **35/35**, 0 debug-layer errors. Log: `logs/warp_shader_window.log`.

| Case | Old text | `RSX_SHADER_WINDOW` |
|---|---|---|
| WPOS.xy, 16×8 target | top-left, half centre (128/128) | bottom/half, top/integer and bottom/integer, each 128/128 exact |
| Race lookup `uv = WPOS·(1/W, −1/H) + (0, 1)`, TEX unit 1 | **mirrored 128/128**, own texel 0/128 | **own texel 128/128**, mirrored 0/128 |
| WPOS.w at clip w = 2 | 2.0 (saturated) on 128/128 | 0.5 on 128/128 |

Also covered:
- ucode scan: 3 WPOS programs count 1; the perspective-TC0 fetch counts 0.
- Keys: `0x12D0` gives a valid key; an unwritten register or an undefined origin/centre gives 0.
- Refusals leave the text unchanged.

**Real backend** (`test_t145_backend.c`, project flags; RSXI snapshots; `tools/wpos_check.py`):
- The scene is a 1280×720 vertical ramp (225 distinct rows).
- The window is written through `rsx_process_method`.
- Log: `logs/arms_final.log`.

| Arm | RT_L (WPOS lookup) vs scene | RT_N (TC0 read) | Debug-layer errors |
|---|---|---|---|
| `off` (window written, switch off) | mirrored 921,600/921,600 | identical | 0 |
| `on` | **identical 921,600/921,600** | identical | 0 |
| `on_gbv` (`D3D12_GBV=1`) | identical 921,600 | identical | 0 |
| `on_all` (+ `RT_WINDOW`, `RT_FEEDBACK`, `MRT_STATE`, `COLOR_XFER=7`) | identical 921,600 | identical | 0 |
| `on_unset` (register never written) | mirrored (unchanged behaviour) | identical | 0 |
| `on_top` (`0x02D0`) | mirrored (the program's formula, per RSX) | identical | 0 |
| `on_int` (`0x112D0`) | integer-centre remap logged; the lookup lands on a texel boundary | identical | 0 |

**Regressions:**
- Suite (`tools/run_suite_t145.cmd` = T141 list + `test_shader_window`): **41/41 PASS** on T145. The baseline `e9f3237` is identical, apart from the new test being absent (`logs/suite_final.log`).
- One pin broke on the way (T110's key line) and was fixed by keeping the line verbatim.
- `test_fp_decompiler.c` builds in neither tree on Windows (POSIX `setenv`). It is pre-existing and left out.

**Builds and audit:**
- Backend TU (`tools/tu_t145.cmd`): 0 errors, 3185 warnings, the same 27 classes as the baseline (3162).
- Audit: 25 inherited items, none in T145 files.

## 6. Material and lighting findings (Phase 3, 4, 5)

| Path | Programs / state | Finding | Label |
|---|---|---|---|
| Terrain, vehicles (main scene) | 54 + 20 + … FPs on `0x00750000`; DXT1 gamma 7 on units 0/2/14/15 | Lit in gamma space without `RSX_COLOR_XFER` (D3) | VERIFIED request; effect HYPOTHESIS |
| Water / refraction | `0x070B0701` (u1 scene copy at WPOS UV) | Mirrored lookup (D1) | VERIFIED translation; visual HYPOTHESIS |
| Surf / shore | `0x07200641` (u4 scene depth at WPOS UV) | Mirrored depth lookup (D1). Also needs T141 `RSX_ZETA_EXACT`. At runtime it compiles and draws on this base without T117 (§10). | VERIFIED translation; visual HYPOTHESIS |
| Scene feedback | `0x022CD841` (u2 scene at WPOS UV) | Mirrored (D1). T141's feedback copy supplies the texels. | VERIFIED |
| Vegetation | 6 FPs read FACING; alpha masks on unit 0 | Facing is handled; unit 0 is point/clamp without `RSX_GUEST_SAMPLERS` (T110) | renderer state |
| Shadows | 415 + 167 draws compare against `0x0B030000` (helper `_rsx_shadow*`, reversed func per RPCS3) | No translation defect found. Stencil is covered by T144. | PARTIAL |
| Sky, particles, specular, reflections | LG2/EX2/POW in 65 FPs; no DDX/TXD | No defect found beyond D3 and the half-precision note | PARTIAL |
| Precision | h writes not fp16-rounded; FP16/FX12/FX9 clamps opt-in (T133); NaN export forced to 0 | Small or unproven; nothing changed | PARTIAL |
| Texture colour space | Gamma decoded after filtering (T110 D7) | A few LSB at edges | PARTIAL, accepted |
| Texture instructions | TEX/TXP/TXB/TXL; shadow compare; T142 fetch masks are used for the gamma/expand keys | No defect found | VERIFIED (code) |

## 7. Remaining visual mismatches (Phase 8)

| Artifact | Class | Evidence |
|---|---|---|
| Dark / wrong water | **Verified shader translation issue** (D1, mirrored refraction lookup). The visible link is a HYPOTHESIS. | §3 |
| Excessively bright surf / foam over the foreground beach | Present in arms A, B and D alike, so not caused by D1. Suspected renderer state: depth contents or the depth test (surf: test on, write off, func 3) or the zeta-as-ARGB8 decode. HYPOTHESIS. | §10, T141 |
| Wrong lighting intensity / material colours | Renderer state: colour transfers off (D3) | §3 |
| Missing highlights | Unresolved. Candidates: D3, h-register precision. | — |
| Vegetation shading | Renderer state (sampler on unit 0, `RSX_GUEST_SAMPLERS`) | memory note, T110 |
| Shadow differences | Unresolved here (T144 stencil, shadow compare unproven at runtime) | §6 |

Nothing is claimed fixed on screen (confirmed by §10).

## 8. Performance impact

- **Switch off:** one predictable branch per pipeline lookup. No new pipelines, no text change.
- **Switch on:**
  - Each pipeline lookup adds one ucode walk (the same cost as the existing gamma-unit walk; HYPOTHESIS ≤ 0.1 ms/frame for about 700 lookups).
  - Each WPOS program compiles once per window. MotorStorm uses one window, so +0 pipelines in steady state, and 3 recompiles on first use.
- Measured in the race (§10): A 3.50 FPS, B 3.98 FPS, D 3.97 FPS. These are single runs with the debug layer on, so the spread is noise, not a speed-up.

## 9. Integration dependencies and conflicts

- **Base:** T142 `e9f3237`, which includes T141.
- **T117** (`fd97181`, FP 16 KiB window + END check) is not in this base.
  - Correction: the offline claim that `0x07200641` does not compile without T117 was wrong. In the runtime A/B it compiled, was remapped and was drawn twice per frame on this base.
  - T117 was not enabled. Whether T117 changes that program's ucode is untested.
  - T117 sits on the T116 shader-cache line (`30b817b`), not on T141's. Integrating it means cherry-picking `fd97181`, plus T116's `c8d8a0a`/`30b817b` if the cache is wanted.
  - Its files overlap with T145 only in `rsx_d3d12_backend.c` (the FP window constant), not in the hunks T145 changes. The merge has not been tried.
- **T144** (`c31aa83`, stencil) branches from T141 too. It touches only `rsx_d3d12_backend.c` among T145's files (`rsx_depth_state.h` and its tests are its own). Different hunks; the merge has not been tried.
- **T143:** worktree only, no commits.
- **T141:**
  - `RSX_RT_FEEDBACK` supplies the scene texels that `0x022CD841` and `0x070B0701` read.
  - Only with `RSX_SHADER_WINDOW` do those reads land at the pixel the guest addresses.
  - T141's harness read feedback at `SV_Position`, which is the corrected behaviour.
- **T110 `RSX_COLOR_XFER`:** independent of this change. The `on_all` arm combines them without errors.
- **Tooling note:** T142's copied `tu_flags.cmd` pointed at `ps3recomp-t141`, so its harness compiled `tests/*.c` against T141 headers. T145's copy is fixed.

## 10. Controlled runtime A/B (authorised 2026-10-28)

**Setup:**
- One exe: `build/motorstorm-t145` (`ps3recomp-t145` at `f7f9366`), sha256 `8e64eef3…4878793`, pinned in `ab/exe_b.sha256`. T117 is not in the build.
- Runner `ab/run_t145ab.py`, generated by `ab/make_runner.py` from `t106/ab/run_ab.py`. Same route, intro skip and controller. Race entry = first `[rsx-hb]` with `last_draws >= 200`.
- Common env:
  - `RSX_RT_WINDOW=1 RSX_RT_FEEDBACK=1 RSX_ZETA_EXACT=1 RSX_GUEST_SAMPLERS=15 RSX_GPU_SYNC=20`;
  - `D3D12_DBG=1 D3D12_IQ=1` (debug layer, first 80 messages);
  - `RSX_XFER_LOG=48`, `RSX_FRAME_PERF=12,1,100000`.
- Capture: one RSXI capture per arm (2 frames, stride 25, pass snapshots), gated on the water program `0x070B0701` and a trigger file written at race entry + 30 s. That is the same race phase in every arm.
- Each run stops at race entry + 90 s, within the 120 s limit.
- Analysis: `ab/ana_t145.py` (WPOS, validation and RSXI pass diffs) and `t122/ab/ana_t122.py` (FPS, window race entry + 15–85 s).
- Four launches in total. `RSX_SHADER_WINDOW` still defaults to 0.

**Results**

| Arm | Env | Race | Race entry (host s) | FPS (xs) | Frame ms p50 / p95 / p99 | Draws/frame | IQ msgs (sev) | `[WPOS]` remaps | WPOS draws (remap) |
|---|---|---|---|---|---|---|---|---|---|
| A1 | `SHADER_WINDOW=0` | yes | 161.4 | 3.50 (3.66) | 270 / 353 / 610 | 1913 | 80 (all 2) | 0 | 7 (0) |
| B1 | `SHADER_WINDOW=1` | yes | 164.0 | 3.98 (4.15) | 234 / 299 / 397 | 1941 | 80 (all 2) | 3 programs, `window=0x012D0` | 7 (7) |
| C1 | `SHADER_WINDOW=1` + `COLOR_XFER=7` | **no**: 440 s hard cap | — | — | — | — | — | — | — |
| D1 | `SHADER_WINDOW=0` + `COLOR_XFER=7` | yes | 164.1 | 3.97 (4.11) | 235 / 298 / 332 | 1937 | 80 (all 2) | 0 | 7 (0, `host_xfer mode_0x7`) |

- The IQ messages are the same warnings in every arm: PSO RTV slots 1–3 expected but unbound (id 679), and clear-value mismatches (ids 820/821). There are 0 errors, 0 device removals and 0 PSO failures.
- `pso_miss` is 0 in every race window.
- XFER: arm A logged 48 `[XFER] … not applied`; arm D logged 48 `… RSX_COLOR_XFER=0x7 applies it`.

**Shader activation (captured frame per arm: A f006148, B f006309, D f006220, ~485 draws each; the second captured frame has no WPOS draws)**

| Program | Draws | Pixels changed on `0x00750000` / MRT `0x01650000`: A · B · D |
|---|---|---|
| `0x022CD841` scene feedback | 1 | 0 / 0 · 0 / 0 · 0 / 0 |
| `0x070B0701` water | 4 | 0 / 0 · 0 / 0 · 0 / 0 |
| `0x07200641` surf | 2 | 212.9 k / 236.6 k · 225.0 k / 225.1 k · 235.2 k / 235.4 k |

How to read this:
- The water and scene-feedback programs draw, but contribute nothing to either target in this phase (all fragments rejected or fully transparent). The same was true in T113 capture I.
- The water fix therefore **cannot be validated** from this race phase.
- Surf "mirror vs own-row" correlation (`corr_mirror` / `corr_self`): A 0.57 / 0.44, B 0.45 / 0.39, D 0.56 / 0.33. B's mirror correlation is lower, which fits the fix, but the metric still favours "mirror" in B, so it does not discriminate. HYPOTHESIS only.

**Visual comparison** (local only, not committed):
- `ab/AB_surf_lower_half.png`;
- `ab/runtime-{A1,B1}-*/{A1,B1}_surf_strip.png`;
- `ab/runtime-*/t145_png/*_{before,after,delta_x4}.png` and `*_backbuffer.png`.

What the images show:
- In A, B and D the surf pass paints water/foam over the foreground beach and totem.
- The foam pattern differs slightly between A and B. The frames are nondeterministic, so this is not attributable.
- D's backbuffer has a different tint (mean RGB 138/152/139, against A 183/183/150). A different moment of the race explains this as well as the colour transfer does, so no XFER visual claim is made.

**C1 limitation:**
- C1 never reached the race. The track load took 66→189 s (A1: 66→86 s), and vehicle loading was still running at 439 s.
- The loading-screen frames took 97–140 ms in `rf` (A1: 3–5 ms), with `present` gate defer/clear ≈ 64/63 (A1: 0).
- There was no crash or hang: frames kept presenting.
- D1, which has XFER without the window fix, loaded normally (race entry 164 s), and B1, which has the window fix without XFER, also loaded normally. So neither switch alone causes this.
- The cause, whether the combination or host variance, is unknown (HYPOTHESIS). No launches were left to repeat it.

**Verified vs suspected**

| Claim | Label |
|---|---|
| `RSX_SHADER_WINDOW=1` remaps all three WPOS programs in game, to the guest window `0x12D0`, with 7/7 draws flagged | VERIFIED |
| The remap adds no validation errors and no PSO failures, and the race still runs | VERIFIED (B1) |
| `RSX_COLOR_XFER=7` is applied in game (48 `applies it`, `host_xfer mode_0x7`) with no validation errors | VERIFIED (D1) |
| `0x07200641` compiles and draws without T117 | VERIFIED (corrects §9) |
| Water refraction improved by the fix | NOT VALIDATED: the water draws contribute 0 px in the captured phase |
| Surf improved by the fix | HYPOTHESIS: the dominant artifact is present in both arms |
| The surf overpaint is a depth/zeta renderer-state issue, not WPOS | HYPOTHESIS |
| Frame time unchanged by either switch | PARTIAL: within single-run noise, debug layer on |
| C1's failure to load is caused by the switch combination | HYPOTHESIS, unrepeated |

**Next steps (need new authorisation):**
- Capture a race phase or track where `0x070B0701` actually writes pixels, for example by checking captures for a non-zero water delta first.
- Repeat C to separate the combination from host variance.
- Investigate the surf depth test against `0x00ED0000`.
- Follow-up to settle D2: dump the race FP ucode to private `generated/` and count `SRC2.abs` uses before changing the decoder.
