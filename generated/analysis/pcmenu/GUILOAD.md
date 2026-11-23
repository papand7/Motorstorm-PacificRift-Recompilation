## pcmenu: GUI page load path, loose files, override hook (2026-11-05, static only; no launch, no build, no code change)

Private. Helpers in this folder: `tdis.py` (TOC-aware disassembler), `strrefs.py`, `strxref.py`, `tocrefs.py`, `xref.py` (bl xrefs, cache `_bl.pkl`), dumps `dis_*.txt`. Never stage.

### 1. Page name -> bytes in guest memory

Chain (all VERIFIED statically unless marked):

| Step | Address | What |
|---|---|---|
| a | `0x1F7560` GUI update (per frame; called from `0x814A8`, `0x81664`) | For each queued page name: copies `".gui"` onto the name (`0x1F85F4..0x1F8678`), calls the page loader `0x1F5658`. The resident check uses `sprintf("gui/%s.gui")` (`0x1F8084`, `0x1F81E4`) against `page+0xC`. Link from `PushPage`/`TransitionPage` actions (names registered at `0x5C8274..0x5C8314`) to this queue: PARTIAL. |
| a' | `0x1F6CC8(gui, name, rs)` | Initial/config page. Called from `ApplyConfigLoadGUI` `0x752EC` (in `0x727B0`) with `cfg+0x2755`, the `SetConfigGUIPage` name, e.g. `mainmenu.gui`. It strdups the name, pushes it to a vector (`0x828838`) and calls `0x1F5658`. |
| b | `0x1F5658(gui, idx, &names, rs)` page loader | `0x1F5C5C`: `std::string("gui/") + names[idx]` gives `gui/options-display.gui` (string at `sp+0xA0`). `0x1F5CC8`: `new` 0x7C page (strings `+0xC/+0x28/+0x44`, handle `+0x60`, texture-handle vector `+0x64`, screen `+0x74`, flag `+0x78`). |
| c | `0x1F5DA8: bl 0x752C98` | Stub (TOC switch to `0x10AFBE4`) to `0x536A30` `ResourceSystem::LoadSync(rs=r3, &handle=r4, path=r5)`. **This is the only file load for a page.** |
| d | `0x536A30` | `0x5318F8(rs, out, path)` issues the request, then polls `0x5346A8(rs)` with `0x756978(1)` (`0x438960`, syscall 141 `sys_timer_usleep`) until idle: synchronous. |
| e | `0x5318F8` | Copies and lowercases the path (`0x757738` -> `0x3C3838`, `tolower` per char). Searches a name list at `[rs+0xC]+0x98..` (0x24-byte entries, compare `0x5F2DB8`): if found, reuses it (`0x530F10`); otherwise queues a new request. The name-keyed reuse is PARTIAL. |
| f | `0x52F300` area (`0x52F414/4AC/588`) | Opens the resource file via `0x756858` -> `0x3BC470` `FS::Open`, which calls `[0x1282340]->vtbl+8`. Path transform `0x52E800`: with no sub-resource (r5=0) the path is used as-is. Only sub-streams get `path_TYPE.evo` (type table `0x1032760`). |
| g | `0x534xxx..0x5357xx` async load state machine (loader `[r25]`) | Reads the first 200 bytes into `+0xA8`. `"EVOS"`+`"BIG "` at `+0xA8/+0xAC` (memcmp `0x535248`/`0x5354E4` = endianness). Header parsed by `0x547E28`/`0x5470B8`; needed size is taken from the header. **Buffer:** if prealloc capacity `+0x170` < size, `malloc(size)` (`0x756678` -> `0x704CE0`) to `+0x68`; else prealloc `+0x174`. The rest is read through the reader `+0x194` vtbl+0x10. No fixed GUI buffer (VERIFIED). Exact EVOSBIG size-field semantics not decoded (outer "Resource PacK file" wrapping an inner info block; HYPOTHESIS). |
| h | back in `0x1F5658` | `0x1F5DDC` handle to `page+0x60`. `0x1F5E24` `0x8E6340`: `data=[handle+0x40]` (relocated pack root). `0x1F5E34` `alloc(0xDC)` (`0x752018`->`0x58A428`), `0x753578`->`0x5BF6D0` GUI screen ctor(data), stored at `page+0x74`. `0x1F5EB8` pushes the page into `gui+0x54` (vector `+0x58..+0x5C`). `0x1F5F20` `page+0xC = "gui/<name>.gui"`. |

- What 0x785C68 and 0x1E89E0 do (VERIFIED): `0x785C68` is `std::string(const char*)` (strlen `0x751B48`, grow `0x758D78`, memcpy `0x751AD8`). `0x1E89E0(gui, std::string*)` scans the resident pages `gui+0x58` backwards comparing `page+0xC` and returns an index or -1. It is a page lookup, not a hash or archive lookup. `0x1F0340` (delegate `0x77D1B8`) uses it to attach `gui/textureresources/%s.rpk` (load `0x752838`->`0x5339C8`) to `page+0x64`. Property setters `0x1ECB48..0x1EEE9C` use `"gui/%s"` the same way.
- Preload: none (VERIFIED). No page list in the EBOOT or the PSARC (only `gui/text_*.lang`, `text_langs.list`). Pages load on demand at page entry; resident pages are reused by name. Pages are unloaded via `0x1F44C8` from the update (HYPOTHESIS).
- Archive index: the FIOS dearchiver (`0x64E950..0x657xxx`; lookupCache, manifest) calls the MD5 helpers at `0x66DC78..` (init `0x67452301` at `0x66F8D8`). The standard PSARC lookup is MD5 of the path: HYPOTHESIS.

### 2. Loose files and the port file layer

- Game config `0x10D5290` (`PROD12345__`). `+0x20` defaults to `/app_home/overrides`, but `0x6B4F0` overwrites it with `cellGameContentPermit` usrdirPath (`/dev_bdvd/PS3_GAME/USRDIR`). The `/app_home/overrides/` strings at `0xE1F560` and `0x10D52B0` have no code reference (scan of all four TOCs, `addi`/`lwz`, raw pointers). There is no retail override directory (VERIFIED static).
- FS singleton `[0x1282340]` (`0x3BC598`): `FIOSFileSystem` 0x3000 B, ctor `0x3C1618(obj, cfg, usrdir)`, vtable `0x103DA58` (+8 Open `0x3C1C38`, +0xC Exists `0x3C2090`). Stack: scheduler `0x662C00` -> ramcache `0x6577F8` -> dearchiver(".psarc") `0x658BB0` -> schedulercache (`/fios` cache.dat, `0x3C0C58`) -> ps3media `0x66AD08`. `0x6B5CC` opens `ms2.psarc`, which mounts it.
- Open/Exists lowercase the path (`0x3C1D04`, `0x3C2164`). Then they call fios open/stat (`0x755518`->`0x6649D0`, `0x755528`->`0x6644C8`).
- Archive-first, loose fallback: PARTIAL. Run logs show `[fs] open FAIL` only for names absent from MS2.PSARC (`data/events/light_fantastic.race`, `audio/atvsmall_player.vsb`, lowercased `audio/dspsettings/...`), as `/dev_bdvd/PS3_GAME/USRDIR/<rel>`. There are no FAIL lines for archive members. ps3media's cellFsOpen sites are `0x666978` and `0x66855C`. To confirm, run with `FS_CALLER=1` and expect `(by 00666978|0066855C)`.
- Direct cellFsOpen elsewhere: fonts `0x5842F8` (`/gui/fonts/*.ttf` -> disc `USRDIR/GUI/FONTS`), saves `0x11830`, edat `0x3C313C`, flashMP3 `0x717DF8`.
- Port: `ps3recomp-vkgame/runtime/ppu/ppu_fs.cpp`. `host_path()` (l.134) strips `/dev_bdvd/` and appends to `ppu_vfs_root` (`PS3_VFS_ROOT`, the directory with PS3_GAME), so `MS2.PSARC` is a plain host file read by the guest FIOS/dearchiver. `PS3_HDD0_ROOT`/`PS3_HDD1_ROOT` (cache.dat) remap `/dev_hdd0`/`/dev_hdd1`. Open/Stat/Opendir/Mkdir all use `host_path`.

### 3. Hook points for options-pc.gui / modified options.gui

- New page, not in the archive: if the fallback holds, `PushPage("options-pc")` loads `USRDIR/gui/options-pc.gui` with no guest change. To keep `original/` untouched, add an overlay root checked first in `host_path` (e.g. `PS3_GUI_OVERLAY`). New text IDs would also need `gui/text_*.lang`, which are archive members, so they fall under the next point.
- Replacing an archive member: the archive wins, so redirect the path before the FIOS open. **Best: `FIOSFileSystem::Open` `0x3C1C38` after lowercasing at `0x3C1D04`** (local `std::string` at `sp+0x74`, data `sp+0x78` or `[sp+0x78]`), plus Exists `0x3C2090` after `0x3C2198`. If the host overlay has the path, rewrite it in place to a same-length archive-miss alias (e.g. `gui/` -> `gu~/`) that `host_path` maps to the overlay. The rewrite is local, so ResourceSystem keys and `page+0xC` are unaffected. It covers pages, `gui/textureresources/*.rpk` and `.lang`. Implement as an anchored lifted-code edit, like `vksync/tools/mspr_patch_lifted.py`.
- GUI-only alternative: `0x1F5DA8` (r5 = path). The same `std::string` (`sp+0xA0`) is copied to `page+0xC` at `0x1F5F20`, so restore it after the call or pass a separate guest buffer.
- Avoid:
  - Patching MS2.PSARC bytes: schedulercache `cache.dat` and ramcache hold archive blocks, plus TOC/zlib tables.
  - Patching after load: the pack is relocated in place and cannot grow.
- Limits:
  - No fixed page buffer; size comes from the header. Existing pages run up to `mainmenu.gui` 4.1 MB and `options-audio-soundtrack.gui` 1.0 MB through the same path.
  - Name buffers are 256 B (`0x1ECCB4` memset 0x100; `0x1F0340` sprintf into `sp+0x90`/`sp+0x190`).
  - Heap and RSX headroom for extra textures were not measured (HYPOTHESIS).
  - Resources still resident are reused without a reload.

### Evidence commands (from this folder)
`py -3 tdis.py 1F5C58 1F5F60` · `py -3 tdis.py 536A30 536AB4` · `py -3 tdis.py 5318F8 531A80` · `py -3 tdis.py 535228 535380` · `py -3 tdis.py 53560C 535624` · `py -3 tdis.py 3C1C38 3C1D60` · `py -3 tdis.py 3C1870 3C19B0` · `py -3 tdis.py 6B498 6B5F0` · `py -3 tdis.py 785C68 785D40` · `py -3 tdis.py 1E89E0 1E8B68` · `py -3 xref.py callers 752C98 1F5658` · `py -3 strxref.py e1f560 10d52b0 df72e8` · `py -3 strrefs.py 52D000 540000` · `grep -a "open FAIL" ../drawcap/ab/runtime-d1-20261103-203822/controller.log`
