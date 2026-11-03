# T110: RSX visual fidelity and rendering corrections (2026-10-27; offline, no build, no launch)

- **Worktree:** `ps3recomp-t110`, branch `agent/t110-rsx-visual-fidelity`, from T108 `6b1a7e4` (T108 has not advanced; its worktree is clean and untouched). Not merged or pushed.
- **Commits:**

  | Commit | Content | Switch (all off by default) |
  |---|---|---|
  | `3c1eb4d` | guest sampler state per texture unit | `RSX_GUEST_SAMPLERS=<mask>` |
  | `2692ec0` | VP draws with attribute 0's array off | `RSX_ATTR0_CONST=1` |
  | `9ca3877` | colour transfers compiled into the guest FP | `RSX_COLOR_XFER=<mask>` |
  | `089d17a` | RT eviction keeps the current guest frame's targets | `RSX_RTPOOL_GF=1` |
  | `e3b961d` | WARP pixel fixtures, T110 source pins | — |

- **With every switch unset, rendering is T108's** (pinned, §5). No visual result is claimed: nothing was run.
- **Ownership:** `ListAgents` shows two peer sessions (01-21 busy, 01-8d idle). T108 and T109 worktrees were not edited; no SPU, timing or gameplay code was touched.

## 1. Defect matrix

| # | Guest state | RSX behaviour | D3D12 before | Passes affected | Visual consequence | Evidence | Test | Status |
|---|---|---|---|---|---|---|---|---|
| D1 | `SET_TEXTURE_FILTER/ADDRESS/CONTROL0/BORDER_COLOR` (0x1A14/08/0C/1C + 32u) | per-unit min/mag/mip filter, S/T/R wrap, LOD range, bias, anisotropy, border | 16 static samplers: **unit 0 point/clamp**, 1–15 linear/wrap, whatever the guest says | every textured guest-FP draw | unit 0 blocky when magnified and never tiles (edge texels stretched); no clamp/mirror/border anywhere else; LOD state ignored | code (root signature); T103 RSXI `host_sampler` | `test_sampler_xlate` (2199), WARP (88) | **VERIFIED defect; fixed (opt-in)** |
| D2 | texture `FORMAT` mip count [31:16] | sampled with its mip chain | **every** host texture `MipLevels = 1`; mips never uploaded | minified textures in 3D scenes | aliasing/shimmer on distant surfaces; mip filters have nothing to work on (D1's mip/LOD fields cannot take effect) | code (all 25 `MipLevels = 1`); garage RSXI `20261023-205211/-220434`: about 27 % of unit bindings carry 3–13 levels (mostly 9–11) | — | **VERIFIED defect; deferred** (§4) |
| D3 | `VERTEX_DATA_ARRAY_FORMAT[0]` size 0 | off array feeds `SET_VERTEX_DATA4F_M`; the VP's `VERTEX_ATTRIB_INPUT_MASK` decides the position | 6 gates drop the draw (`position_attrib_disabled`) | depth-only/shadow passes into zeta `0x00ED0000` (1280×720) and `0x0B030000` (1024×2048), about 440 draws per race frame (T101) | missing shadow-map and depth-prepass geometry; wrong depth-based effects | code; T101 logs and model | `test_attr0_gate` (516) | **VERIFIED defect (class B); fixed (opt-in)**; visual size HYPOTHESIS |
| D4 | `SET_SHADER_PACKER` 0x1FEC, ADDRESS gamma [23:20], `UNSIGNED_REMAP_BIASED` bit 12 | sRGB output on half exports to integer surfaces; sRGB→linear per lane; x·2−1 | ignored by the guest-FP compile (T107) | any draw that asks; MotorStorm writes the packer at 6 sites | if asked: too bright / clipped (loading-screen texel 128 → 200 instead of 157) | T107 code + EBOOT scan | WARP (gamma/sRGB/blend/clamp/2-unit), T107 `test_color_xfer` | **VERIFIED defect; fixed but held off**: whether MotorStorm's frames ask is runtime-only (T108 Q6) |
| D5 | (replay) offscreen RT written before an early-replay cut, sampled after | surface keeps its content | evictable: `used` is reset per replay | composites after T96 early replays, only with a full 32-slot pool | composite input reads nothing (black/stale) | T101 test 9 | `test_rtpool_victim` (11) | **VERIFIED latent defect; fixed (opt-in)**; whether it fires is runtime-only (T108 `RTPOOL_LOG`) |
| D6 | sampler mode 7 `MIRROR_ONCE_BORDER`; mode 5 `CLAMP` (GL_CLAMP) | border / half-border blend | edge clamp | rare | edge texels instead of border | D3D12 has no equivalent | sampler test (mapping pinned) | VERIFIED limitation, kept |
| D7 | texture gamma | decoded before filtering (texture unit) | decoded in the shader after filtering | gamma units with linear filtering | ≤ a few LSB between differing neighbours; exact at texel centres | decompiler design | WARP (point-sampled, exact) | PARTIAL, accepted |
| D8 | anisotropy with a point mip filter | anisotropic | anisotropy dropped (needs D3D12 `MIN_MAG_ANISOTROPIC_MIP_POINT` feature check) | — | slightly blurrier at grazing angles | — | sampler test | PARTIAL, deferred |
| D9 | border colour vs `CONTROL1` remap | order unknown | border taken as A8R8G8B8 → RGBA, before the SRV mapping | border-mode units with a remap | wrong border channel order possible | — | — | HYPOTHESIS |
| D10 | `SET_SHADER_WINDOW` pixel centre | half or integer centre | not audited | all | possible half-pixel shift | — | — | HYPOTHESIS, not changed |
| D11 | exposure readback / bloom alpha (T108 verdict B) | — | `RSX_RT_READBACK` off | race composition | black or blown-out composite | T108 §7 | — | HYPOTHESIS; needs T108's runtime verdict |

## 2. Verified RSX behaviour used

- **Sampler fields** (`rsx_sampler_xlate.h`):
  - Filter, wrap and LOD decode as the framework's existing decoders (`rsx_live_draw.c` `decode_sampler`, `rsx_draw_engine.c`, the Vulkan backend).
  - Bias: FILTER [12:0], signed 1.4.8. Anisotropy: CONTROL0 [6:4] → 1, 2, 4, 6, 8, 10, 12, 16. Border: A8R8G8B8. These follow RPCS3 `fragment_texture`.
  - Convolution filters are taken as linear (the framework took min 7 as nearest), PARTIAL.
  - A non-mip filter samples level 0 whatever the LOD range.
- **Depth-compare units:** the decompiler's helper reads level 0 at texel centres and filters itself, so their sampler is forced to point with no LOD shift, keeping the wrap modes.
- **Disabled attributes:** an off array reads the constant register (T101 VERIFIED with the real `rsx_process_method`/`rsx_fetch_attrib`; re-checked in `test_attr0_gate`).
- **Colour-transfer order** (as compiled):
  1. fetch;
  2. remap;
  3. gamma decode on the fetched lanes (per unit, only units the program samples);
  4. expansion on the remaining lanes;
  5. program arithmetic;
  6. sRGB encode of RGB on the export (alpha untouched, clamped);
  7. blend unit.

  Encoding before blending means blending happens in gamma space, which is G70-class behaviour. That this is RSX's rule is consistent with the hardware generation but **not proven** (PARTIAL). The WARP fixture pins this order.

## 3. Implemented corrections

**C1 `RSX_GUEST_SAMPLERS=<mask>`** (1 = filters, wrap and LOD; +2 bias; +4 anisotropy; +8 border; 15 = all; bit 0 required):
- **Root signature:** keeps CBV b0, the t0–t15 table and CBV b1, then adds 16 single-sampler tables (s0..s15, root parameters 3–18, 21 DWORDs). The PSO's HLSL is unchanged; root-signature compatibility with the decompiler's `SamplerState rsx_samp[16] : register(s0)` is proven by PSO creation on WARP.
- **Sampler heap** (2048, shader-visible):
  - descriptors 0–15 are the old static samplers, bound wherever guest state does not apply (host-built shaders, unbound units);
  - the rest is an append-only cache keyed on the decoded fields. A descriptor is never rewritten, so there is nothing to fence. When full, the unit uses its fixed sampler and one line is logged.
- **Binding:** both heaps and the fixed tables are set after each of the two `vp_root_sig` binds (the main pass and after a zeta conversion). Per draw, only the tables that change are set.
- **RSXI:** `host_sampler` reports `guest` / `guest_depth_compare` / the fixed name.

**C2 `RSX_ATTR0_CONST=1`:**
- `a0_drop()` replaces the six blanket gates.
- The draw renders unless there is no guest VP (fewer than 16 ucode bytes: the fallback VS needs a position array) or the program reads no input (mask 0: identical vertices).
- `RSX_ATTR0_LOG=<n>` prints admitted draws (fp, input mask, constant v0, colour offset) plus power-of-two totals.
- Depth writes go through the unchanged PSO depth key, so a depth-only pass writes when its guest depth test/write is on. This is by code; no GPU fixture covers it (PARTIAL).

**C3 `RSX_COLOR_XFER=<mask>`** (1 gamma, 2 expansion, 4 sRGB output; 7 = all):
- `vp_get_fp_pso` takes the draw's `dr_color_xfer` request, restricted to the units the program fetches.
- The masks and sRGB flag are added to the PSO key.
- Compilation goes through the new non-buffered `rsx_fp_decompile_shadow_color_expand_ex`, then `rsx_fp_apply_srgb_output`. A program text that the sRGB rewrite cannot parse compiles without it and logs `[XFER]`.

**C4 `RSX_RTPOOL_GF=1`:**
- The eviction victim must be unused in both the current replay and the current guest frame (`gf_used`, T100).
- It falls back to the old rule, with a log line, only if every slot was used this frame. No draw is skipped where the old rule would have drawn.

**Cost when off:**
- one branch per draw (C1);
- one call per upload (C2);
- one cached check per draw (C3);
- nothing outside eviction (C4).

Records grow by one u32 per unit (border) and the PSO entry by 33 bytes.

## 4. Deferred, and why

| Item | Reason |
|---|---|
| **D2 mip-chain upload** (largest remaining fidelity gap) | Touches the texture cache's identity and checksum (whole chain), the per-level layout rules (swizzled per level, DXT block rows, linear pitch, the cube pyramid stride already computed), the upload buffer and T102's upload timing. It needs its own fixtures per format. **Plan:** `rsx_texture_layout` gains a per-level offset/size function; `vp_tex` slots get `MipLevels = min(guest, log2)+1`; one `CopyTextureRegion` per subresource; the checksum covers the chain. Until then D1's mip/LOD fields are inert (level 0 only). |
| **Enabling C3 by default** | Whether MotorStorm's loading or race draws request a transfer is unknown offline; T108's `RSX_XFER_LOG` answers it. If they request nothing, C3 changes nothing. |
| **Enabling C1/C2/C4 by default** | Proven against RSX rules and fixtures, but never run on the game. One A/B run decides (§8). |
| D8, D9, D10, D11 | §1; D11 needs T108's runtime verdict first. No arbitrary pass skipping or brightness change was made. |

## 5. Regression fixtures and offline results

**Suite** (`logs/suite_t110.txt`, `tools/run_suite_t110.cmd`): **ps3recomp-t110 28 PASS / 0 SKIP / 0 FAIL.**
- These are the 23 T108 tests plus:
  - `test_t110_pins` (12 pins, 15 source mutations all rejected);
  - `test_sampler_xlate` (2199 checks);
  - `test_attr0_gate` (516);
  - `test_rtpool_victim` (11);
  - `test_t110_warp` (88).
- ps3recomp-t108 on the same runner: its 23 PASS. The 5 T110 tests are absent there (shown as ABSENT/FAIL "no such file").

**WARP fixture** (`libs/video/tests/test_t110_warp.c`; software D3D12, no GPU, no game data):
- **Shaders and samplers:** real decompiler output for hand-assembled TEX programs, `rsx_sampler_xlate.h` samplers, and the backend's layouts. Expected values come from the RSX wrap and filter rules and the sRGB curves.
- **Layout equivalence:** the fixed tables reproduce the static samplers **bit for bit**.
- **Samplers:** guest clamp, wrap, mirror, border and linear on unit 3 and unit 0.
- **Gamma:** dark 10 → 0.003035 (linear segment), midtone, highlight; alpha lane untouched; transfer disabled returns the exact texel.
- **sRGB output:**
  - midtone 128 → 188;
  - gamma + sRGB round trip within ±1;
  - clamps 2.0 → 255 and −0.5 → 0;
  - alpha 0.25 → 64.
- **Blending and multiple units:** the encoded source is blended in gamma space; with two units, gamma on unit 1 leaves unit 2's fetch untouched, and gamma on unit 2 is applied.
- **Shader bindings:** reflection shows t3/s3 in space 0, and PSO creation succeeds with both layouts.
- **Negative control:** a copy with the wrap mapping and sRGB reference broken fails 14 checks.

**Prior pins updated** (each still pins the default as legacy):
- T101 `test_t101_pins.py`: the attr0 and eviction pins follow the new helpers (15/15).
- T107 `test_d3d12_color_xfer.py`: "applies a transfer only under `RSX_COLOR_XFER`; `host_xfer` is `none` unless set".

**TU compiles** (`tools/tu_t110.cmd`, the exact T96I flags):
- `rsx_d3d12_backend.c`, `cellGcmSys.c`, `rsx_commands.c` and `rsx_fp_decompiler.c` all rc=0.
- No new warning classes against T108 (the decompiler was checked against a T108-source compile, `tu_decompiler_t108base.cmd`). The checks were run after each commit.

**Audit:** `audit_public.py --staged` before each of the five commits gives 25 BLOCK, all pre-existing tree files (same as T107/T109). None are T110 files (`logs/audit_c1..c5.log`).

## 6. Changed files

- **New:**
  - `libs/video/rsx_sampler_xlate.h`, `rsx_attr0_gate.h`, `rsx_rtpool_victim.h`;
  - `libs/video/tests/test_sampler_xlate.c`, `test_attr0_gate.c`, `test_rtpool_victim.c`, `test_t110_warp.c`;
  - `tools/test_t110_pins.py`.
- **Modified:**
  - `libs/video/rsx_d3d12_backend.c`;
  - `libs/video/rsx_fp_decompiler.[ch]` (one entry point);
  - `tools/test_t101_pins.py`, `tools/test_d3d12_color_xfer.py`.
- **Edit scripts** (`t110/tools/edit_{samplers,attr0,xfer,rtpool}.py`) replay onto T108's backend byte-identically; that is how the four fixes were committed separately.

## 7. Compatibility with T108, and expected impact

**Compatibility:**
- T110 is T108 `6b1a7e4` plus five linear commits; there is nothing to merge.
- With the switches unset, T108's probe, dumps and logs behave identically. T108's prepared exe and runner were not touched.
- A T108 runtime result therefore transfers directly to T110 arm A.

**Expected impact if enabled (HYPOTHESIS until §8):**

| Fix | Expected effect |
|---|---|
| C1 | unit-0 surfaces filter and tile correctly (largest visible change in textured scenes); clamp/mirror/border edges correct elsewhere |
| C2 | shadow maps and depth pre-pass geometry return |
| C4 | nothing unless the pool fills |
| C3 | changes only draws that ask for a transfer |

None of these is expected to explain a fully **black** race on its own. That remains T108's A–D question.

## 8. Runtime validation procedure (needs explicit authorization; nothing run)

1. **Build:**
   - `generated\analysis\t110\configure_t110.cmd` is T108's configure with `PS3RECOMP_DIR=ps3recomp-t110` and `build\motorstorm-t110`;
   - then `build_t110.cmd`.
2. **Pin:**
   - `py -3 generated\analysis\t110\run_t110.py prepare A` copies the exe and prints its SHA256;
   - set `EXE_SHA`;
   - rerun `prepare A`, then `prepare B` … `prepare D`. Each arm gets fresh hash-verified `hdd0_X`/`hdd1_X` copies.
   - `preflight` refuses while `EXE_SHA` is unpinned (checked: `dryrun B` prints `PREFLIGHT FAIL: EXE_SHA not pinned`).
3. **Run** `dryrun <arm>`, then `launch <arm>`, for arms A, B, C, D (E only if arm A logs `[XFER]` requests in the frames being compared):
   - same original CROSS-press race entry, intro skip, 300 s session / 310 s host cap, no `--target`;
   - T108's probes: `RACE_PRESENT_PROBE` on real Presents with guest-frame ids, presenting-only `CELLMARK_DUMP` at the guest 1280×720, `PS3_PRESENT_DIAG`, `RTPOOL_LOG`, `RSX_XFER_LOG`.
   - The controller also timestamps `[samplers]`, `[attr0]` and pool lines.
4. **Compare, frame by frame** (same guest-frame ids or the same loading-screen page; presenting dumps only):

   | Question | Read | Pass |
   |---|---|---|
   | Race geometry visible | probe verdicts A–D (T108 §6), arm A vs B–D | the same or later stage than A; never a new black stage |
   | Depth-only draws restored | `position_attrib_disabled` count (A) vs `[attr0] admitted` (C) | the drop count falls by the admitted count; `RACE_PRESENT_PROBE` scene non-black; no new `dropped_draw` reasons |
   | Sampling | B vs A dumps of the same frame; RSXI `host_sampler` | unit-0 surfaces filtered and tiled; no new seams; `[samplers]` reports no heap-full line |
   | Brightness / clipping | loading-screen page in A vs E (T107 `gain_ratio.py`, `bc3_linearity.py`) | only if E applies: texel 128 at gain 1.561 → 157, and the clipped fraction falls from 92/256 to 46/256 |
   | Transparency, bloom, exposure | composite-stage probe lines; blend-heavy UI frames | unchanged from A unless D4/D11 apply; never darker or brighter by a global factor |
   | Sharpness | 1:1 crop of the same frame | B ≥ A on magnified unit-0 surfaces; distant aliasing unchanged (D2 is still open) |
   | Validity | crashes, `[fc-watchdog]`, new REFUSED | none in any arm |

5. **Reference:** the original game's assets and code are the reference (PSARC textures decoded offline for colour; the guest state recorded by RSXI for semantics). No PCSX2/RPCS3 trajectory match is required, and no pixel-exact claim will be made without a hardware capture.

## Tools and logs (`generated/analysis/t110/`)

- **Tools:**
  - `tools/edit_*.py`, `make_tu.py` → `tu_t110.cmd`;
  - `tu_decompiler_t108base.cmd`, `run_suite_t110.py/.cmd`, `build_warp.cmd`;
  - `make_runner.py` → `run_t110.py`, `pb_stall_t110.cfg`, `configure_t110.cmd`, `build_t110.cmd`.
- **Logs:** `logs/suite_t110.txt`, `logs/suite/`, `logs/tu/`, `logs/audit_c1..c5.log`.
- **Scratch:** `scratch/t110/` holds the byte-identity replay and the negative-control WARP copy.
