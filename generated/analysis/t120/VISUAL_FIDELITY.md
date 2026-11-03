# T120: visual fidelity and rendering correctness

Offline only: no game build, no launch, no merge, no push. Labels: VERIFIED, PARTIAL, HYPOTHESIS.

## 1. Base and branch

- Worktree `ps3recomp-t120`, branch `agent/t120-visual-fidelity`, based on T113 `2562ba8`.
  - `2562ba8` is the FP span fix. Below it: `40d1ccf` (RSXI MRT pass snapshots) and `74fd084`.
- Commits:
  - `235b3e6`: render-target sampling windows;
  - `169e618`: guest depth/stencil state, windows without a GPU wait, zeta-as-colour windows.
- The T113 FP-span fix is untouched (`rsx_fp_span.h`; there is no fixed 4096-byte read).
- T115B, T116, T117, T119 and T122 were not merged. No other agent's worktree was modified.

## 2. Renderer architecture (as relevant here)

**Recording and replay.** The guest RSX FIFO is decoded into `rsx_state` (`rsx_commands.c`). Each draw is recorded into a `D3D12DrawRecord`, which holds the guest state at draw time. `render_frame` then replays the records:
- a zeta pre-pass;
- an SRV fill, which resolves each texture unit to an upload, an offscreen RT (`rt_exact`), a depth surface (`zeta` / `zeta_as_color`) or a null SRV;
- per-draw PSO lookup (`vp_get_fp_pso`, keyed on the FP ucode hash, VS, blend, nrt, format, cmask, cull, depth key, cube/shadow/colour-transfer).

**Resources.**
- Offscreen RTs are host resources at the guest surface clip size, one value per pixel.
- Zeta surfaces are D24S8 resources. A zeta read as colour uses a separate A8R8G8B8 image (`cres`), rebuilt by a conversion pass.

**Evidence sources.**
- T113 captures G (frame f006314, the shore program still truncated) and I (fix on: f006502/f006527, plus a dumped shader directory).
- RSXI `events.jsonl`, read leniently because of bare `nan`: `t113/tools/ev.py`.
- Pass and end BMP snapshots, read with `t120/rsxbmp.py`.

## 3. Visual defect inventory

| # | Symptom | RSX state / resources | Evidence | Cause | Status |
|---|---|---|---|---|---|
| 1 | ~16 px streaked right-edge column; 9 bottom rows | scene targets 1280x720 sampled as 1264x711 windows (`0x00750000`, `0x01650000` as 2528x711 under AA-2; `0x01DD0000` as 1264x711) | G f006314, §4 | the whole host resource is bound, so u = 1 lands on column 1280 | VERIFIED cause; fixed opt-in (`RSX_RT_WINDOW=1`); not runtime-verified |
| 2 | Depth-based effects misregistered by 1264/1280 | zeta `0x00ED0000` read as 2528x711 / 2524x710 A8R8G8B8 (shore draws `fp_07200641`, velocity pass `fp_0074CE81`, op 466) | G, I | same as #1, on `cres` | VERIFIED mismatch; fixed opt-in (`RSX_RT_WINDOW=1`, `169e618`) |
| 3 | Transparent draws write depth; later transparent and water draws behind them are rejected | 36 draws per race frame with depth test on, write off (blended 484-497 shore/water, 453-460, 532-537) | G, I tally (`t120/tools/state_tally.py`) | the guest-FP PSO always had `DepthWriteMask = ALL` | VERIFIED code + state; fixed opt-in (`RSX_DEPTH_STATE=1`); visible effect not observed |
| 4 | A pass that should overwrite is depth-rejected | op 466 (`fp_0B027F41`, 640x360): depth func ALWAYS with writes | G, I | the PSO always used `LESS_EQUAL` | VERIFIED; fixed opt-in |
| 5 | Stencil-masked passes apply everywhere | 442 draws tag stencil (ALWAYS, refs 0/64/255); op 483/594 test NOTEQUAL 128 (mask 128); the velocity pass (op 538/651) tests NOTEQUAL 255 | G, I | `StencilEnable = FALSE`; the write mask and back-face registers were not decoded | VERIFIED; fixed opt-in. The ops behind the tags were not captured (the RSXI record now has `ds_key`) |
| 6 | Shore and velocity passes test against the wrong depth | `fp_07200641` (2 draws, depth test on) and `fp_0074CE81` (stencil) read their own bound zeta as colour | I | the hazard check swapped in the shared depth buffer (cleared on bind) although the read goes to `cres` | VERIFIED; fixed opt-in (`RSX_DEPTH_STATE=1`) |
| 7 | Window copies would stall the GPU every frame | the scene size is dynamic: 1259..1265 x 708..712 across frames 6264..6527 | G, I and other T113 captures | `235b3e6` called `wait_for_gpu` on every size change | VERIFIED; fixed in `169e618` (retire after FRAME_COUNT+1 presents) |
| 8 | MRT targets B..D blend/mask like target A | `COLOR_MASK_MRT` 0x0370 and `BLEND_ENABLE_MRT` 0x036C were not decoded for D3D12; blended MRT draws 484-489 write MRT1 (the luminance source) | code | the PSO mirrors RT0 | HYPOTHESIS for visible effect. The values are now recorded (`mrt_regs`); honouring them waits for a capture showing them, because the semantics of a never-written register are unknown |
| 9 | Scissor ignored | the replay uses the viewport rect as scissor | code; G/I: scissor = viewport on every draw | none in the race | VERIFIED no race impact; open in general |
| 10 | NaN tests folded | fxc folds `x != x` even with IEEE strictness; `fp_0074C781`'s NaN guard is dead | `t113/fxc/` | compiler | VERIFIED offline; no known visible defect |
| 11 | Surf band very bright | recovered shore draws (T113) | T113 arm I frames | possibly #3/#6 (writes, wrong depth buffer) or genuine | PARTIAL; no native reference |
| 12 | Lighting, shadows, particles, water reflection, texture filtering, gamma | not audited at pixel level in this pass | none | none | open (§7, §8, §10) |

## 4. Right-edge artifact: root cause (VERIFIED from captured RSX state)

Path traced: guest surface → pitch/format → host allocation → viewport → scissor → shader coordinates → texture sampling → copies → presentation.

| Surface | Guest surface | Viewport | Guest samples it as | Host |
|---|---|---|---|---|
| `0x00750000` scene, `0x01650000` MRT1 | 1280x720, pitch 10240, format `0x3148` (antialias 3 = 2 samples side by side) | 1264x711 | 2528x711, pitch 10240 = 1264x711 px | 1280x720, 1 value/px |
| `0x01DD0000` resolved | 1280x720, pitch 5120 | 1264x711 | 1264x711 | 1280x720 |
| `0x00ED0000` zeta | as scene | — | 2528x711 A8R8G8B8 | 1280x720 D24S8 (+ `cres`) |

**Correct stages:** allocation, pitch, viewport, scissor (equal to the viewport), copies and presentation.

**Wrong stage:** the texture binding. On RSX a texture's normalised (1,1) is its own declared last texel. The backend bound the whole 1280x720 resource, so every pass stretched the scene by 1280/1264 and read columns 1264-1279, which no draw writes (stale content). The right 160 columns of the scene pass vs the presented backbuffer are in `t120/G_f006314_right160_scene_vs_bb.png`.

**Visible-path passes:**
- op 544 `fp_0074B441` (`0x00750000` → `0x01DD0000`): destination columns ≥ ~1248 read never-drawn texels;
- op 555 `fp_02193941` (`0x01DD0000` → backbuffer): reads `0x01DD0000`'s own never-drawn columns.

**Backbuffer metric** (left-neighbour repetition): ~0.9 in the interior, 0.6-0.7 at x ≥ 1250, 0.00-0.02 at x 1270-1274.

**The 1264x711 vs 1280x720 hypothesis is VERIFIED:** it is a sampling-window mismatch. The size is not fixed at 1264x711; it varies per frame (#7).

## 5. Shader correctness

- **VERIFIED (arm I):** both post-fix race frames bind the guest FP pipeline for every draw (665 and 917 draws, 0 fallbacks; `t120/tools/pso_tally.py`). In G, `fp_07200641` fell back on 2 draws per frame.
- **VERIFIED:** none of the 183 race fragment programs dumped in arm I (`t113/runtime-I-*/rsxi/shaders`) contains an unhandled-opcode marker or a skipped CAL/RET (`rsx_fp_decompiler.c` emits `/* TODO: ... */` for both).
- **Preserved:** the T113 span handling (END-based, 64 KiB bound). T117's 16 KiB window (`fd97181`) overlaps it and must be reconciled before integration, without returning to 4096.
- **Not done:** an instruction-level semantic audit (modifiers, predicates, precision) against the RSX ucode. That needs a reference interpreter, and no shader-level defect was found from the captures. The NaN folding is item #10.

## 6. Alpha blending and depth

**Blend.** The RT0 blend key (factors, equations, separate alpha) maps 1:1; `test_d3d12_blend_state` passes. MRT B..D: item #8.

**Depth/stencil.** `169e618`, `RSX_DEPTH_STATE=1`:
- `rsx_ds_key` packs:
  - depth: test, write, compare;
  - stencil: test, compare, fail/zfail/zpass, read/write masks;
  - two-sided back-face compare and ops.
- `rsx_ds_apply` builds the D3D12 desc, and the replay calls `OMSetStencilRef`.
- `rsx_commands` now decodes `SET_STENCIL_MASK` (0x032C), `TWO_SIDED` (0x0348) and `BACK_*` (0x034C-0x0364).
- D3D12 has one reference and one pair of masks for both faces. A two-sided state whose back ref or masks differ uses the front values and logs `[ds]` (first 4).
- A zeta that a draw reads only as colour stays bound as its depth target. Its `cres` is rebuilt from the depth so far, then the zeta returns to DEPTH_WRITE. A draw that can write the bound zeta marks `cres` stale.
- With the switch unset, pipelines and bindings are identical to before.

**Draw order.** Unchanged; transparent draws are not reordered.

## 7. Lighting and shadows

- The shadow map (`0x0B030000`, 1024x2048 D24, sampled as `zeta` with a compare, 583 samples per frame) is read at its exact declared size, so there is no window mismatch (VERIFIED, arm I).
- Shadow placement, acne and lighting constants were not compared at pixel level; there is no native reference capture. Open.
- Stencil tags (#5) are likely material/object masks used by later passes (velocity; refs 64/128/255). The visible effect on lighting is HYPOTHESIS until the A/B.

## 8. Water and particles

- The T113 shoreline correction is intact (`fp_span`).
- The surf band's semantics are PARTIAL. Its two draws:
  - test depth without writing, and
  - sample the scene depth as colour (depth fade).
- Before `169e618` both behaved wrongly: they wrote depth, tested against the shared buffer, and read a 1280/1264-stretched depth. With `RSX_DEPTH_STATE=1` plus `RSX_RT_WINDOW=1` all three follow the guest state. Whether the band's brightness changes is for the A/B to show.
- The fixes are generic RSX semantics; nothing is shoreline-specific.
- Particles (dust, smoke, spray) were not separately audited. The blended non-writing draws in #3 include them if they are in that set; the A/B pass snapshots will show it.

## 9. Post-processing

**Chain (G/I):**
1. scene `0x00750000` + MRT1 `0x01650000`;
2. op 502 `fp_0074B181` luminance (320x180 → ... → 10x5) → `0x07EBA600`;
3. exposure (`c33.x`; T113 arm I 0.95-1.11);
4. op 538/651 velocity (`fp_0074CE81`, stencil NOTEQUAL 255, reads zeta as colour);
5. op 544 resolve → `0x01DD0000`;
6. op 555 composite → backbuffer;
7. bloom at 640x360 (op 466 family).

**Notes:**
- T113's exposure fix remains valid. The luminance source MRT1 gets its shoreline content again. Item #8 can affect MRT1's blend; whether it does is HYPOTHESIS until `mrt_regs` is captured.
- No pass is dropped (0 fallbacks). No post effect is disabled.

## 10. Texture and colour correctness

- Render-to-texture feedback is preserved. A window is refreshed from its target whenever the target was written since the last copy (the generation is bumped on every entry into RENDER_TARGET or COPY_DEST, and per `cres` rebuild).
- Texture cache, invalidation and T115/T115B mip/BC/cube work are not touched.
- No gamma, exposure or colour change was made.

## 11. Implemented fixes

| Commit | Switch | What |
|---|---|---|
| `235b3e6` | `RSX_RT_WINDOW=1` | an offscreen RT sampled through a declared sub-rectangle is bound as a box-copied window of that size (`rsx_rt_window.h`) |
| `169e618` | `RSX_RT_WINDOW=1` | resized windows are retired instead of waited for; zeta-as-colour windows |
| `169e618` | `RSX_DEPTH_STATE=1` | guest depth write mask, compare and stencil in guest-FP pipelines; a zeta read only as colour stays bound; stencil write mask and back-face decode |
| `169e618` | none (record only) | RSXI `ds_key`, `mrt_regs` (COLOR_MASK_MRT, BLEND_ENABLE_MRT, written bits), `window` on depth reads |

Both switches stay opt-in until the runtime A/B. With them unset the backend behaves exactly as `2562ba8`.

## 12. Tests and evidence

**WARP tests:**
- `libs/video/tests/test_t120_rt_window.c` (WARP; real decompiled `TEX R0, TC0`), 21 checks:
  - rules: AA-2, 4x AA, odd sizes, the dynamic 1261x709 / 1265x712 sizes, zeta 2524x710 with unknown pitch, rejections;
  - pixels: the old binding reproduces the streak (4/20 columns never drawn); the window matches RSX texels exactly (point) and clamps at its own edge (linear).
- `libs/video/tests/test_t120_depth_state.c` (WARP + D3D12 debug layer, 0 errors), 40 checks:
  - GL → D3D12 compare and stencil-op enums, against `d3d12.h` names;
  - pixels: writes off, ALWAYS, stencil tag + NOTEQUAL, write mask, two-sided.
  - The expected pixels come from the scene geometry, not from a second implementation. Each case also runs the old pipeline, which reproduces the defect.

**Decode and pins:**
- `libs/video/tests/test_t120_rsx_state_decode.c`, 8 checks: `rsx_commands` decode of 0x032C, 0x0348-0x0364, 0x036C/0x0370 and their reset values, through `rsx_ds_key`.
- Pins:
  - `tools/test_rt_window.py`: 8, including no `wait_for_gpu` in `win_get` and zeta windows;
  - `tools/test_depth_state.py`: 5;
  - `tools/test_d3d12_depth_state.py`: harness stubs for the new symbols, legacy behaviour unchanged.

**Runs:**
- Suite `t120/tools/run_suite_t120.cmd ps3recomp-t120`: **34/34 PASS**, with no inherited failures in this tree. Logs: `t120/logs/suite/`.
- TU compile: 0 errors. New lines carry only warning classes the file already has (`-Wunsafe-buffer-usage`, `-Wpadded`, `-Wdeclaration-after-statement`, `-Wdeprecated-declarations`).
- Audit `--staged`: only the 25 inherited BLOCKs (`t120/logs/audit_staged_2.log`), the same list as before.

**Capture tools:** `t120/tools/state_tally.py`, `op_detail.py`, `pso_tally.py`, `edge.py`.

## 13. Performance impact (estimated; to be measured in the A/B)

**`RSX_RT_WINDOW`:**
- One box copy per (target, write generation) sampled through a window: about 3-4 copies of ~1264x711 per race frame (scene, MRT1, resolved, zeta colour).
- One `CreateCommittedResource` per target when the size changes, which is nearly every frame (#7). Retired windows are held for FRAME_COUNT+1 presents; there is no GPU wait unless 64 are pending.
- A possible later optimisation for T119/T122: a per-target cache of a few sizes.

**`RSX_DEPTH_STATE`:**
- More distinct PSO keys (depth write/compare/stencil per draw class): a handful of extra pipelines, compiled once.
- One extra `cres` rebuild when a draw reads the bound zeta as colour after depth writes (the shore and velocity passes).
- No new per-draw `getenv`: both switches are read once into a static.

## 14. Integration dependencies

- **T115B** (`65d2695`): edits `render_frame` and `srv_write_ex`. Textual conflicts are expected near the SRV fill (the window and zeta-as-colour branches).
- **T116** (`30b817b`, PSO cache): the PSO key `depth` is now `u64` (`rsx_ds_key`). A persistent cache key must include it.
- **T117** (`fd97181`): reconcile with `rsx_fp_span`; never return to 4096.
- **T119:** no shared lines. The window copy cost feeds into its measurements.
- **T122** (barriers/resource lifetime):
  - `169e618` adds transitions: window copies, and the bound zeta going DEPTH_WRITE → read → DEPTH_WRITE around a `cres` rebuild;
  - it adds a deferred-release list (`s_rtwin_grave`, FRAME_COUNT+1 presents).
  T122 should take both over or review them.
- **Framework:** `rsx_commands.h/.c` gain fields and methods used by every backend. Vulkan/Metal are unaffected, since they don't read the new fields.

## 15. Remaining defects

- **Not runtime-verified:** #1-#7 are fixed in code and in synthetic GPU tests only.
- **#8 MRT blend/mask:** needs the `mrt_regs` values from a capture, then an opt-in PSO change.
- **#5 stencil ops:** the captures predate `ds_key`, so the tag ops (REPLACE?) are not yet observed. The A/B's RSXI will show them.
- **Scissor:** the guest scissor is not applied as a scissor (no race impact).
- **Depth surfaces read as depth with a declared sub-window:** not windowed. D3D12 cannot box-copy depth; none in the race.
- **Not audited:** lighting/material constants, shadow placement, particles, filtering/anisotropy, gamma/presentation at pixel level. No native PS3 reference exists in this project, so no parity claim is made.

## 16. Runtime validation plan (needs authorization: build of `169e618` + launches)

**Setup.** Same route and capture time; T113 runner pattern (`t113/run_t113.py`):
- fresh HDD copies, window visible;
- reject `0x087A0001` with frozen `present_success`;
- RSXI from 199 s with `passes`, `RSXI_RTS=00750000,01650000,01DD0000,02195900,07EBA600`;
- `CELLMARK_DUMP` 60 every 10;
- `RSX_VPC_WATCH=33`.

**Arms:**

| Arm | Exe | Switches |
|---|---|---|
| A | `169e618` | none (= T113 behaviour) |
| B | `169e618` | `RSX_RT_WINDOW=1` |
| C | `169e618` | `RSX_DEPTH_STATE=1` |
| D | `169e618` | both |

**Pass criteria:**
- B/D: right-edge metric at x ≥ 1248 equal to the interior (~0.9); `[rtwin]` lines for `0x00750000`/`0x01650000` (aa=3), `0x01DD0000` and `0x00ED0000`.
- C/D:
  - `ds_key` present;
  - the velocity pass is stencil-masked;
  - the shore draws bind zeta `0x00ED0000` (RSXI `bind_rt`), not the shared buffer;
  - `[d3d12] op … samples zeta … while writing it` no longer printed for them.
- All arms:
  - `c33.x` over 180-240 s within 0.93-1.11;
  - 0 `compile FAIL`;
  - shoreline black px ≤ 22;
  - no debug-layer errors (a separate debug-layer run);
  - frame time within noise of A, or the cost recorded.
- Read `mrt_regs` from the C/D captures to decide #8.

**Limitation.** The race intro camera is scripted, but dynamic resolution and timing differ between runs. So compare per-frame metrics, not exact pixels.

## 17. Local commits

- `235b3e6` D3D12: sample only the part of a render target a guest texture covers (`RSX_RT_WINDOW=1`)
- `169e618` D3D12: guest depth/stencil state in guest-FP pipelines (`RSX_DEPTH_STATE=1`); RT windows without a GPU wait

**Fixed vs unverified.** Fixed in code with deterministic GPU tests: the right-edge window mismatch (colour and zeta-as-colour), the per-frame stall that mismatch fix introduced, and the depth write/compare/stencil state and wrong depth binding for draws that read their own zeta. Unverified: all of it at runtime (no launch authorized), MRT blend/mask, and any claim of PS3 visual parity.
