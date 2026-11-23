# Noise screen / rainbow menu after several races (stale handle-keyed caches)

User report (exe 9f421113, play settings: Enhanced lighting, GI, dynamic lights, FSR 3.1): after quitting
several races, a new race shows the 3D scene as stippled noise (HUD crisp), and the menu turns rainbow.

## Cause: HYPOTHESIS (strong, code-level; not yet reproduced)

Three caches in the Vulkan backend are keyed by a raw Vulkan handle value and were never cleared when the
image behind the key was destroyed:

- `vk_fx_view` (rsx_vk_scenefx.h): the scene effects' depth-aspect views, keyed by `VkImage`.
- `s_tsr.dview` / `dview_img` (rsx_vulkan_backend.c, `vk_tsr_mv`): FSR 3's motion-vector pass depth view, keyed by `VkImage`.
- `s_tsr.dfb` / `dfb_view` (`vk_tsr_obj_draw`): FSR 3's object-motion framebuffer, keyed by the depth target's `VkImageView`.

NVIDIA hands a new object the value of one just destroyed. When a race unloads, its depth target is
destroyed; when the next race (or the menu) makes a new one with the same value, the lookups match and return
the view of the dead image. FSR 3's motion vectors and the GI/AO/fog/shadow passes then read whatever reuses
that memory (with RSX_VK_MEM_RECYCLE, quickly another image): random motion vectors smear the FSR 3 history
into exactly the stippled look; the state persists until the depth target changes again. Random, hence
"suddenly", after some races. Texture cache, snapshot and reinterpretation paths were read and are not keyed
this way (engine handles are dropped with their objects).

## Fix (ps3recomp-vkgame, uncommitted)

- `libs/video/rsx_vk_stale_keys.h`: `RSX_VK_STALE_KEYS` (default on, `=0` restores the old caches), `RSX_VSK_FORGET`, a ring of destroyed values for the log.
- `rsx_vulkan_backend.c`: `vk_forget_image` from `vk_destroy_image` and `vk_retire_destroy` (where an image is really destroyed) clears the three keys; `[stale-keys]` log lines: keys forgotten, a lookup meeting a recycled value (on), stale hits (off).
- Test: `python tools/test_vk_stale_keys.py` (CC = build/llvm clang): wiring checks + model of the three caches under handle recycling; PASS (forgetting 0 stale answers, keeping 62).

## Build

`py -3 generated/analysis/vehfps/tools/shadow_link.py build/stalekeys-link ps3recomp-vkgame/libs/video/rsx_vulkan_backend.c`
-> `build/stalekeys-link/MotorStormPacificRiftRecomp.exe` sha256 `fc24923c7c8212557c5ef620abda521791217cc23d199fc6e85d059db1b7c82b`
(also includes the other uncommitted edits in rsx_vulkan_backend.c / rsx_vk_scenefx.h at build time).

## Arms (run_vk.py, before Klt5t; exe_sk)

- `Kmr1o`: RSX_VK_STALE_KEYS=0, `Kmr1`: fix on. Launch each with `RUN_VK_RACE_S=480`, driven by
  `py -3 generated/analysis/vksync/tools/multi_race.py <tag> 4 25 2` (blind pause-menu quit; check the auto shots
  in build/shots/<tag> that the quit/restart steps landed; adjust `downs` if the pause menu differs).
- VERIFIED requires: Kmr1o logs `[stale-keys] ... kept for a recycled` and/or noisy shots; Kmr1 logs
  `rebuilt for ... a value a destroyed image had` with clean shots.
