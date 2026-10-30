# T163: rendering validation

**Result: partial. Fixed-function scenes only. No differential comparison and no validation-layer run.**

`ps3recomp_host` scene self-checks, Windows, `cc343a0`:

| Scene | RTX 5060 (1.4.341) | Radeon iGPU (1.4.315) |
|---|---|---|
| (default clear) | PASS | PASS |
| `--draw` | PASS | PASS |
| `--depth` | PASS | PASS |
| `--tex` | PASS | PASS |
| `--tex-io` | PASS | PASS |
| `--quads` | PASS | PASS |

Each PASS is rc 0 from the scene's own expected-pixel checks, not a full image comparison.

**NOT RUN (unsupported, not passed):** `--shader`, `--rtt`, `--mrt` and `--cube` were attempted on the RTX with `PS3RECOMP_VK_GUEST_PROGRAMS=1`. They return rc 0 but print "the Vulkan backend runs no guest programs; nothing to check". `--mip`, `--mrt-a`, `--depthtex` and `--depthbounds` need the same path.

**Required coverage not achieved:**
- Strips and fans with guest programs, constant attributes, texture rewrites, alpha blending, stencil, render-target switching, multiple passes, shader constants, buffer reuse, guest-memory updates.
- Vulkan validation layers: **not available**, so 0 errors cannot be claimed.
- D3D12 differential: **none**. `ps3recomp_host` has no D3D12 path, so no pixel-difference numbers exist. It needs a shared scene runner or a D3D12 host.
- Software Vulkan renderer: not installed.
