# T163: rendering validation

**Result: partial. All 17 `ps3recomp_host` scenes ran with guest programs under the validation layer on both GPUs. No D3D12 differential exists.**

Windows, `f11ecd4`, exe SHA-256 `834f7e965dadf7f6ce0132cd2769592302b25786e840174f23daee112d51e109`, LunarG SDK 1.4.341.1, `PS3RECOMP_VK_GUEST_PROGRAMS=1`, `--frames=10`. Tool: `tools/run_scenes_t163.py`.

| Scene | RTX 5060 | Radeon iGPU |
|---|---|---|
| (default), `--draw`, `--depth`, `--tex`, `--tex-io`, `--quads` | PASS | PASS |
| `--shader`, `--mip`, `--rtt`, `--depthtex`, `--mrt`, `--mrt-a`, `--cube`, `--depthbounds`, `--split-present`, `--feedback` | PASS | PASS |
| `--mip-aniso` | **FAIL** rc 3, 0xC0F080 vs 0x3060A0 | **FAIL** rc 3, same |

Each PASS is rc 0 from the scene's own expected-pixel check (plus its guest-draw count check where it has one), no "nothing to check", and no validation message. It is not a full-image comparison.

**`--mip-aniso` (VERIFIED from source):** the scene only passes with anisotropic filtering. Metal has it behind `PS3_ANISO` and its CI requires the scene to fail without that; the Vulkan backend has no anisotropy code. A missing opt-in feature, not a regression.

**Validation layer:** `VK_LAYER_KHRONOS_validation` from the SDK, `VK_LAYER_REPORT_FLAGS=error,warn`. The loader log proves it was inserted in all 34 runs, and a run with `info` on printed the layer's own status message, so its output reaches the logs. 0 errors and 0 warnings. This covers only what these small scenes exercise. No deliberately invalid call was made as a negative control.

**Not covered:**
- Stencil: no scene tests it. The source sets `stencilTestEnable` and picks D32S8 formats, so the "inert" comment near the engine pipeline code looks stale (PARTIAL, not proved by a run).
- Game workloads, constant attributes, alpha blending as its own scene, buffer reuse at scale, guest-memory update stress.
- D3D12 differential: **none**. `ps3recomp_host` has no D3D12 path, so no pixel-difference numbers exist.
- Software Vulkan renderer: not installed.
