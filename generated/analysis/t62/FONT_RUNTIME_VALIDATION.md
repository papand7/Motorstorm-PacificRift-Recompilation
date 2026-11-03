# T62: font-fix runtime validation

2026-10-26. One private build, one bounded run. Nothing merged or pushed. No race was entered. Shared worktrees, `port/` and `generated/hdd0|hdd1` are untouched (`generated/hdd1/.../cache.dat` is still sha256 `eaccbe0b…`).

## Result: BLOCKED (inconclusive, not FAIL)

- The run stopped at 17.5 s on `GcKernel::Present() Timeout`. That was before the garage, before any menu, and **before the game rendered a single glyph**.
  - Glyph renders: 0 `cellFontRenderCharGlyphImage` (88BE4799) calls.
  - Surface setups: 0 `cellFontRenderSurfaceInit` (90B9465E) calls.
  - The trace had both hooked.
  - The game did call `cellFont Init()` and `OpenFontFile(kab_plain.ttf)`, at 13.0 s.
- So the fixed code path **never executed** (VERIFIED). This run says nothing about text, for or against.
- The TEX_NOCACHE comparison was not run: its condition ("text absent or partial") was never reached. A baseline rerun is not covered by the authorization, so I stopped.

## 1. Source and baseline

| Item | Value |
|---|---|
| Worktree / branch | `ps3recomp-t62`, `agent/t62-font-validate` (local only) |
| Baseline | `307b08a`. This is the runtime of exe `96d9dee1…` (`build/motorstorm-int-nm-307b08a`), the last exe that reached the garage and main menu (T36, T44). |
| Integration | cherry-pick of T61 `166c973` → `c529ab0`. The patch is byte-identical (both diffs sha256 `29fd57d9…`). Nothing else was applied. |
| Not included | T24-render `ef877b0`, `3579f52`, `419e887` (T61's base). These are not runtime-validated and were deliberately left out. |

Patch review (VERIFIED by code):
- **Memory.** The buffer comes from `sys_heap_memalign`, a bump/bin allocator that returns a guest EA in `VM_HLE_HEAP` `0x50000000–0x58000000`. The VM is flat-backed there, so the guest can access it.
- **Lifetime.** There is one buffer per renderer, reused for every glyph and grown only when a larger surface is needed. It is freed only in `DestroyRenderer` and `cellFontEnd`. The game copies the rows in the same function right after the call (`0x586CF4` → `0x586D90`), so the buffer cannot be freed before the copy. Repeated glyphs do not leak.
- An allocation failure returns `CELL_FONT_ERROR_ALLOCATION_FAILED`.

Unit tests on the T62 tree (`logs/unit/t62/`):
- `test_font_null_surface_atlas` 0 failures;
- `test_font_render_surface`, `test_font_initialize_with_revision`, `test_font_open_file_abi` all pass;
- `test_font_hle_nids.py` 3/3 PASS.

## 2. Build

- Script: `scratch/t62/build_exe.cmd`, log: `scratch/t62/build_exe.log`.
- Toolchain and inputs: clang-cl 23.1.3, Ninja, Release. Same `port/` (sha256 `b27b99b1…`), `generated/ppu-hooked-staging` and SPU inputs as the 307b08a exe. Only `PS3RECOMP_DIR` changed, to `ps3recomp-t62`.
- Build result: 280/280, rc=0.
- Output: `build/motorstorm-t62-font-c529ab0/MotorStormPacificRiftRecomp.exe`, sha256 `162afb4a40fd8dc9f0f0ae60fe30eb0b2ebdb9dc785281a48c3bcd47882ab6b7`.
- Private copy: `t62/exe/`.
- Note: the new exe is 3.7 MB smaller than the 307b08a exe (397,556,736 vs 401,239,040 bytes). Not investigated (PARTIAL).

## 3. Procedure (`run_t62.py`, `t62_trace.cfg`)

- Launcher and snapshot: T44's launcher and private HDD snapshot (`t62/hdd0`, `t62/hdd1`), PAD_FILE input.
- Planned sequence:
  1. Garage +8 s: CROSS, then UP, then CROSS (LeaveGarage).
  2. `mainmenu.gui` +4 s: RSXI capture.
  3. DOWN, DOWN, UP. No menu CROSS.
  4. Stop. Hard caps: garage +75 s, 200 s total.
- Env: T44's set, plus three diagnostic additions:
  - `TEX_SAVE=1` (atlas content per upload);
  - `CELLMARK_DUMP=150`, `EVERY=130`, `MINDRAWS=1` (backbuffer screenshots);
  - a smaller trace config.
- Screenshot note: host-window screenshots were refused by the tool permission policy, and the window is hidden anyway. Screenshots therefore had to come from the renderer's own backbuffer dump.
- Run directory: `generated/runs/20261026-120556-t62-font-validate`. The controller log is in `t62/runtime-20261026-120556/`.

## 4. What happened (logs in `t62/logs/`)

| Host s | Event |
|---|---|
| 0.3 / 1.3 | D3D12 up / PSARC opened |
| 1–12 | Guest flips at about 11/s. T44 ran at about 33/s on the same boot (`run1_heartbeat.txt` vs `t44_heartbeat_first20.txt`). No draw frames. |
| 8.7–13.0 | Frontend pages load: `animations/*`, `festival`, `textureresource`, `blank.gui` |
| 12.17 | **Last RSX heartbeat** (frames=105, draw_frames=0) |
| 13.0 | `cellFont Init`, `OpenFontFile(/dev_hdd1/kab_plain.ttf)` |
| 17.5 | `GcKernel::Present() Timeout` (Last Reference Passed 92) → stop line, process killed, no leftover process |

- No crash or access-violation lines. Only the known `[mfc] REJECTED size=0` and NULL-read noise.
- No frames were dumped (no frame ever had draws). RSXI status stayed `waiting`.

**Cause of the stall: HYPOTHESIS, test-config induced.**
- The last render-thread output is `[TEX_SAVE]`. At kill time, `tex_C1650000_2560x720_rgb.bmp` was left truncated at 3.9 of 5.5 MB in the workspace root (moved to `logs/stray_tex_save/`).
- So the render thread was most likely stuck in the TEX_SAVE per-pixel BMP writer, a diagnostic I added.
- The early 3× lower flip rate is unexplained. It started before any font call, so the font change is not involved. A freshly written 400 MB exe being scanned on first launch is possible but unverified.

## 5. Font result

**BLOCKED.** Glyph positions, sizes, alpha and navigation updates were all unobserved. The TEX_NOCACHE atlas-cache comparison was not applicable.

## 6. Remaining defects

1. Present-timeout early stop in this configuration (above). The T44 baseline also hit a Present timeout, but at about 126 s.
2. Unchanged from T61:
   - stale-atlas risk from the 4-bytes-per-row `tex_csum` (HYPOTHESIS);
   - B8 `0x1000` RGB fringe (cosmetic, T24-owned).

## 7. Recommendation

Authorize **one rerun of the same exe** with the T44 env exactly, keeping only `CELLMARK_DUMP` for screenshots and **dropping `TEX_SAVE`**.

- If text renders through garage, menu and cursor moves, the result is PASS and T63 (first race) can proceed.
- If text is absent or partial, use the already-authorized `TEX_NOCACHE=1` run.

The runner supports this; it needs a one-line env change.

**T63 is not yet unblocked:** the font fix has not been exercised at runtime.

---

# T62B rerun (2026-10-26 12:56): **PARTIAL** — text renders; newly rasterized glyphs can be missing

- Same exe `162afb4a…`, T44 env exactly. `TEX_SAVE` removed. Selective `CELLMARK_DUMP=40/EVERY=200/MINDRAWS=1`. Same trace config.
- Fresh HDD1 copy `hdd1-t62b` (from the shared `generated/hdd1`, `cache.dat` `eaccbe0b…`). Runner mode `launch-b`.
- Run: `generated/runs/20261026-125628-t62b-font-validate`. Controller log, heartbeats and PNGs are in `logs/t62b/`.

| Check | Result |
|---|---|
| Startup FPS | about 32 flips/s from 3 s (T44: 33/s). The run 1 slowdown did not recur (VERIFIED). |
| `GcKernel::Present() Timeout` | 0 occurrences in 51.7 s (VERIFIED). Run 1's stall came from TEX_SAVE. |
| Crashes | none. Exit 1 is the controller's planned `taskkill` after the sequence; no leftover process. |
| Glyph path | `RenderSurfaceInit` and `RenderCharGlyphImage` each called 77 times by menu +4 s, 91 by the end. The counts rise on navigation (VERIFIED). |
| Garage | skipped: boot went straight to `mainmenu.gui` at 37.8 s, as in T44. Garage text was not observed. |
| Main menu (`frame_004`, `frame_006`) | THE FESTIVAL (highlighted, yellow, large), WRECKREATION, GARAGE, OPTIONS, "Select" prompt and the full Festival ticker line are all visible. Positions, sizes and full alpha look correct (VERIFIED by screenshot). |
| Navigation (`frame_005`) | DOWN moved the highlight to WRECKREATION, and the ticker switched to its description (VERIFIED). The final frame shows THE FESTIVAL again, so the second DOWN apparently did not register; the third input was UP. This is an input-timing issue, not a font issue (HYPOTHESIS). |
| Earlier screens | Legal/Havok screen (`frame_003`): all text present. |
| RSXI | capture at menu +4 s, complete (`rsxi/`). |

**Defect (VERIFIED by screenshot, cause HYPOTHESIS):**
- The Wreckreation ticker reads "ccess nline Free lay Split Screen and Time ttac game modes. eader oards are also availa le here."
- Exactly the glyphs first needed at that moment are blank: A, O, P, L, b (and the k in "Attack").
- Glyphs already in the atlas (lowercase letters used by the Festival line) appear.
- This matches the known stale-atlas risk: `vp_upload_tex_slot` checks only columns 0–3 per row, so glyphs added later into an already-uploaded atlas never reach the GPU.
- Not a T61 defect: the glyphs are rasterized (the call counts rise), but the GPU copy is stale.

**Verdict: PARTIAL.** The T61 fix works: NULL-surface glyphs render, and the menu is readable. Glyphs added after the first upload can be missing. The authorized `TEX_NOCACHE=1` run would confirm the cache cause, but it was not run automatically, per the instructions.

**T63:** the menu is readable enough to navigate to a race. Recommend first running the `TEX_NOCACHE=1` comparison (already authorized), then a texture-cache fix (a full-content hash or dirty tracking for B8 atlases) as its own task. Neither blocks a T63 race attempt.
