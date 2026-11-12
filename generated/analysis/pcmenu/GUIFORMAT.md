## PC menu prep: MotorStorm PR `.gui` page format (2026-11-05, static/offline; no launch, no build, no code change)

Private. Inputs: `generated/analysis/t30/frontend/gui_all/` (232 packs + 14 dev text stubs). Scripts in this folder are read-only, except `edit_demo.py`, which edits in memory only and writes nothing.
Offsets are hex. "B+x" means relative to the page-segment base B. Labels: VERIFIED (checked over all 232 packs, or by exact data match), PARTIAL, HYPOTHESIS. Nothing here has been checked in the running game.

### 1. Pack (`EVOSBIG ` resource pack)
- **Header** (VERIFIED, 232/232): `"EVOSBIG "`, `u32 18`, `"Resource PacK file"`, `u32 dirSize`, `u32 dirOff` (always `0x26`). All values are big-endian.
- **Every section** starts with `"EVOSBIG "` + `id8`. The id is a 16-bit type and a 48-bit value: `0x0001` = directory, `0x0005` = texture, `0x001B` = GUI layout (`<page>.lyt`).
- **Directory section** (VERIFIED): `id8`, `u16 4`, `u16 0`, `u32 0x11111111`, `u32 nEnt`, `u32 nNames(=nEnt)`, `u32 nDepsTotal`, `u32 namesLen`, `u32 pathsLen`, `id8 rootId` (the `.lyt`). Then the names block, the paths block (`M:\assets\...`), the entries, and `u32 0x99999999`.
  - Entry: `id8`, `u32 size`, `u32 fileOff`, `u16 nDeps`, `id8[nDeps]`, `u16 1`, `u32 nameOff`, `u16 1`, `u32 pathOff`.
  - Only the `.lyt` entry has deps. They are its texture ids, and that order is the texture index used by image widgets.
- **Layout** (VERIFIED):
  - Sections tile the file with no gaps and no alignment padding. Physical order differs from entry order.
  - The `.lyt` (page) section is always last (232/232). The page base is often odd-aligned in the file.
- **No checksums.**
  - Ids correlate one-to-one with content over 649 ids: same id means identical bytes, and identical bytes means the same id. `o_button.dds` keeps its id at two different paths (VERIFIED).
  - The hash function is not md5/sha1/sha256/crc32/fnv of the bytes or the name. Whether the game checks or caches by id: HYPOTHESIS. Give modified/new `.lyt` a fresh id and keep the root id, entry id and section id equal.
- **Texture section** (PARTIAL; matches T65): 43-byte header (`u16 2` @+10, `u16 w,h` @+1C, `u16 mips`, `u16 fmt` with `0x0B` = DXT5 and `0x01` = ARGB8, ..., `u32 dataSize`), then raw blocks.
- **Page (`.lyt`) section** (VERIFIED): `id8`, `u16 1`, `u16 0`, `u32 dataSize`, `u32 relocSize`, then data (B = section+0x1C), then the reloc table.
  - Reloc table: `u32` B-relative offsets of every pointer field. Entries are unique, 4-aligned and unsorted. Values are non-zero and in range.
  - Null pointers are 0 and have no reloc entry.
- **Pointer coverage** (VERIFIED, `coverage.py`): a structure walk reaches 159435/159638 reloc entries and finds 0 unrelocated pointers. All 203 unreached entries are in table/spinner class blocks, which are not decoded. Every `options*` page has 100% coverage except `options-audio-soundtrack` (table).
- **Pointer use at runtime: HYPOTHESIS.** The loader probably adds B to each listed field. The fix-up loop was not found in the EBOOT, and `EVOSBIG` is not present there as a string.
- **Consequence:** data can be inserted or appended. Insert: shift every reloc slot ≥ X and every relocated value ≥ X. Append: add objects after the data, then add their reloc entries.
  - Because the page section is last, a grown page only changes its section `dataSize`/`relocSize` and its directory entry `size`.
  - Adding textures would mean editing the directory: counts, name/path blocks, `dirSize`, and every section offset. Reuse a template pack that already holds the textures instead.
  - `edit_demo.py` inserts a 5th Options item in memory. Result: 397 reloc entries, walker clean (0 missing, 0 unreached); edits `0x1F34→0x217C`, `0x5C4→0x634`, entry `0x2514→0x27CC`. This is offline only (PARTIAL).
- **Serialization** (VERIFIED): objects are 4-aligned and written depth-first. Strings are NUL-terminated and padded with `0xFF`. String arrays are packed back-to-back. Strings are not deduplicated.
  - A 0-child array pointer points at the current write cursor. 0 with no reloc is also safe (HYPOTHESIS).

### 2. Page segment
- **Page header** (0x98 bytes; VERIFIED):
  - +00 `nWidgets`, +04 top-level widget array.
  - +08 16, +0C language-name ptr array.
  - +10 5, +14 five `{w,h,w,h}` modes (1280x720 … 640x360).
  - +18 `nChan`, +1C channel array (12 B each: `{name*, nKeys, keys*}`, key = `{f32 value, f32 time}`; FCurves such as `PercentagetoDecimal` = `(0@0, 1@100)` live here too).
  - +20 `nFonts`, +24 font-name ptr array.
  - +28..+6C handler slots. Known: +48 Back, +4C Accept, +50 update, +54 enter, +60 invites check. +28/+34/+40/+44/+58/+5C/+64 are other buttons/exit (PARTIAL).
  - +70.. constants. Copy all of these from a template.
- **Widget record** (0x8C bytes):

| off | meaning | label |
|---|---|---|
| +00 | geo block 0x30: `x, y, sx, sy, ?, ?, rot, vis1, vis2, ?, alpha, colour(-1)` | VERIFIED layout; rot = degrees HYPOTHESIS |
| +04 | second block 0x2C (same layout, all zero transforms; runtime/delta) | copy |
| +08 | style/role: images 9; text 3 = row label, 8 = value, 4 = header title, 5 = menu item / info | PARTIAL |
| +0C/+10 | selectable (1/-1) | VERIFIED |
| +14 | initial focus (exactly 0 or 1 per page, 232/232) | VERIFIED |
| +20 | 1 (283× -1) | ? |
| +2C/+30 | child count / child array (0x8C records, contiguous) | VERIFIED |
| +34,+38 | extra button handlers | PARTIAL |
| +3C | Accept (X) | VERIFIED |
| +40/+44 | GainFocus / LoseFocus | VERIFIED |
| +48/+4C | per-frame Update / Init (page entry) | VERIFIED by content |
| +54/+58/+5C/+60 | **Up / Down / Left / Right** | VERIFIED (L/R = Decrease/IncreaseOption; first/last-item wrap handlers) |
| +64 | class: 0 text, 1 image, 6 spinner, 8 video, 9 menu, 10 table | VERIFIED |
| +6C, +7C, +80 | misc ints/floats | copy |
| +84 | class block | VERIFIED |
| +88 | name (literal; scripts address widgets by it, not unique) | VERIFIED |

- **Class blocks** (VERIFIED):
  - **Text** (0x40): +00 `u32 stringId`, +04 font-name ptr, +08 RGBA colour, then flags/ints. Colours: labels `FFFFFFFF`, values `F7BF13FF` (orange), titles/info `000000FF`. Info box: +28/+2C = 8.9/0.3.
  - **Image** (0x20): +00 texture index into the `.lyt` deps, +04 mask texture index or -1, +0C shader-name ptr (`GUIBasicMasked` for bars; 0 = default), +10/+14 u/v max (= w/2^n, h/2^n), `-1`, `-1`.
  - **Menu**: `{-1,-1,-1}`.
  - **Video**: `{-1,-1}`.
- **Handler** (VERIFIED): `{u32 entryIdx, u32 nActions, u32 0, actions*}`.
  - Action (20 B): `{name*, nArgs, args*(array of string ptrs; numbers are decimal strings), nSucc, succ*(u32 indices, 0xFFFFFFFF = END)}`.
  - Tests branch `[F,T]`. `TestInequality(a,b)` branches `[v≤a, a<v<b, v≥b]`.
- **Coordinates:**
  - [-1,1] screen space, x right, y up. sx/sy are half-extents; a 24×24 arrow is `0.01875×0.0346` at 1280×720. VERIFIED.
  - Image children are offset from the parent, unscaled. The options-audio bar `0.3901-0.0395 = 0.3506` equals the arrows' y. VERIFIED.
  - Text children do not fit the unscaled model. Their offsets look scaled by the parent's half-extent, and text scale is 0.2/0.3556 = 1×. HYPOTHESIS.
  - So clone whole row subtrees and move only the top-level box.

### 3. `options.gui`
- **Menu:** `Options_menu` @B+588 (class 9, `sel 1,1,1`, initial focus, no direction handlers). Children array @B+F88: AUDIO F88, DISPLAY 1014, CONTROLLER 10A0, LANGUAGE 112C.
  - Item y = -0.1235 / -0.2222 / -0.3111 / -0.3951; x ≈ -0.44; rot ≈ 5.6.
  - Each item is a text widget (+08 = 5). Label ids 2924 / 1958 / 2925 / 3540; fonts `kab_plain42/42/41/38` (from the page font list); text scale 0.1/0.178.
- **Item handlers:**
  - Accept: `TransitionPage(options-audio, Undefined)` etc.
  - GainFocus: `PlaySoundEvent(highlight); ScrollTextReset(Info Box 1 text); SetTranslatedText(Info Box 1 text, 2490/3600/3601/3701)`.
  - Update: `MapAnimationChannel(currentWidget, <NAME>_000n_Visibility_Intro, Visibility)`.
  - LANGUAGE Init: `DisplayLanguageSelection` → F: `SetNotSelectable` + `SetInVisible`.
- **Focus** (HYPOTHESIS): the menu moves by child index (all 33 menus are vertical in index order). Wrap needs explicit Up/Down handlers on the first and last items (as pausemenu does). `TransitionPage(Undefined, <widget>)` = move focus (VERIFIED by use).
- **To add a 5th item:**
  1. Make the children array 5 records: insert at B+11B8 (or append a new array and repoint +30), and set count +2C = 5.
  2. Copy the LANGUAGE record. Give it a new geo block (y ≈ -0.48; wreckreation's 5th item is at -0.48), its own text block (new string id), name, Accept `TransitionPage(<newpage>, Undefined)`, GainFocus, and Update reusing `LANGUAGE_0006_Visibility_Intro`.
  3. Add reloc entries.
  4. If LANGUAGE can be hidden, a gap remains. Options: shift via an Init `SetChannelValue(..., translatey)` (HYPOTHESIS), or put the item before LANGUAGE.
  5. Ensure `/gui/<newpage>.gui` resolves through the PSARC VFS. Pages are loaded as `gui/<name>.gui`, and the name must be served or injected at runtime.
- **In-race Options:** the same menu exists in `pausemenu-options` (3 items).

### 4. Option rows
- **Bar row** (options-display / options-audio):
  - Box image → label text (+08 = 3, white, `kab_plain15`) and a focusable bar image: `GUIBasicMasked`, mask tex `MaskRight.dds`, `sel 1,1,x`.
  - Arrows `main_arrow_left/right` are 24×24 images, toggled by `GetSelectedWidgetName` or by GainFocus/LoseFocus.
  - Update: `GetOptionValue(key)` → `MapValueWithFCurve(currentReturnValue, PercentagetoDecimal)` → `SetChannelValue(currentReturnValue, currentWidget, maskLimit)`; `TestIfSelected` → box visibility 1/0.5.
  - Left/Right: `ExecuteFunction(DecreaseOption|IncreaseOption, key)` + an apply function (`SetDisplayOption`, `SetAudioVolume`).
  - Keys are `<chunk>.<key>` from `/data/profile/*.xml`, e.g. `gui.osd.opc`, `audio.vol.sfx`. Step and range are not known (HYPOTHESIS).
- **Text-choice row** (options-controls, best template):
  - Box `Audio_blackbox_plainN` (tex `options_bar_highlight`) with children: label (+08 = 3), N value texts (+08 = 8, orange, only the first is selectable), `main_arrow_right/left`. Rows are spaced 0.1975 in y.
  - Value ids: On 476, Off 651, Low 2157, Medium 3142, High 2156 (from widget names; string table not read, HYPOTHESIS).
  - Init: `GetOptionValue(Options.ControllerPref.Rumble)` → `TestInequality` chain → `SetVisible` one value text, `SetInVisible` the others.
  - Left/Right: same chain + setter (`SetRumbleConfigPref n`).
  - GainFocus: show arrows + info text. LoseFocus: hide arrows.
  - Up/Down are explicit only for wrap; other moves use default navigation, which is not tree order and is probably geometric (HYPOTHESIS). Give every new row explicit Up/Down.
- **Other ways to show text** (VERIFIED in data):
  - One text widget + `TestIfIntsEqual` chain + `SetTranslatedText(currentWidget, id)` (racelobby ambience/privacy).
  - `SetTranslatedText(w, currentReturnValue)` from an id-returning function.
  - `ExecuteFunction(GetXString)` → `SetChannelValue(currentReturnValue, w, text)` (laps, track). This shows arbitrary strings (e.g. "1920x1080") but needs a new registered function.
  - No page sets literal text.
- **Generic setters:** `SetBoolOptionValue(bool,key)`, `GetBoolOptionValue(default,key)`, `SetStringOptionValue(str,key)`, `Increase/DecreaseOption(key)`.
- **SetChannelValue channels:** visibility, text, red/green/blue, colour (packed RGBA int), masklimit, alpha, translatex/y, rotate.

### 5. `.lyt`
- The `.lyt` *is* the page segment above. There is no separate layout file.
- Geometry is float NDC per widget. Fonts are named `<face><px>`, e.g. `kab_plain15` → `USRDIR/GUI/FONTS/KAB_PLAIN.TTF` (PARTIAL), and must be in the page font list (HYPOTHESIS).
- Displayed text is always a numeric string id. Widget names are literal identifiers only.
- New labels need new string ids (string table not located; `global.rpk`/`fonts.rpk` candidates) or the `text`-channel route.

### Scripts
`pack.py` (pack/directory), `packcheck.py`, `idcheck.py`, `idhash.py`, `reloc.py`, `page.py`, `widgets.py` (tree, `full`), `fieldstats.py`, `classblk.py`, `teximg.py`, `texts.py`, `actions.py`, `efuncs.py`/`efuncs.txt`, `chans.py`, `menus.py`, `edgeh.py`, `rowdump.py <page> <widget...>`, `coverage.py`, `edit_demo.py`. Run from this folder, e.g. `py -3 widgets.py ../t30/frontend/gui_all/gui_options.gui full`.
