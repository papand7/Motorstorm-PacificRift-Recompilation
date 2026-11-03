# T45: MotorStorm menu controls and invisible text

Offline only: no launches, builds, merges or pushes. Sources:
- `ps3recomp-307b08a/libs/input/cellPad.c`
- T36, T41 and T44 logs and RSXI dumps

## 1. Keyboard and controller mapping (VERIFIED, from source)

- The keyboard is used only when no XInput pad is connected (`cellPad.c:509`). T44 logged "keyboard fallback active on port 0".
- Keys are read only while the game window has focus. `PAD_NO_KEYBOARD=1` disables the keyboard.

| PS3 button | Keyboard | XInput pad |
|---|---|---|
| **CROSS** (accept) | **Z** | A |
| **CIRCLE** (back) | **X** | B |
| SQUARE | A | X |
| TRIANGLE | S | Y |
| D-pad | Arrow keys | D-pad |
| L1 / R1 | Q / W | LB / RB |
| L2 / R2 | 1 / 2 (trigger value 255) | LT / RT (threshold) |
| START | Enter | Start |
| SELECT | Tab | Back |
| Left stick | Arrow keys (0/128/255) | Left stick |
| Right stick | **none** (fixed at 128) | Right stick |
| L3 / R3 | **none** | LThumb / RThumb |
| PS | **none** | none |

**Confusing (VERIFIED):**
- The keyboard **X key is CIRCLE (back)**, not CROSS. Use **Z** to accept.
- The arrow keys drive the d-pad and the left stick at the same time.

**Missing on keyboard:** L3, R3, right stick, analog stick magnitude.
- Pressure values are zero on the keyboard path.
- That does not matter here: the game never calls `cellPadSetPortSetting` (none in T36/T44 stdout), so pressure mode is off.
- None of these buttons are needed for menu navigation.

**Proposed correction (optional, not applied):**
- Add `{'C', CELL_PAD_CTRL_L3}` and `{'V', CELL_PAD_CTRL_R3}` to the existing `map[]` in `pad_poll_keyboard`.
- Drive the right stick from I/J/K/L.
- Test: a host unit test that feeds key states through the map and checks the `CELL_PAD_CTRL_*` bits.

## 2. Invisible text

**Text geometry is submitted to RSX; it is not missing (VERIFIED).** Captured frame f004569 (`t41/scratch_b/f4569.txt`):
- Ops 25–31 and op33 sample font atlas `0x04E88580` (2048×1024, format 0xA1 = B8 linear) on u0 and u1.
- Their draw state:
  - fp `02537E81` alternates with fp `022C1C41`.
  - Blend on (`bk 0x0122418B`), colour mask 15.
  - Viewport 1280×720; scissor full, or the 123,637 strip for op33.
  - Vertex counts are glyph-sized (54–876).
- Order: after the background (ops 20–24) and before the icons (ops 34–39). This is the correct UI layer order.
- Icons and bars use the **same fp `02537E81`, blend and viewport/scissor**, and they are visible. That puts the fault in the B8 atlas path, not in blend, scissor, viewport or draw order.

| Candidate | Status |
|---|---|
| Font load / glyph atlas build | cellFont opens the disc fonts and the atlas completes (AGENTS.md). Whether the bytes are non-zero at sample time is **unverified**: the checksum samples only 4 bytes per row. |
| Upload | B8 linear ≥64 KB is snapshotted at record time (`PS3_TEX_SNAPSHOT=1`), so the bytes are captured. VERIFIED by code. |
| Component remap | T41's remap `0x56FF` through `rsx_texture_component_remap` gives RGB = ONE, A = the B8 byte (white glyph, coverage in alpha). This is correct, so the remap is ruled out. VERIFIED by code. The value 0x56FF itself came from T41 (PARTIAL). |
| Shader | fp `02537E81` samples atlas.x on u1 (forced to 1.0 by the remap) and conditionally zeroes `h[3]` through `cc0.w`. The H/R half-register aliasing is emulated with separate `r[]`/`h[]` arrays plus pk2h/up2h. A B8-specific path through this logic could zero the alpha. **HYPOTHESIS.** |
| Atlas contents empty | **HYPOTHESIS**, untested. |

**Remaining question:** the glyph alpha is either 0 in the atlas bytes, or it is zeroed in the shader.

Next step (needs authorization and the renderer owner; no backend edit made):
- One bounded capture that dumps the snapshotted `0x04E88580` bytes and the per-unit CONTROL1 for op25.
- If the bytes are non-zero, test fp `02537E81` offline: feed it a B8 texel and compare against the RSX half-register semantics.
- No colour or alpha tweaks.

## 3. T44 handler reach (VERIFIED, from the existing trace)

Main-menu input reaches the handlers end to end. Detail is in `t44/MAIN_MENU_INPUT_TRACE.md`.
- CIRCLE → `57F450` and `57FA00`.
- CROSS → `57F1A4` (mainmenu → options → options-audio and back).

The problem is invisible text, not input. Correction to T41: **byte 7 = CROSS, byte 6 = CIRCLE** (PARTIAL).
