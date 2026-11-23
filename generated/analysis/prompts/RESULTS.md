## PC key-cap button prompts (2026-11-23; private)

### Mechanism (VERIFIED, offline)
- The PS3 prompt icons are not font glyphs. They are baked into DXT5 GUI textures in the `.gui` packs:
  - icon-only textures (`x_button.dds` 40x40, `start.dds`, `pause_start_button_prompt.dds`, `L1.dds` ...);
  - composites (`x_to_skip_prompt.dds` 500x84 = bar + cross icon; the words "Press" and "to Skip" are separate
    `kab_plain14` text widgets in `gui_osd-main.gui`).
- Evidence: `tools/find_icons.py` decodes them (`icons/*.png`); osd-main's image widget `x_to_skip_prompt` uses
  texture 14; the runtime dump `build/texdump/ms2/500x84_a8_c5d1034028193a87.dds` is byte-identical to the pack's
  `x_to_skip_prompt.dds` blocks, so the engine uploads the pack bytes unchanged (BC3, format 0xA8).
  Consistent with T157: the stale font atlas lost the words of "Press X to Skip" but never the icon.

### Hook
- Framework: `rsx_draw_engine_set_tex_patch(patch, gen)` (libs/video/rsx_draw_engine.{h,c}): probe on upload,
  patch the staging copy per level, skip the texture pack for a patched texture, re-upload a known texture when
  `gen()` changes. Test: `test_texture_host_patch` in libs/video/tests/test_rsx_draw_engine.c (all checks pass,
  `tools/build_engine_test.cmd`).
- `pad_host_device_present()` (libs/input/cellPad.c) for Auto.
- Port: `port-vkgame/pc_prompts.h` (table of 23 textures: size, FNV-1a 64 of level 0, icon centre/size, button;
  procedural key cap + own stroke font; BC3 block decode/encode), wired in `pc_menu.cpp` to the live layout
  `s_layout` (double-buffered, versioned on every rebind) and the `prompts` setting. Test:
  `port-vkgame/tests/test_pc_prompts.c` (`tools/build_prompts_test.cmd`), `tools/preview.py` renders all 23
  (`preview/`): the C hash finds every texture.
- Not covered (left as the original icons): L1/R1 bars on light backgrounds (`L1_R1_prompt_bar*`,
  `Skip_page_prompts`), photo mode `buttons.dds`, gallery arrows, controller diagrams, buttons with no key bound.

### Run
- Exe 6b9ad4b7... (build/motorstorm-vkgame-100-ppucc2), slot `exe_pr1`, arm `Kpr1` (ssr3o settings +
  `MSPR_PROMPTS=keyboard`), shots `build/shots/pr1`. In-game result: UNVERIFIED until Kpr1 runs.

### Kpr2 (after Kpr1: the ENTER cap covered "s" of Press and "t" of "to")
- Kpr1 VERIFIED in game by the coordinator: the cap shows, but 64 px wide it overlapped the text.
- Now the cap is exactly the original icon's rect (table rw x rh: the 35 px ring for the skip prompts), never larger.
  Enter = return arrow, Space = open box, Shift = outlined up arrow; words (CTRL, ESC, BKSP, F12) condensed to
  0.62 width, then scaled down. `tools/preview.py`: 23/23 textures x 7 labels, 0 renders with texels past the rect
  (preview/*.png, scratch/pr2_zoom.png).
- Exe 9a7344e3..., slot exe_pr2, arm Kpr2 (queued after Kst9o).
