# HDR output (RSX_HDR)

Opt-in HDR present in the Vulkan backend (`ps3recomp-vkgame/libs/video/rsx_vulkan_backend.c`, section "HDR present";
shaders `libs/video/vulkan/rsx_vk_hdr.vert/.frag`, embedded with
`build/vulkan-sdk/Bin/glslangValidator -V --vn rsx_vk_hdr_frag_spv -o rsx_vk_hdr_frag.spv.h rsx_vk_hdr.frag`).
Off unless `RSX_HDR` is set; without it the present is the old SDR blit, unchanged.

## What it does (stage 1)

The game draws its scene into 8-bit targets (main scene 0x00750000 A8R8G8B8, composite 0x01DD0000; only the
luminance/exposure chain is FP16, see `t145/RSX_SHADER_LIGHTING_FIDELITY.md`). Light above SDR white is already
clipped when the frame reaches the present, so stage 1 is SDR-to-HDR:

- swapchain HDR10 (A2B10G10R10, `VK_COLOR_SPACE_HDR10_ST2084_EXT`) or scRGB (FP16, extended sRGB linear), via
  `VK_EXT_swapchain_colorspace`;
- the offscreen target is drawn through a full-screen pass (no blit): decoded with gamma 2.2, SDR white at
  paper-white nits, luminance above the knee stretched to the peak (identity below the knee, slope 1 at it,
  hue kept), then BT.709 to BT.2020 + PQ (HDR10) or linear/80 nits (scRGB);
- peak from DXGI (`IDXGIOutput6::GetDesc1` on the window's monitor; dxgi.dll loaded at run time).

| Variable | Default | Meaning |
|---|---|---|
| `RSX_HDR` | off | `1`/`hdr10`: HDR10; `scrgb`: FP16 scRGB (falls back to the other if the surface lacks it) |
| `RSX_HDR_PAPER` | 200 | nits of SDR white (game UI, ordinary surfaces) |
| `RSX_HDR_PEAK` | monitor peak, else 600 | nits the brightest SDR white is stretched to; `<= PAPER` = no stretch |
| `RSX_HDR_KNEE` | 0.5 | luminance (0..1) where the stretch starts |
| `RSX_HDR_CURVE` | 2.0 | how late the stretch rises (power; higher = only the very brightest) |
| `RSX_HDR_GAMMA` | 2.2 | display gamma of the game's frame |

The HUD is part of the same frame, so white HUD text is stretched too; lower `RSX_HDR_PEAK` or raise
`RSX_HDR_CURVE` if it is too bright.

## Results

- Kk90 (2026-11-06, exe ff7cac19, `tools/add_arm_k90.py`, Kk89 + `RSX_HDR=1`), PARTIAL: log
  `HDR: monitor peak 418 nits (full frame 418), Windows HDR OFF`, `HDR on: HDR10 (PQ, BT.2020), paper white 200
  nits, peak 418 nits`, swapchain format 64 (A2B10G10R10) colour space 1000104008 (HDR10 ST2084). Race drawn
  correctly through the HDR pass (snip chat-pictures d20e251f…: colours, orientation, HUD right). Windows HDR
  was off on the monitor, so the desktop showed Windows' SDR conversion; the HDR look itself is not yet judged.

## Next (stage 2, not started)

Real HDR and tone mapping need the light before it is clipped: promote the scene and composite targets to FP16,
keep the game's shaders from saturating, and replace the game's own output curve with a selectable tone mapper
(one curve for HDR displays up to their peak, one for SDR). HYPOTHESIS until the composite pass (0x01DD0000) and
the scene shaders' output clamp are read.
