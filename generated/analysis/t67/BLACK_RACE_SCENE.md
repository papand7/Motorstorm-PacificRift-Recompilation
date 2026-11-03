# T67: black race scene — RSX/D3D12 investigation (offline)

2026-10-26. Offline only:
- No game launch, no build, and no code change.
- No shared worktree touched: `ps3recomp-t62` was read only.
- Nothing merged or pushed.

**Inputs:**
- RSXI frame 4985 of `generated/runs/20261026-140153-t64c-loadrace-stall` (exe `162afb4a…`; source `ps3recomp-t62` @ `c529ab0`);
- the T64C `stderr.log` and `performance.json`;
- the garage capture `20261025-102805-garage-capture-probe` f001854 for comparison.

**Tools and outputs in `t67/`:**
- `passes.py` (pass reconstruction);
- `passes_f4985.txt`;
- `snaps/` (converted snapshots).

## Result: **PARTIAL**

- **Located (VERIFIED):** the first draws where image content is lost.
- **Root cause:** not proven offline. No code correction was made, because the evidence does not prove a cause.
- **Needed next:** one targeted runtime diagnostic (§7).

## 1. Render-pass reconstruction, frame 4985 (VERIFIED)

267 records: 256 draws and 11 clears. There were no drops: no `batch full`, the vertex buffer was not full, and `dropped_events` = 0.

| ops | target (guest) | what | evidence |
|---|---|---|---|
| 0–2 | `0x0B030000` 1024×2048 (shadow) | depth/stencil clears only, **0 draws** | garage f1854: 198 shadow draws here |
| 3 | `0x00ED0000` (scene zeta) | depth+stencil clear (mask 0x3), 0 draws | |
| 4 | `0x01650000` | colour clear to 0 | |
| **5–196** | `0x07B78D80` 640×480, fmt 0x148, zeta = itself (engine idiom for "no depth"), depth off, **cull FRONT** | **192 draws, 45,983 prims**: 12 terrain (vs `CEED7030`/fp `07A9CEC1`) plus 180 objects | **Planar water reflection.** VP view rows c13 and c16–18 are Y-negated relative to the scene pass, and the camera Y is −43.4 against −10.5. Snapshot shows mirrored terrain and sky (`snaps/snap16.png`). |
| **197–208** | **`0x00750000` 1280×720 2×AA (0x3148) + MRT `0x01650000`**, zeta `0xED0000`, depth test LEQUAL / write off, cull BACK, vp 1274×716 | the **same 12 terrain draws** (same vs/fp, same vertex counts 645/687/…) | main scene pass |
| 209–225 | `0x0B830000` / `0x0BA10000` 640×360 | depth-from-zeta copy (op 210, ALWAYS), 12 draws fp `02B9EC81`, a fullscreen pass | |
| 226 | `0x0243AB00` | clear (0.5, 1, 0.5) | |
| **227–239** | `0x00750000` (no MRT), depth LEQUAL/off, **stencil test on (func 0x205, ref/mask 128)** | 13 draws, fp `022CD841`/`02B9EF81` (**water**: refraction samples `0x750000` on t2 by screen position) | RSXI `rt_feedback` (high) |
| 240–245 | `0x02195900` 320×180 → … → `0x022C1600` 10×5 | luminance downsample **of MRT1 `0x01650000`** | |
| 246–247 | `0x01650000` | fullscreen fp `0074CE81` (reads zeta-as-colour and itself) | |
| 248–263 | 8×8, 320×180 ×3, `0x01DD0000` 1280×720 (op 253 composite of `0x750000`), 16×16, 640×360, 320×180, 160×90, 80×45 | exposure, bloom, composite | |
| 264–266 | backbuffer | final composite plus the HUD ("Press ⊗ to Skip") | |

**Compared with the garage:**
- In the garage, the shadow pass has 198 draws and the scene pass into `0x750000` has 311 draws.
- In the race, the shadow pass has **0** draws and the scene pass has **12 + 13** draws. The 180 object draws appear **only** in the reflection pass.

## 2. Surface `0x00750000` and the feedback warning

- **Format:** 1280×720 colour with 2×AA, fmt `0x3148` (AA field = 3). The host target is single-sample 1280×720 RGBA8; its later texture reads ask for 2548×716.
  - The 2×AA layout is still unmodelled (known item, `RSX_DRAW_REJECTION_AUDIT.md`). It does not explain the frame being all zero.
- **The feedback (op 227, unit t2):** a **legitimate RSX pattern.** The water shader computes `uv = position.xy × (1/1274, −1/716) + …` and samples the scene below the water for refraction.
  - On RSX this reads framebuffer memory, without coherence guarantees.
  - In the D3D12 backend it is a **hazard**:
    - **VERIFIED:** `rsx_d3d12_backend.c` ≈7008 skips the PSR transition for a sampled RT that is also bound, so the resource stays in `RENDER_TARGET` state while the draw runs.
    - **Inferred, not traced:** that the draw's SRV for t2 is that same resource. If so, the read is undefined in D3D12.
  - A correct model is a copy of the bound target taken before the sampling draw.
- **Not an alias error:** `0x750000` is matched as `rt_exact` to the right slot.
  - Separately, lookup textures at `0x00779580`/`0x0077B080`/`0x0077B400`/`0x00960C80` fall inside `0x750000`'s guest span (RSXI `rt_alias`, resolved as uploads).
  - RT keys ignore the memory location (local vs main). Possibly they are main-memory textures (HYPOTHESIS; the terrain fp samples t11/t12 from them).

## 3. First draw where expected content is lost (VERIFIED)

**Ops 197–208**: the 12 terrain draws into `0x750000` + MRT `0x01650000`.

- **Snapshots:** `0x750000` and `0x01650000` are **exactly zero** (max 0) at the end of the frame.
- **The water pass does not explain it.**
  - The luminance chain op 240 reads MRT1 `0x01650000` before op 247 overwrites it.
  - Its output `0x02195900` is all zero.
  - Water draws 227–239 have no MRT.
  - So the terrain draws left **MRT1 at zero** before any water or feedback draw ran.
- **The same 12 draws produce visible terrain** in the reflection target (ops 5–16). They use the same vertex program, fragment program, textures and fp constants. Their colour is `texture × lighting × tc6.y`, and MRT1 = colour/16.
- **Everything downstream is consistently black:** exposure, bloom and the composite op 253 (`0x01DD0000`), then the backbuffer. The black final image is the scene pass's empty output passed along.
- **Intentional black (unskipped cinematic)?** Not supported. The game draws terrain with a valid camera into the scene target, and the reflection and HUD are live. A fade would act at composite time, but `0x750000` is already zero.

## 4. Differences between the working and the failing terrain draws (VERIFIED from records)

| | reflection (works) | scene (black) |
|---|---|---|
| depth | test **off** | test **on**, LEQUAL, write off, zeta `0xED0000` (cleared at op 3; value not logged) |
| cull / winding | FRONT, mirrored view | BACK, normal view. Consistent: a mirror flips winding, so culling alone cannot reject one pass and keep the other. |
| targets | 1 × RGBA8 640×480 | 2 × RGBA8 (MRT) 1280×720, guest 2×AA |
| VP constants | mirrored view | normal view (c13, c15–19, c32, c36 differ). `tc6.y` is VP-computed. |

**Verified RSX-semantics deviation in the same code path** (`rsx_d3d12_backend.c:2632-2641`, guest-FP PSO). When the guest enables the depth test, the PSO always uses `DepthWriteMask=ALL` and `DepthFunc=LESS_EQUAL`, and `StencilEnable=FALSE`. So:
- the guest's write-off is ignored;
- any guest depth function other than LEQUAL is ignored;
- all guest stencil is ignored.

For ops 197–208 (LEQUAL, write off) this alone cannot zero the target; it would leave the nearest terrain visible. For ops 227–239 it removes the stencil mask, so the water draws write where the original would not.

## 5. Root cause

**Not established.** Ranked candidates for ops 197–208 writing nothing (HYPOTHESIS):

1. **Every fragment fails the depth test.** This happens if the op-3 clear value (`ZSTENCIL_CLEAR_VALUE`, not logged) is not ≥ fragment z, or if `0xED0000` holds data the game expects a z-prepass to have written.
   - The race frame has **no** z-prepass and **no** shadow draws. The garage has a shadow pass.
   - This is the only state difference that can reject whole draws.
2. **Fragments are written as 0.** `tc6.y`, or the lighting term, evaluates to 0 with the normal-view constants. That needs the VP evaluated on real vertex data.
3. **The MRT / 2×AA target setup** (two RTVs, 1274×716 viewport on a 1280×720 resource) rejects or discards output.

The missing shadow-pass and object draws (180 object draws only in the reflection) may share a cause upstream of the backend, such as SPU-built command lists or the visibility system. That is not established either.

## 6. Correction

**None made.** Offline evidence does not prove which candidate is responsible.

These are VERIFIED defects in the code, each deserving its own focused fix and test, but not proven to cause the black image:
- **(a)** honour the guest depth write mask, depth function and stencil state in `vp_get_fp_pso` (and the PSO key);
- **(b)** copy-on-feedback for a sampled render target that is also bound.

Mixing them in now would change several variables at once.

## 7. Runtime validation needed: yes (one bounded run)

Same exe and path as T64C. The race intro is reached about 154 s after launch, so it fits within the 205 s cap. No new code; existing diagnostics only:

- `RSXI_SNAP=passes` on a race frame (`RSXI_MINDRAWS=250`): snapshots after op 208 and after op 239 separate the terrain loss from the water overwrite.
- `RT_CLEARDBG=2` (magenta on bind): if `0x750000` comes out magenta, the draws were rejected (depth or rasterization); if black, the shader wrote 0.
- `PS3_DRAW_ACCT_MS=5000`: confirms that no draws are dropped in race frames.

Decision:
- **magenta after op 208:** next run `DEPTH_OFF=1` (diagnostic only), and log `ZSTENCIL_CLEAR_VALUE`. A one-line log needs a build.
- **black after op 208:** evaluate the VP output `tc6.y` (`RSXI_VP_CONSTS=512` plus geometry capture).

## 8. 5 fps race state: first assessment (offline; no optimisation mixed in)

- **Guest-bound, not presentation-bound.** Guest flips and host frames both run at about 5 per second (heartbeat 4733 → 4986 over 153–205 s).
- **CPU:** the process uses about 2.2 cores. One host thread (TID 19848, first seen in the race) uses about 0.8 core and is near saturation. Kernel time is about 0.7 core.
- **SPU work:** dispatches rise from about 0.6 to **124 per second** in the race state (about 25 per frame). The run had **WWS AOT off**, so Wws job modules run without AOT.
- **Likely limiter:** SPU job execution, physics and vehicle jobs, on a single host thread (HYPOTHESIS).
- **Backend:** each frame expands about 87k vertices on the CPU and converts zeta-as-colour about 4 times. This is secondary.
- **Next:** a per-thread profile (`PS3_SCBLOCK_PROF`, SPU dispatch timing) in a later run, kept separate from the rendering fix.

## 9. Remaining uncertainties

- The depth clear value, and whether a z-prepass exists in the guest command stream (no `cmd_offset` in RSXI).
- Why the race frame has no shadow-pass draws and only 12+13 scene draws.
- The 2×AA layout, and the memory location of the lookup textures inside `0x750000`'s span.
- The identity of host thread 19848.
