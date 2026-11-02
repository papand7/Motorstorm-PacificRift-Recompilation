# T178: dark terrain squares

Status: **PARTIAL. The squares are not fixed.** The defect is narrowed to the box draws of one fragment program, and those draws' shader translation is ruled out. No root cause is established, so no renderer fix was made. One bounded capture will decide between the remaining causes. No game was launched.

## 1. Baseline

- VERIFIED: the squares first appear in intermediate target `0x00750000`, written by box draws (T172 "class 2"; T171 TA `f005564`, snapshot 04 at op 1887 to snapshot 05 at op 1899, 12 box draws). They survive into the final image (T169 VA and VB frames).
- VERIFIED: per-pixel, the box darkening is flat with 1-pixel hard silhouette edges. Measured on the L channel of the TA pair: about 34 %, about 5 % and about 1 %; where squares overlap, 37 % = 1 − 0.66 × 0.95. T172's RGB fit gave about 0.26 for the same squares.
- VERIFIED: a large near box in the same frame shows a smooth gradient, so the same shader, sampling and UV path can work.
- Config in that capture: T171 TA run (T171 runner pin `4450ea1f...`), `samplers=0xF zeta_exact=1 depth_state=0`.
- HYPOTHESIS: the squares sit over the start grid. Boxes come in a pair per racer, about 6 units apart.

## 2. Hypotheses and evidence

| Hypothesis | Evidence | Result |
|---|---|---|
| FP/VP translation wrong | Real private HLSL replayed on WARP with T165 B1 constants against an analytic reference (`tools/box_replay_t178.py`): p99 ≤ 0.0017, max 0.0022 on ops 911, 912, 913 | Ruled out, given correct inputs (VERIFIED) |
| Depth reconstruction formula wrong | c260-263 is the exact inverse of c256-259 (I×M ≈ identity); host viewport Z matches the shader's assumption; zeta byte order correct by source | Ruled out (VERIFIED) |
| Swizzled B8 decode wrong | `test_t178_boxdiag.py`: 8×8 and 16×16 against a Morton reference | Ruled out (VERIFIED) |
| Wrap instead of clamp | Some captures show `linear_wrap`, but TA, VA and VB showed squares with samplers=0xF | Ruled out as the cause (VERIFIED) |
| Mips, remap | One level, non-mip filter; remap 0xA9FF correct | Ruled out (VERIFIED) |
| WPOS, RT reinterpretation, feedback | T172 | Ruled out (VERIFIED) |
| Polygon offset | Box draws are stencil-marked volumes with depth GREATER and no write; flat alpha is not a depth-fight pattern | Not supported; not assumed |
| Unit 1 content flat, stale or wrong | Replay with a flat texture gives flat alpha (control: byte 168 gives 0.341). Host bytes never captured | **Open** |
| Wrong zeta values with a non-transparent texture rim | Far boxes are very depth-sensitive: u spans about the full range for d .9953-.9963 | **Open** |
| Missing depth bounds test | D3D12 backend ignores it (Vulkan applies it). ELF scan found no method word, but that scan is weak | **Open** |
| Real PS3 appearance | No reference exists | **Open** |

Leading candidate (HYPOTHESIS): the dark squares are the unit boxes using 8×8 texture `0x0A142300`. This is inferred from silhouette size, because TA has no constants. Surrounding about 5 % quads would be vehicle boxes.

## 3. Root cause

**Not established.** Correct shader output with flat alpha means the inputs are wrong or the appearance is real.

## 4. Draws, shaders, state

- FP `0x022C20C1` (code hash `0xD84095FF`), VP `0xC163B50D`, unit cube, target `0x00750000`, zeta `0x00ED0000`.
- Guest state: depth GREATER, no write; stencil NOTEQUAL with a per-box ref; cull front; blend key `0x0122418B`.
- Unit 0: zeta read as A8R8G8B8. Unit 1: B8 (`0x81`) swizzled, clamp to edge, linear, 1 level. Alpha = 1 − unit 1 byte.
- Textures: vehicle boxes 16×16 `0x08CEE380`, `0x0944A600`, `0x0826CC00`; unit box 8×8 `0x0A142300`.
- Draw ids: TA `f005564` ops 1888-1899; B1 `f003500` ops 907-913.

## 5. Code changes and tests

`ps3recomp-t178`, branch `agent/t178-dark-terrain-squares`. Diagnostics only, no rendering change:

- Guest depth bounds state recorded and written in RSXI draw events. The backend still does not apply it.
- `RSXI_TEX_BYTES=<n>`: guest bytes of uploaded textures up to n×n.
- `RSXI_SNAP_FP=<hex>`: target copy after each draw of one fragment program.
- `tools/test_t178_boxdiag.py`: source pins plus the decode check. This is not a before/after regression test, because no defect was fixed.

The first version of the draw hook broke the `test_rsxi_geom` pin. The suite caught it, and the hook now sits on its own line.

Overhead: not measured. By source, with RSXI inactive the additions are one branch per draw and three state stores when the guest sets depth bounds; with RSXI active but `RSXI_SNAP_FP` unset, one more comparison per draw.

## 6. Before and after

None. No fix exists, so no game pixels were compared. Only the WARP replay ran; RTX 5060 and AMD iGPU comparisons were not applicable. Analytic comparison results are in section 2.

## 7. Full test results

Commit `b2240f2c`, through `env_t169.cmd`: 125 PASS, 2 FAIL, 43 SKIP, 0 TIMEOUT.

`test_rt_pool_srv_layout` and `test_vpc_watch` fail. Both also fail when run alone on the T177 tree, so they are inherited. `test_t178_boxdiag` and `test_rsxi_geom` pass.

Build: rc=0 (`generated/analysis/t178/tools/build_t178.cmd`, main checkout). Runner `prepare t` passed its exe pin. Nothing launched.

## 8. Uncertainties

- The unit-box attribution is inferred; TA has no box constants, and B1 has constants but no snapshots.
- T165 B1 constants come from a different frame than the TA pixels.
- The replay uses synthetic ground depth and synthetic textures.
- The ELF depth-bounds scan cannot exclude indirect or batched writes.
- Base differs from T171: T171's default-on shader window commit is not in this tree, so the runner sets `RSX_SHADER_WINDOW=1`. If a squares-free result appears, compare against this first.
- The D3D12 debug layer was not run on the box path, because no game run was made.

## 9. Commits

- Code: `b2240f2c18b99626172d15224ae80ee4e5da2d55` on `agent/t178-dark-terrain-squares` (`ps3recomp-t178`), base `b86a1073`.
- Report: this commit on `agent/t178-dark-terrain-squares-report` (`root-t178`).

Audits: `audit_public.py --tree` on a copy of the code, rc=0. Report audited with `--staged --private-reports`.

## 10. Bounded in-game validation request

**Not run. Needs authorization.** Local console session, Godot and other workloads closed or suspended (`query session`, `nvidia-smi --query-compute-apps` empty).

Exe sha256 `109d1bfea4a6828976d49f2d01912fe1cdde96495a68898ac2628ecc6fae8ec5`. Runner: `generated/analysis/t178/ab/run_t178.py` (main checkout), derived from the T171 runner by `tools/make_runner_t178.py`.

```
py -3 generated/analysis/t178/ab/run_t178.py prepare t
py -3 generated/analysis/t178/ab/run_t178.py launch A a1
py -3 generated/analysis/t178/ab/run_t178.py launch B b1
```

Two launches, each stopping at race + 45 s, on the T171 route. Capture is at race + 38 s, one frame.

- Both arms: T171 arm B's flags plus `RSXI_VP_CONSTS=512 RSXI_UNITS=803 RSXI_TEX_BYTES=32 RSXI_SNAP_FP=022C20C1`.
- Arm B adds `TEX_NOCACHE=1`.
- Stops: effective-line mismatch, watchdog, crash, PSO failure, session change.

| Result | Meaning | Next step |
|---|---|---|
| `depth_bounds.test=1` on box draws | Missing feature | Implement D3D12 depth bounds (`D3D12_DEPTH_STENCIL_DESC1`, OPTIONS2) |
| Guest bytes flat, near the observed value | Host is innocent: asset or guest state | Look at who writes the texture (SPU), or treat as real appearance |
| Bytes have a transparent rim, per-box snapshot flat; arm B clears it | Stale texture | Fix cache invalidation for that write path |
| Bytes have a transparent rim, per-box snapshot flat; arm B does not clear it | Zeta values wrong | Compare unit 0 content with the depth pre-pass |
| Per-box snapshot shows correct gradients, squares absent | Base difference from T171 hides it | Compare with T171 before concluding |

A PS3 reference capture of the start grid would settle whether any flat darkening is real.
