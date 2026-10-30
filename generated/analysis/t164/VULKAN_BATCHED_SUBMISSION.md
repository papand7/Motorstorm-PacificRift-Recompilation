# T164: batched submission

**Switch:** `RSX_VK_BATCHED_SUBMIT=1`, opt-in. Unset, the reference path is kept unchanged apart from opt-in counters. D3D12 code is not touched. Applies to the draw engine path, which is the one Vulkan uses with guest programs on. The fixed-function vtable path stays synchronous even with the switch on.

## New path

```
RSX commands -> rsx_draw_engine -> vk_eng_draw
  -> vk_batch_draw:
       arena: vertices, indices, constants (constants only when changed)
       descriptor set: new per distinct binding, reused while identical
       same framebuffer and no sampling of its targets? stay in the render pass
       else: end pass, full memory barrier, begin pass
       record; flush if the batch is full
Boundary: readback, engine submit_and_wait, present, full batch
  -> vkEndCommandBuffer, vkQueueSubmit(batch fence)
Retirement: strictly oldest first, on poll or when a slot is needed
  -> destroy retired objects, recycle arena blocks, reset descriptor pools
```

## Limits

| Limit | Value | When reached |
|---|---|---|
| Batches in flight | 4 | CPU waits for the oldest (counted) |
| Draws per batch | 4,096 (`RSX_VK_BATCH_DRAWS` overrides, capped at 8,192) | Flush, no wait |
| Arena per batch | 48 MiB | Flush, no wait |
| Arena block | 16 MiB; larger for one large upload, freed on retire | |
| Descriptor pools per batch | 16 x 512 sets | Cannot be reached: a draw takes at most one set |

Memory bound: about 4 x (48 MiB + one block) of arena, plus large uploads until they retire. Standard blocks are kept for reuse and released at shutdown.

## What replaces each guarantee of the old waits

| Guarantee | Now |
|---|---|
| Draw order | One queue, one recording order |
| Render target then sample | Full memory barrier before each new render pass |
| Upload then sample | `vk_begin` ends the pass and adds a barrier before each copy or clear |
| Sampling a bound target directly | Detected, the pass is split, same as reference behaviour |
| Colour feedback and depth snapshots | Copies ordered on the GPU, no CPU wait |
| Vertex and constant data | Per-batch arena, valid until that batch retires |
| Descriptors | Never rewritten after being recorded |
| Destroying images, views, framebuffers, pipelines, buffers | Goes on the recording batch's retire list if work is pending, otherwise destroyed at once |
| Batch against present | Present flushes first; every batch starts with a barrier against all earlier submissions |
| CPU reads | `vk_batch_idle`: flush and wait for all |

Samplers live until shutdown, as before. Shader modules may be destroyed while pipelines are in use (Vulkan allows it).

## Synchronization: what it is and isn't

Barriers use `ALL_COMMANDS -> ALL_COMMANDS`, `MEMORY_WRITE -> MEMORY_READ|WRITE`, and images stay in `GENERAL`. This is **correct but coarse**. Synchronization2 was not adopted: the backend targets Vulkan 1.0 and these barriers are already few (see `VULKAN_PERFORMANCE.md`). Narrower stage masks and real layouts are later GPU-side work, not measured here.

## Bugs found on the way

- My first pool code allocated until failure. On Vulkan 1.0 that is invalid (`VUID-VkDescriptorSetAllocateInfo-apiVersion-07895`). **The validation layer caught it only under load, in the benchmark scenes.** Fixed by counting allocations.
- Slot pointers were unsafe as batch identity because slots are reused; a per-batch sequence number replaced them before any run.
- Ending a batch in the middle of a draw would have left its data in a batch that retires too early. That path was removed: nothing can flush between a draw's first allocation and its record.

## Anisotropic filtering

- Device feature `samplerAnisotropy` is enabled when supported; `maxSamplerAnisotropy` limits every sampler.
- Guest state: `SET_TEXTURE_CONTROL0 [6:4]` is decoded into `rsx_be_sampler_desc.aniso`, only where the filter allows it (linear min and mag, and trilinear or no mips, matching `rsx_sampler_xlate.h`).
- `PS3_ANISO=2..16`: Metal's opt-in, on linear-min mipped samplers. Not applied unconditionally.
- Point-filtered and unmipped samplers are unchanged.

## Instrumentation

`RSX_VK_STATS=1` prints one `[vk-stats]` line at shutdown. `RSX_VK_FRAME_HASH=1` prints FNV-1a per presented frame. Off, each counter is a branch or a plain add. On, the timers and timestamps cost 11-17% in three of the four measured cases (`VULKAN_PERFORMANCE.md`).

## Build

`generated/analysis/t164/tools/build_vk_t164.cmd` (private, gitignored): the T163 recipe with `-DPS3RECOMP_VULKAN_SDK=<sdk>`. Vulkan-Headers v1.4.341, clang-cl LLVM 23.1.3, Ninja, Release.

## Not done

- Vulkan's own `RSX_BACKEND` switch and any game-path connection.
- Vertex-program constants above the UBO cap and vertex textures: existing gaps, unchanged.
- Windows surface: still headless.
