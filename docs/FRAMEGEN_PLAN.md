# Frame generation plan (FSR 3.1 FG, Vulkan)

Goal: 60 fps output at upscaled 1080p. The simulation holds ~40 Hz (45 to 50 Hz with stalls), so present 40 to 45 real frames/s and let FSR frame generation (FG) fill to ~60 to 90 output frames/s. Status: PLAN plus a probe stub. Nothing here has been run (no game run was allowed). Labels: VERIFIED = read from files on disk; HYPOTHESIS = not tested.

## 1. What the SDK ships (VERIFIED from `build/fidelityfx-sdk/Kits/FidelityFX`)

`signedbin/` holds: `amd_fidelityfx_loader_vk.dll/.lib`, `amd_fidelityfx_upscaler_vk.dll`, **`amd_fidelityfx_framegeneration_vk.dll`** (plus the dx12 set, denoiser and radiancecache for dx12). So the signed Vulkan set DOES contain a frame generation provider; our backend copies only the loader and upscaler DLLs today and must also ship `amd_fidelityfx_framegeneration_vk.dll` beside them (`RSX_FSR3_DIR` already covers the lookup).

Headers: `framegeneration/include/ffx_framegeneration.h`, `ffx_framegeneration_api_types.h`, `vk/ffx_api_framegeneration_vk.h` (copied into `libs/video/vulkan/third_party/ffx_api/framegeneration/include/` for the probe). Docs: `docs/techniques/frame-interpolation-swap-chain.md`, `frame-interpolation-api.md`.

Versions: swapchain FG 4.0.0 needs a Radeon RX 9000 (RDNA 4) GPU; on other hardware the API falls back to FG swapchain **3.1.7**, which has no extra GPU requirement. Both: storage-image load on `VK_FORMAT_R16G16B16A16_UNORM`. Memory about 42 MB at 1080p (51 MB with a separate UI surface and double buffering).

## 2. How integration works on Vulkan (VERIFIED from docs and headers)

The FG swapchain **replaces `VkSwapchainKHR`**, so it replaces our swapchain, acquire and present.

- `ffxCreateContext` with `ffxCreateContextDescFrameGenerationSwapChainVK` (physicalDevice, device, `VkSwapchainKHR* swapchain` which is destroyed and replaced, `VkSwapchainCreateInfoKHR createInfo`, four `VkQueueInfoFFXAPI`: gameQueue, asyncComputeQueue, presentQueue, imageAcquireQueue), chained with `ffxCreateContextDescFrameGenerationSwapChainVersionVK` (version = `FFX_FRAMEGENERATION_SWAPCHAIN_VK_VERSION`). Optional `...SwapChainModeVK` (compose UI on present queue or game queue).
- `ffxQuery` with `ffxQueryDescSwapchainReplacementFunctionsVK` returns replacements for `vkGetSwapchainImagesKHR`, `vkAcquireNextImageKHR`, `vkQueuePresentKHR`, `vkSetHdrMetadataEXT`, plus `CreateSwapchainFFXAPI/DestroySwapchainFFXAPI` (extra `void* pContext`) and `GetLastPresentCount`.
- A second context, `ffxCreateContextDescFrameGeneration` (FG proper) with the backend VK descriptor, then each frame: `ffxConfigure(ffxConfigureDescFrameGeneration)` (enable, `swapChain`, `frameGenerationCallback`, `presentCallback` for UI, optional `HUDLessColor`, `generationRect`, `allowAsyncWorkloads`) and `ffxDispatch(ffxDispatchDescFrameGenerationPrepareV2)` with depth, motion vectors, camera near/far/fov, jitter, frameTimeDelta, `reset`, `cameraPosition/Up/Right/Forward` as the SDK header lists. In the callback, `ffxDispatch(ffxDispatchDescFrameGeneration)` fills the interpolated image from the real backbuffers.
- Inputs: upscaled colour (the backbuffer), depth and motion vectors (render-size, same convention as the upscaler dispatch), camera data, and UI via one of: present callback (UI drawn per displayed frame), separate UI texture (alpha-blended onto both), or HUD-less colour (shader detects UI).
- Vulkan device needs: queues as above (the swapchain makes its own present/compose threads, 2 extra CPU threads), swapchain extension, and the signed provider checks the device. Extension names are not listed in the docs; the provider will report failures through `fpMessage`.

## 3. What the backend has (VERIFIED by reading `rsx_vulkan_backend.c`, `cellGcmSys.c`)

- Upscale: `vk_tsr_*` (TSR FSR 3.1 upscaler context, jitter, render-size `s_tsr.depth` R32F and `s_tsr.mv` RG16F with camera MVs plus moving-object MVs, `vk_tsr_record` dispatches into `s_fsr.mid` (output size, RGBA8) then blits to swapchain image idx). Upscale dispatch happens inside the window present, one per game flip.
- HUD: NOT separated. HUD draws are drawn into the same scene target (and jittered, `n_hud`), so they are upscaled together with the scene. No HUD-less copy, no UI target exists.
- Present: `vk_present_complete_locked` waits the present fence, reads back the centre pixel (and the frame hash/dump when asked), then `vk_present_window` acquires, records, submits to the one queue, waits `window_fence` (CPU-side wait per frame), and `vkQueuePresentKHR`. One queue, one family (`queueCount = 1`, `s_vk.queue`): there is no async-compute or separate present queue.
- Pacing: `gcm_sim_pace_after_flip` (`PS3_SIM_PACE`, `PS3_SIM_PACE_HZ`) sleeps in the guest flip to hold a sim rate. Present interval via `RSX_PRESENT_INTERVAL` (0 gives MAILBOX else FIFO). Not coupled to presentation.
- Swapchain image usage is TRANSFER_DST (+ COLOR_ATTACHMENT for FSR); entry points are loaded by hand (`pvk*`), not via a loader library.

## 4. What is missing, in order

1. Ship `amd_fidelityfx_framegeneration_vk.dll` and load check (done in the probe: `RSX_FRAMEGEN=1`).
2. A Vulkan queue layout: extra queue(s) (a second graphics-capable queue for present/compose, optional compute queue, and an image-acquire queue), a `vkQueueSubmit` lock shared with FFX (`submitFunc`; our `vk_queue_submit` already serialises). Needs device creation changes.
3. Swapchain ownership handover: create through `ffxCreateContext` (FG swapchain), use the replacement entry points in `vk_present_window`/`vk_create_swapchain`, keep the usage bits we need, handle window resize/lost.
4. A UI/HUD answer (see risks). Minimum viable: a HUD-less colour copy taken before the first HUD draw, passed as `HUDLessColor` (mode 3). Better: render the HUD in a separate RGBA target after the scene upscale and give it as UI texture (HUD must then be drawn at output resolution or composited after the TSR).
5. FG context (`ffxCreateContextDescFrameGeneration`) and Prepare/Dispatch per real frame: our upscaled image is `s_fsr.mid`; depth and MV are render-size (FG accepts a render size via `renderSize`), camera data from the latched `fr_*` values (near, far, fov, plus camera position/basis, which we do not currently latch: derived from the c0-c3 matrix inverse already computed in `vk_tsr_mv`).
6. Move the per-frame window present from a CPU `vk_wait_fence(window_fence)` model to FG's: the swapchain paces and may present twice per `vkQueuePresentKHR`.
7. Pacing policy: see risks. Decouple the sim cap from the displayed rate.

## 5. Flags

- `RSX_FRAMEGEN=1`: enables the probe now (default off, presentation unchanged). Later: enables FG; `RSX_FRAMEGEN=probe` could stay as the probe-only mode.
- Reuse `RSX_FSR_MODE=3` and `RSX_FSR=<profile>` (FG needs the TSR path for depth, MVs and jitter). Reuse `RSX_PRESENT_INTERVAL=0` plus VSync off in tests.
- Planned: `RSX_FRAMEGEN_UI=hudless|texture|callback`, `RSX_FRAMEGEN_ASYNC=0|1`.

## 6. Risks

- **Input latency.** Interpolation needs the next real frame before showing the in-between one: about one real frame (22 to 25 ms at 40 to 45 Hz) added latency, plus FG pacing. Unfixable at 40 Hz base except by lowering the render queue depth. Measure.
- **HUD.** Today the HUD is in the colour target and is jittered and upscaled; FG warps text and speed dials unless a HUD-less or UI target is supplied. This is the largest piece of work.
- **40 Hz pacing.** `PS3_SIM_PACE_HZ` makes the game flip at a fixed rate; FG wants a steady real cadence slightly below half the output rate (SDK advice). 40 to 45 Hz base gives 80 to 90 out; capping the display at 60 means dropping frames or presenting with VSync at 60 (a 60 Hz VSync with a 40 Hz base and FG x2 = 80 would be uneven: either run 30 base x2, or accept VRR). Decide the target mode: VRR output ~80, or fixed 60 with a 30 Hz base. HYPOTHESIS.
- **Windowed present stalls.** The ~11 ms present wait per frame in long episodes at 45 to 50 Hz (windowed compositor, not the FG) will be amplified: FG's pacing thread busy-waits and uses borderless/exclusive fullscreen for best results; windowed DWM presents can add jitter. Test borderless fullscreen first.
- **Single queue.** The backend has one queue; FG wants separate present/compose queues for pacing, so queue creation and submit locking must change (risk of deadlocks with `vk_queue_submit` serialisation).
- **Artifacts at cuts and camera shake.** FG relies on MVs; a camera cut must call `reset`. Our camera MVs come from a reprojection assuming c0-c3 world-to-clip (HYPOTHESIS from rsx_tsr.h); shake applied to the camera matrix feeds the MVs as real motion (good) but moving-object MVs are partial (replayed draws only), so particles, transparent effects and skinned objects will ghost.
- **GPU and DLL gating.** FG 4.0.0 needs RDNA 4 and a driver; otherwise 3.1.7 is used, but whichever is selected must be logged. Signed DLLs are loaded from the exe dir, so they must be distributed with the launcher; keep out of the public tree as the upscaler already is (check `docs/DISTRIBUTION.md`).

## 7. What a game run must check (not run yet)

- Output frame rate counter: the presented rate (generated plus real) separately from the real rate; expect about 2x real. Log `GetLastPresentCount` vs flips.
- HUD: speedometer, boost bar, minimap and text stable and not warped, and with RSX_FRAMEGEN off identical to now.
- Artifacts at cuts: race start camera, replays, track intros, menus to race transitions (`reset` set), loading screens, no streaks.
- Camera-shake behaviour: crashes and boost shake, no extra judder or double-image.
- Latency: compare input-to-photon (or at least frame time) with FG off.
- Frame pacing: frame-time histogram of presented frames (even spacing), the present wait per frame at 45 to 50 Hz, and no regressions in `[sim-pace]` stats.
- Fallback: with the DLL missing, the probe logs and the game still presents through the current path.

## 8. Probe stub (this change)

`vk_fg_probe` in `libs/video/rsx_vulkan_backend.c`, called after the FSR present passes are built. With `RSX_FRAMEGEN=1` it loads the loader and queries the FG swapchain provider for its GPU memory estimate (no context) and logs `FRAMEGEN: provider answered...` or the error code. It does not create the swapchain context because that call destroys and replaces the window swapchain. Not built or run. The probe is not a proof that the 3.1.7 or 4.0.0 provider will be selected on a given GPU.
