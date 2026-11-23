# Bindless textures, MDI, multi-threaded recording, SIMD vertex work: feasibility and RSX_VK_BINDLESS

2026-11-22. Private, offline. No game was launched; the GPU was busy (texture pack generation).

## 1. Profile from existing logs (VERIFIED, `[vk-stats]` deltas over ~1 s windows)

| Run | draws/frame | backend record ms/frame | desc set allocs/frame | drain draws ms/frame (`[drain-prof]`) |
|---|---:|---:|---:|---:|
| Kbr6 (race) | ~1870 | 1.89 (~1.0 us/draw) | ~274 (15% of draws) | 7.7-9.3 |
| Klt4 (race) | ~2890 | 3.08 (~1.06 us/draw) | ~475 (16%) | n/a |

- `record_ms` covers the whole backend draw (vertex/index copies into the arena, constants, descriptors, command recording).
- The rest of the drain (about 6.5 ms in Kbr6) is engine-side work that this data does not split up.
- The frame (25-35 ms) is set by the main thread (`roadto60_next/CURRENT_CRITICAL_PATH.md`), not by the drain.
- `vk_batch_*` batches command buffers and submissions. It does not merge draws.
- `RSX_TEX_SLOTS` is D3D12-only (the size of its upload table). It does nothing in Vulkan.

## 2. Verdicts

- **RSX_VK_BINDLESS**: built (section 3). Expected saving 0.2-0.5 ms/frame on the drain thread; about 0 on frame time while the main thread sets the frame (HYPOTHESIS).
- **MDI**: BLOCKED, not built. Every draw has:
  - its own dynamic UBO offset (vertex constants, up to 8 KB);
  - its own copy of vertices and indices in the arena;
  - often a viewport/scissor/stencil change or a ZPASS query.
  To merge draws, the vertex-program constants would have to move into an SSBO indexed by draw ID, which means rewriting every VPConst access. Ceiling: at most ~0.5-1 ms of drain per frame.
- **RSX_VK_MT_RECORD**: not built.
  - `RSX_BE_THREAD` already moves all recording off the drain. It was slower in 4 in-run A/Bs (+0.8 to +4.6 ms/frame, Kk23-27, `vksync/BE_THREAD_AND_VMX_FAST.md`), on a CPU whose 12 threads are already busy.
  - N recording threads would add to that load.
- **RSX_VTX_SIMD**: not built.
  - GPU decode is on. What stays on the CPU: the raw vertex copy (~3.1 KB/draw, a CRT memcpy that is already vectorised), engine topology/index building, and VS memo hashing.
  - Their share of the ~6.5 ms engine time is BLOCKED: there is no drain-thread sampler profile for the current build. Profile first.

## 3. RSX_VK_BINDLESS=1 (opt-in, read once)

- Files:
  - `libs/video/rsx_vk_bindless_core.h`: slot map and pixel-program rewrite, no Vulkan.
  - `libs/video/rsx_vk_bindless.h`: Vulkan side.
  - Hooks in `rsx_vulkan_backend.c`: instance 1.2, device setup, view-destroy forget, pipeline create/layout, write_descriptors, the bind in the batched draw, the prep worker text, shutdown, stats.
- Set 1 holds `Texture2D[4096]` at binding 16 and `SamplerState[128]` at binding 48. It is partially bound, update-after-bind and update-unused-while-pending.
- Per draw, the 16 texture slots and 16 sampler slots go in a 128-byte push block, pushed only when they change. Set 0 keeps only the UBOs and RT bindings, so it is reused within the batch until the constants move to another arena block.
- Off (logged) when:
  - the device is not Vulkan 1.2 or lacks the features or limits;
  - `RSX_FSR_MODE=3`;
  - submission is not batched.
  Cube, volume and ray-query programs, and any rewrite or translation that is refused, keep the old path, per program.
- `[vk-bindless]` line in the stats.

Tests (VERIFIED offline):
- `ps3recomp-vkgame/tools/test_vk_bindless.py`: hook pins, plus `tests/test_vk_bindless.c` (565,917 checks). Three mutations are caught: backward-shift delete, the free list, the unit range.
- `generated/analysis/bindless/tools/build_test.py` builds the glslang variant. Against `vksync/ab2/vkwarm_pipe.txt`:
  - 193 pixel programs, 126 rewritten, 126/126 compile with the tables in set 1 (bindings 16/48) and the push block (second member at byte 64);
  - 67 programs keep the old path (split units).
- Same image: NOT verified (no replay tool for Vulkan frames). Kbl1 is the look check.

Exe: `build/bindless-link/MotorStormPacificRiftRecomp.exe` (shadow_link.py from ppucc2 objects + current `rsx_vulkan_backend.c`), sha256 `f99651b12d20d17591c517f28468eebed157539d0786b9e3c8f8fc9e648de959`, staged as `ab2/exe_bl`.

Arms queued before `Klt5t`:
- Kbl1: look, bindless on, shots in `build/shots/bl1`.
- Kbl2a / Kbl2b: timing, bindless on / off, same exe. Close EA Desktop and Epic first.

Compare `[drain-prof]` means, `record_ms` and `desc_allocs` deltas, and `[frame-hist]`.

Risks:
- The first bindless run translates the rewritten programs again (shader cache misses; longer load, possible first-use hitches).
- Validation-layer cleanliness is unchecked.
- A sampled view destroyed outside the two hooked sites would leave a stale slot (none found).

## 4. With FSR 3.1 (RSX_FSR_MODE=3), 2026-11-22

Why it was off: a precaution. Nothing was ever seen to fail with FSR 3.1; it was simply untested. `vk_tsr_obj_draw` (the motion-vector object pass) replays each draw with the draw's own set 0 under `s_tsr.dpl`. I gated bindless off rather than check whether that is compatible.

Checked (VERIFIED by reading the code; pinned in `tools/test_vk_bindless.py`):
- **Same set 0 layout.** `s_tsr.dpl` = { `s_g.set_layout`, `s_tsr.pdsl` }. Bindless set 0 is allocated from `s_g.set_layout` and holds the same UBO and RT bindings.
- **No texture reads in the object pass.** `rsx_tsr_obj_fs` samples nothing, so the unwritten texture bindings in bindless set 0 are not used.
- **No leaked bindings or push constants.** The object pass calls `vk_batch_end_pass()` before binding its layout. Every other pass ends the engine pass first through `vk_begin()`: TSR motion vectors and scene effects are compute; HDR, FSR 1 and present record into their own command buffer. Ending a pass clears `s_b.ds_set`, so the next bindless draw is "fresh": it rebinds both sets and re-pushes its slots. Another pipeline layout's set 1 or push constants never reach a bindless draw.
- **No push-constant overlap.** The FX and FSR pipelines use their own layouts with compute or fragment ranges. Nothing is shared with `s_bl.pipe_layout`.
- **Jitter and mip bias unaffected.** Jitter lives in the vertex program, which is unchanged. The FSR mip bias is applied in `vk_eng_sampler`, whose samplers are the ones the table holds.

Change: the `vk_tsr_wanted()` gate is removed from `vk_bl_device_setup` (doc comment updated). Hook tests 21/21 pass; the glslang warm-list test still compiles 126/126.

Exe: `build/bindless-fsr-link/MotorStormPacificRiftRecomp.exe`, sha256 `1552d113f5358dc6d471fe2068090971670bbf43a1b25cbd61fcd2c81117d5cb`, slot `ab2/exe_bl2`.

Arm Kbl3, before `Klt5t`: Kbr6's setup (FSR 3.1 balanced, no texture pack, shots from 1500 every 90) plus `RSX_VK_BINDLESS=1`, visual only. Compare its shots with Kbr6's. Kbl1/Kbl2a/Kbl2b keep `exe_bl` (FSR off; the change does not affect them).

## 5. Kbl1 / Kbl3 boot failure and fix (2026-11-22)

What happened (VERIFIED from the logs): both runs stopped about 4 s after psarc_opened with `GcKernel::Present() Timeout`.

Cause:
- stderr ends at `[warm] engine pass 1 ... cached` followed by `RSX_VK_BINDLESS: on`. Pass 2 (the synchronous warm replay of ~680 programs) never reports completion.
- Pass 2 was translating every rewritten pixel program on the RSX thread. The rewritten texts were not in the shader cache, so each one went through glslang one after another, and the guest's Present wait timed out.
- Descriptor updates were not the cause. Slot writes are one `vkUpdateDescriptorSets` each, with no device waits and no table rebuilds.

Fix (exe `build/bindless-async-link`, sha256 `bd08139aeec1140818c698b48e2848198ad78651fb0c618a2495c36e42adf824`, slot `exe_bl3`):
- `pipeline_create` translates only the original program, as without the switch. The warm replay and the prep worker are unchanged.
- The rewritten text is kept on the program. Its first draw asks the background pool for it (`rsx_hlsl_to_spirv_async`). A pending program is polled again at most every 8 batches.
- Until it is ready, the original pipeline draws. Once it is ready, bindless variants are built from a copy of the program (kept out of the side cache and the warm list) and used from then on. A refused translation keeps the original.
- New counters in `[vk-bindless]`: ready, polls_pending.

Tests:
- `tools/test_vk_bindless.py`: 28 PASS, including pins that pipeline creation, the queue step and the prep worker never translate a rewritten program on the drain thread.
- The glslang test now also checks the async path: queued (1), then served (0), with the tables in set 1. 126/126 warm-list programs compile.

Arms:
- Kbl4 = Kbl1's setup on the fixed exe.
- Kbl5 = Kbl3's setup (FSR 3.1) on the fixed exe.
- Both are queued before Kbl2a/Kbl2b, which are repointed to `exe_bl3` (the old exe would time out the same way).

Note: on the first run, programs switch to bindless over the first seconds of use. Translations are then on disk, so later runs switch at once.
