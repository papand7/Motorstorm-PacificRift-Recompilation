# T163: next steps

**Status against milestones:** M1 partial (reproducible Windows build of the fixed-function path). M2, M3 and M4 are blocked at the step below.

**Blocker:** glslang, spirv-tools and the validation layer. The signed LunarG SDK 1.4.341.1 installer is downloaded at `build/t163-vksdk-dl/vulkan_sdk.exe` (SHA-256 `bcf2d75aa9556889ab974858666e20b3655b6055a0db704ccb47279ff33b5bfe`, Authenticode valid), but running it was denied by the session's permission policy and it **has not been run**. Either the user installs it, or the user allows the silent install to `build/vulkan-sdk`.

**Order after that:**
1. Rebuild with glslang found. Run all host scenes with guest programs under `VK_LAYER_KHRONOS_validation` on both GPUs. Fix whatever fails. Settle the stencil contradiction.
2. Differential harness: make the scene builders drive D3D12 (WARP and hardware) and compare full images, reporting pixel count and maximum channel difference.
3. Batch submission: record per pass, and submit and wait only at readback, present or real dependencies. Prerequisite for any benchmark.
4. Synthetic 2,000 and 6,900 draw workloads, both APIs, default configurations, medians and spread.
5. Parity: colour formats, vertex textures, `VkPipelineCache`, a Win32 surface, the T120 state fields, and FP windows above 4096.
6. Decide on `RSX_BACKEND`. The game path is `rsx_live_draw` + D3D12, not the engine. Either run the engine under the game (large behaviour risk, loses the T1xx D3D12 fixes) or put a Vulkan executor behind `rsx_live_draw`. The second looks closer to parity (HYPOTHESIS, not costed).

**Optimisation applicability (source review, nothing measured):**
- **Residency (`a049b1e`):** the code is inside `rsx_d3d12_backend.c`, so it can't be reused directly. The write-watch and budget logic could be extracted. Vulkan needs its own deferred destruction.
- **GPU vertex fetch (T162):** the Vulkan backend uses no storage buffers today. It would need a storage-buffer path and SPIR-V variants of the fetch shader. Not merged.
- **Shared HLSL:** already the design; decompiler output feeds both compilers. Differences in glslang's HLSL front end remain to be tested.
- **State dedup (T159):** don't port it yet. Under per-draw submission, state setup is unlikely to be the first-order cost (HYPOTHESIS). Measure after batching.

**In-game test:** not justified yet. No game launch was made or is requested.
