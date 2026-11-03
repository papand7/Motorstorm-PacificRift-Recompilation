# T164: Vulkan submission root cause

Source reviewed: `libs/video/rsx_vulkan_backend.c` at `f11ecd4` (VERIFIED from source unless marked). Line numbers are that commit's.

## Path before T164

```
FIFO walker (cellGcm_rsx_process_fifo)
  -> rsx_draw_engine (register file, surfaces, texture cache, compaction)
    -> vk_eng_draw / clear / upload / create / snapshot
         memcpy vertices into the one s_vk.vertices        (overwritten next draw)
         memcpy constants into the one s_g.ubo             (overwritten next draw)
         vkUpdateDescriptorSets on the one s_g.set         (rewritten next draw)
         vk_begin: vkResetCommandBuffer, vkBeginCommandBuffer on the one s_vk.cmd
         barrier, vkCmdBeginRenderPass, draw, vkCmdEndRenderPass
         vk_submit_and_wait: vkEndCommandBuffer, vkResetFences, vkQueueSubmit,
                             vkWaitForFences(UINT64_MAX)    <-- CPU stops here
```

There is one command buffer, one fence, one vertex buffer, one UBO and one descriptor set. **The fence wait after each operation is what makes all that sharing legal.** It can't simply be removed. The header says so ("what lets the engine's submit_and_wait and staging reuse cost nothing").

## Every queue operation and wait

| Site (f11ecd4) | Call | What it protects | Class |
|---|---|---|---|
| `vk_submit_and_wait` 610 | submit + fence wait, reached from 18 call sites | see below | see below |
| `vk_queue_submit` 562 | the only `vkQueueSubmit` wrapper | queue external sync (`queue_mu`) | Required (kept) |
| `vk_device_idle` 578 | `vkDeviceWaitIdle` | shutdown only | Required |
| `vk_present_wait_gpu` 1993 | `present_fence` wait before image destruction | a present's copy still reading the image | Resource reuse |
| `vk_present_complete_locked` 2003 | `present_fence` wait | CPU reads the frame back | CPU readback |
| window path 1950, 1996 | `window_fence` | swapchain blit (no window on Windows) | Not exercised |
| `vkQueueWaitIdle`, `vkQueueSubmit2` | none in the file | | |

No synchronization2: the backend loads Vulkan 1.0 entry points only.

## The 18 `vk_submit_and_wait` call sites

| Operation | Lines | Protected | Class |
|---|---|---|---|
| Draw | 3479 | Shared vertices, UBO, set; order | **Artifact of the design** |
| Clear colour, depth/stencil | 2376, 2392 | Order | **Unnecessary**: a barrier gives the order |
| Texture region upload | 2187 | Staging buffer destroyed right after | **Artifact**: staging can outlive the copy |
| Create target, depth, texture, snapshot, scratch depth | 2321, 2347, 2520, 2636, 2683, 3271 | Order, layout move | **Unnecessary**: a barrier gives the order |
| Depth snapshot | 2708 | Staging; order | **Artifact**: stays on the GPU timeline |
| Colour readback, depth readback | 2464, 2744 | CPU reads the result | **Required by CPU readback** (kept) |
| Vtable path: texture, draw, clear | 696, 1615, 1663, 1709 | Same sharing, fixed-function path | Left synchronous, not the path to a title |
| Init | 3658 | Start-up | Harmless (kept) |

## RSX semantics: what really needs the CPU to wait

| RSX operation | Needs | Used |
|---|---|---|
| Target written, then sampled | GPU order and memory visibility | Barrier, no CPU wait |
| Upload, then sampled | Same | Barrier, no CPU wait |
| Depth reuse across passes | Same | Barrier, no CPU wait |
| Target change | Ends the render pass only | Barrier, no CPU wait |
| Guest memory write, then draw | Nothing on the GPU: the engine re-hashes and vertices are copied at record time | None |
| CPU-visible readback (guest_read, depth_readback, dumps) | **CPU wait**. The engine's `submit_and_wait` contract is "fully synchronous" | Batch ends, CPU waits |
| Frame present | GPU order; the wait is for the readback copy | Submit without waiting for draws; the present's own fence is kept |
| `NV406E_SET_REFERENCE`, semaphores | Guest-visible sync | **Not connected in this path**: the only `rsx_draw_engine_flush` definition has no caller in `libs/` or `runtime/`. Must be settled before a game runs on this path |
| FIFO boundaries | Nothing | None |

## Measured cost of the old design

See `VULKAN_PERFORMANCE.md`: every operation paid one fence wait of 49-51 µs, and that waiting took 63-67% of the frame wall time in workloads A and B on both GPUs.
