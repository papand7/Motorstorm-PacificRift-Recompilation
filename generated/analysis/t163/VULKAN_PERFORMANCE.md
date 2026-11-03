# T163: performance

**Result: no Vulkan vs D3D12 comparison exists, so no statement that either is faster is supported.** Representative rendering is not established and there is no shared D3D12 harness.

**Only measurement:** wall time of the whole `ps3recomp_host --draw --frames=600` process, 3 runs per device, Vulkan only. The number of frames actually rendered was not confirmed from the output.

| Device | ms |
|---|---|
| RTX 5060 | 703, 686, 691 |
| Radeon iGPU | 460, 459, 453 |

This includes process and device start-up, so it says nothing about game workloads. The iGPU being quicker here must not be generalised.

**Structural finding (VERIFIED from source):** every clear and draw is its own command buffer with a fence wait (`rsx_vulkan_backend.c` header; 18 call sites of `vk_submit_and_wait`). The heavy scene's roughly 6,900 draws would mean roughly 6,900 CPU/GPU round trips per guest frame. Any comparison before batching would measure this design choice, not Vulkan.

**Not measured:** CPU command processing, recording, pipeline creation, shader compilation, uploads, GPU execution, synchronisation, the 2,000 and 6,900 draw workloads.
