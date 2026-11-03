# T168: visibility diagnostic validation

No culling was implemented, so there is no optimized output to compare. What is validated here is `RSX_VIS_DIAG`: its classes are right, and it doesn't change the image. No game was launched.

**Code:** `ps3recomp-t168-vis`, branch `agent/t168-visibility`, commit `fc6f1db`, based on T168 `800287c`.

## Tests

| Test | Result |
|---|---|
| `test_vis_diag` (classifier and pass table) | 10 checks, 0 failed |
| `test_t168_vis_backend` with `tools/check_vis_t168.py` (real D3D12 backend, software GPU) | PASS, 0 failed, 6 frames per arm. One arm's log is kept (`vis/logs_check.txt`, 103 PASS lines) |
| Arms depth_on, D_on, D_gbv, A_on | rc=0, 0 debug errors. D_gbv ran with GPU-based validation. 18 warnings per arm, the known benign clear-value id 820 |
| Diag on vs off, depth, D and A presets | 4 snapshots bit-identical per preset (`4aab0991d6fd9561`) |

**Limit:** the hash is the same across all three presets, so the harness doesn't exercise preset differences. It shows the diagnostic is neutral for this scene, not on real game content.

## Scenario coverage

| Brief's scenario | Harness draw | Result |
|---|---|---|
| Frustum boundary | M edge | visible |
| Large spanning object | M span | visible |
| Fully outside | M outside | outside |
| Camera or object movement | M moving, across 6 frames | visible for g≤4, then outside |
| Terrain occlusion (stand-in quad) | M occluder, M occluded | visible; occluded has 0 samples |
| Transparent object | M blended | visible |
| Shadow caster outside the main camera | S caster, S no caster | caster visible in its own target; no-caster outside |
| Multiple views | S view 1, S view 2 (two viewports) | separate passes, both visible |
| RT feedback | F feedback | visible |
| Beyond far plane | M beyond far | clamped, not clipped |

These are synthetic quads. They validate the classifier and pass separation, not any game scene. Vertex shaders are the harness's own, so guest skinning and VP behaviour are not covered.

## Offline capture analysis

`vis/tools/cull_offline_t168.py`, 19 frames, 11,441 records: 0 provable no-effect draws (`CULLING_OPPORTUNITIES.md`).

## Not validated

- `RSX_VIS_DIAG` on a real game frame, and its actual overhead.
- Real-GPU behaviour: the harness ran on the software GPU.
- Anything needing a run: outside share, hidden share, occluder count, PVS counters, GPU time.

## Remaining risks

| Risk | Label |
|---|---|
| Near/far clip: the host clamps where RSX may clip (`VISIBILITY_SYSTEM_RECONSTRUCTION.md`) | HYPOTHESIS |
| `pvsjob` float edge cases: `fcgt` denormal handling not audited | PARTIAL |
| Upstream LOD modifier could be time-driven, which would make LOD depend on host frame rate | PARTIAL |
| Records are not always guest draws: the backend concatenates within one BEGIN/END | VERIFIED limit |
| Diagnostic limits: over 16,384 draws go unmeasured and over 128 passes merge into the last. Both are reported in `[vd-f]` | VERIFIED |
