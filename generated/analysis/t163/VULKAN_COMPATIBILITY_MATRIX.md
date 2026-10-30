# T163: Vulkan vs D3D12 compatibility matrix

Tree: `ps3recomp-t163-vulkan` (`afdcabd` + `cc343a0`). Status words apply to **Windows at this commit**. "Tested" means run here. "Implemented" means source only, not run here, because guest programs need glslang (see `VULKAN_NEXT_STEPS.md`). No row has been compared against D3D12.

| Subsystem | D3D12 (game path) | Existing Vulkan | Status | Missing work |
|---|---|---|---|---|
| RSX command processing | FIFO walker, `rsx_live_draw` | Same walker; feeds the draw engine or the vtable | Tested (fixed-function scenes) | Engine path untested on Windows |
| Shader translation | Decompilers to HLSL to DXIL | Same decompilers to HLSL to SPIR-V (glslang) | Implemented | glslang. Vulkan keeps 4096-instruction windows and refuses longer programs (T146 `RUNTIME_SWITCHES.md`) |
| Vertex buffers | Guest-layout upload, VP compaction | Vtable: `rsx_fetch_attrib`. Engine: compaction | Tested (vtable) / Implemented (engine) | Game formats unproven |
| Index buffers | Yes | **Vtable: no-op** (`vk_cb_draw_indexed`). Engine: `vkCmdDrawIndexed` | Missing (vtable) / Implemented (engine) | Engine path needed |
| Texture sampling | 16 units, opt-in guest samplers and mips | Vtable: unit 0, point. Engine: per-unit samplers, cube | Tested (vtable) / Implemented (engine) | Vertex-texture units are a stated gap |
| Texture residency | 96 slots; 1,024 plus write-watch and budget on `agent/perf-next-tex-residency` | Engine's own cache and sampled re-hash | Implemented | The new residency is D3D12-only code |
| Render targets | Pool, MRT | Engine: RTT, MRT, RGBA8 and RGBA16F only | Implemented | Other colour formats, depth-only passes (stated gaps) |
| Depth/stencil | Yes, T144 fidelity work | Depth tested on the vtable. Stencil on the engine: **source disagrees** | Partial | `70aee63` and D32S8 formats exist, but the comment near the engine pipeline code still says the test is inert. Must be tested |
| Alpha blending | Yes | Engine: `VK_BLEND_OP_*`. Vtable: none | Implemented | Run scenes |
| Shader constants | Per-draw CB slots | Engine: `bind_vs_constants` | Implemented | Run scenes |
| Pipeline caching | PSO cache | Table of 8192 and SPIR-V cache; **no `VkPipelineCache`** | Partial | Add driver-level cache |
| Resource barriers | Tracked states | Every image stays in `GENERAL` | Implemented, not optimal | Layout tracking is a later optimisation |
| Guest memory updates | Texture re-check, opt-in write-watch | Engine re-hash; feedback snapshots | Implemented | Run scenes |
| Draw submission | Deferred per pass | **One command buffer, submit and fence wait per clear or draw** (documented as deliberate) | Tested, **not viable for 6,900 draws** | Batching is the first performance task |
| Presentation | Swapchain | Readback and PPM dump; **window unavailable on Windows** (needs SDL2 or a native surface) | Partial | Win32 surface |

**Not ported to Vulkan:** T120 state fields (Vulkan doesn't read them), T159 state dedup, T162 GPU vertex fetch, T155 residency. Parity for T137 MSAA and T145 shader window was not audited.

**Shareable:** the walker, decompilers, `rsx_vertex_fetch`, `rsx_vertex_compact` and `rsx_texture_layout` already are.

**Main structural difference:** Vulkan and Metal use the draw engine, while D3D12 has its own path. A `RSX_BACKEND` switch is therefore not a thin vtable: the game's live path would have to change engines. It is not implemented.
