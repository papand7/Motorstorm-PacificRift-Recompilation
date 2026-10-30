# T163: existing Vulkan work (VERIFIED from git and source)

**Where it lives:** in the ps3recomp tree itself, inherited from upstream and present in every local branch. It is not a MotorStorm-specific effort and has never been used by this port (`docs/UPSTREAM_INTEGRATION.md:57`: merged but inactive).

| Item | Evidence |
|---|---|
| Backend | `libs/video/rsx_vulkan_backend.c` (about 3,800 lines at `afdcabd`), `.h` |
| Translator | `libs/video/rsx_shader_spirv.cpp`: decompiler HLSL to SPIR-V through glslang, with a memory and disk cache |
| Shared path | `libs/video/rsx_draw_engine.c/.h`: register-file draw engine, shared with Metal. D3D12 does not use it (0 references in `rsx_d3d12_backend.c`) |
| Fallback shaders | `libs/video/vulkan/rsx_vk_fallback.*` with precompiled `.spv.h` |
| Harness | `runtime/host/host_posix.c` (`ps3recomp_host`): hand-built NV4097 scenes with pixel checks |
| CI | `.github/workflows/linux-vulkan.yml`: Linux on lavapipe, gcc and clang, with the validation layer. Results of those upstream runs are not available here |

**Key commits (first appearance):**
- `3881610` 2026-09-02: draw engine
- `70dada7` 2026-09-26: stage V0 (clear, present, readback)
- `19fa68e` 2026-09-26: stage V1 (fallback draw path)
- `55fe15b` 2026-09-27: HLSL to SPIR-V
- `70aee63`: stencil
- `f6960aa`: cube maps
- `1e6f4c8` 2026-10-17: colour feedback snapshots
- `5588d58` 2026-10-19: last backend commit, pipeline table size. 29 commits touch the backend in total

**`agent/t146b-vulkan-windows`:** has **no commits of its own**. Its tip is `f373398`, the local baseline, and its worktree is clean. Any Windows port attempted there was never committed.

**Status before T163:**
- Windows build: never. CMake stopped with "Linux-only", and the source was wrapped in `#ifndef _WIN32`.
- Tested on Windows or with MotorStorm: no evidence of either.
- Why it stopped here: the port targets D3D12, and Vulkan was never activated. No report found records a decision to abandon it.

**RACiT:** `racit-reference-t131/README.md:21` only lists a "Vulkan-based RSX renderer", and one patch there mentions Vulkan. The patch was not reviewed in depth and no Vulkan notes were recovered.

**Reusable:** all of it. The backend, engine and translator are in the MIT-licensed ps3recomp tree (`LICENSE`).
