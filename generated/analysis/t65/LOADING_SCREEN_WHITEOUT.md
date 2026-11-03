# T65: race loading screen whiteout

2026-10-26. Offline only: no launch, no build, no merge, no push. No worktree was modified. No TEX_SAVE.

## Result: **PASS. Classification A.** The original fade-in has no clamp, and it stays on screen because LoadRace never finishes.

- The whiteout is the game's own 2-second fade-in, computed with no clamp: `gain = 0.5 · t`, where t is the number of seconds since the loading screen started.
- Our renderer reproduces it faithfully.
- The screen only disappears when the race loader returns from `LoadRace`. That makes the brightness a direct readout of how long LoadRace has run, which is T64's issue.
- **No renderer defect was found. No correction is justified.** Clamping would change original semantics.

## 1. Original rendering path (VERIFIED, EBOOT sha256 `bbb7fe25…`, `logs/disasm_*.txt`)

| Address | What |
|---|---|
| `0x8EA00` race loader | `bl 0x329660` start loading screen (`0x8EA64`) → `bl 0x89230` **LoadRace** (`0x8EA88`) → … → `bl 0x329D90` stop (`0x8EE88`; `0x8F0A4` on the unwind path) |
| `0x329660` / `0x329D90` | start: `stb 0 → [obj]`, then creates `AsyncRenderThread`; stop: `stb 1 → [obj]`, then joins the thread |
| `0x329048` loop (on that thread) | `start = time()` once; each iteration: `sys_timer_usleep(30000)`; `t = time() − start`; then the uploads below |
| | `c55 = (t, [obj+0x5E0], [obj+0x5E4], 0)` (`li r4,0x37`) |
| | `c59 = (0, 0, 0, 1.0 + (−0.5)·t)`: `fmadds f31,f31,f0,f29` at `0x3291CC`; TOC `+0x3D88` = 1.0, `+0x3D8C` = −0.5 |
| | colour clear to 0 (`0x1D90`/`0x1D94` mask `0xF0`), viewport, scissor, then the draws via vtable `+0x14` |
| `0x4361B0` | `time()` = `sys_time_get_system_time` (stub `0xCC011C`) × 1e-6, i.e. wall-clock seconds |
| `0x7351E0` | raw `SET_TRANSFORM_CONSTANT_LOAD` (`0x1EFC`) upload, no processing |

- **No clamp and no exit on t.** The loop contains no `fsel`, `fcmpu` or `fcmpo`. Its only exit is the stop flag.
- **No intentional white transition and no fade-out.** The term starts at black (w = 1), reaches the unmodified artwork at t = 2 s (w = 0), and then keeps extrapolating past it.
- **The loop keeps updating while LoadRace is blocked.** It runs on its own thread, so it does not wait on the loader, and the loader does not wait on it.
- The garage loader (`0x8D9F0`) and four other loaders (`0x706B8`, `0x82188`, `0x37020`, `0x60D70`) use the same screen. This is the same mechanism as the earlier garage and boot whiteouts (`whiteout/FINDINGS.md`, `docs/LOADING_SCREEN_FADE_TRACE.md`).

## 2. Assets and shaders (VERIFIED: T63 RSXI frame 6287, `shaders/`)

| Op | Programs | Texture | Role |
|---|---|---|---|
| 0 | vp `FF398E97` / fp `02537E81` | `0x0527D280` 1280×720, fmt `0xA8` | controls artwork |
| 1 | vp `F69565E0` / fp `02538941` | `0x0517D280` 1024², fmt `0x88` | animated emblem sprite sheet (frame index from `c55.x`) |
| 2 | vp `FF398E97` / fp `02537E81` | `0x04E88580` 2048×1024, B8 | text (glyph atlas) |

- **Vertex programs:** `o[8]` (TEX1) = `c[59]`. The texcoord interpolant is unclamped.
- **Both fragment programs:** `h0.xyz = tc1.w·(tc1.rgb − X) + X` with `tc1.rgb = 0`, so the output is `X·(1 − w) = X · 0.5t`.
  - No saturate anywhere on that path.
  - The registers are FP16, so neither the hardware nor the translation clamps the value below the 8-bit target.
- **Render state:** all three draws go to the display target (rt 0, fmt 328, 8-bit). Blend `0x0122418B` is straight alpha and was verified earlier.
  - No FP16 target, exposure, tone-map or post-FX pass is involved.

## 3. T63 timeline (`logs/gain_timeline_ref058.txt`, `logs/gain_fit.txt`)

- **Inputs:** the 24-bit backbuffer dumps.
  - The screen is drawn straight to the 8-bit display, so these are the presented bytes; no FP16 data exists to lose.
  - The decisive evidence, though, is the RSXI constants, not the image files.
- **Before the race load (frames 046–057, up to 122.9 s):** normal menu brightness. No whiteout before the race loading transition.
- **Ramp:** gain relative to frame 058 rises **linearly**: 1.0 → 1.7 → 2.4 → … → 31.5 at 204.5 s (40 points).
  - Fitted start: **host 121.82 s**. This matches `loadscreen-popup` (121.81 s) and the LoadRace start (121.5 s).
  - Implied rate: 0.55 gain/s, against 0.5 in the original code. The difference is the timing error of dump file mtimes.
- **Shape:** progressive, not abrupt. The fade-in from black completes at about 123.8 s; frame 058 (124.7 s, screenshot `08`) is already at about 1.3× its true brightness.
- **RSXI frame 6287 (≈ 204.9 s), exact:**
  - `c55.x = 82.8755 s`;
  - `c59.w = −40.4377 = 1 − 0.5 · 82.8755`;
  - **gain 41.4**.
- **Final frames:** 70 % of pixels are saturated white. They are not uniform: black text and the controller outline stay visible (black × gain = black), and dark detail clips toward orange or red. This is the signature of a pure multiplicative gain.

## 4. Original versus implemented semantics

| Stage | Original | Port | Status |
|---|---|---|---|
| Fade term | `1 − 0.5·t`, unclamped | same values reach the RSX (`c59.w = 1 − 0.5·c55.x` in every draw) | VERIFIED |
| Time base | `sys_time_get_system_time` µs | wall-clock rate matches (fitted start = page load) | VERIFIED |
| VP/FP math | lerp to `tc1.rgb` by `tc1.w`, FP16, no saturate | same HLSL; gain matches earlier captures to 0.1 % | VERIFIED |
| Blend | straight alpha | `0x0122418B` = straight alpha | VERIFIED (earlier tests) |
| Clear | colour clear 0 each frame | display clear → frame-start `ClearRenderTargetView(clear_color)` (`rsx_d3d12_backend.c:7770`, `:6568`); RSXI `clears` counts only offscreen clears | VERIFIED (code) |
| Accumulation | none | refuted by the exact gain law | VERIFIED |
| B (overlay opacity/blend), C (HDR/exposure), D (sampling), E (clear/composition) | — | each excluded by the rows above | VERIFIED |

**Earliest divergence:** none in rendering. The only difference is how long the screen stays up, i.e. LoadRace has run more than 83 s.

## 5. Confirmed versus open

- **VERIFIED:** all of §1–4.
- **HYPOTHESIS (not decidable offline):** on PS3 the same code brightens the screen as `0.5 · duration`. Either retail loads end within a few seconds of the fade completing, or long PS3 loads wash out too.
  - Deciding this needs a hardware or RPCS3 reference of race-load duration. It is not needed to classify this symptom.

## 6. Correction and capture plan

- **No fix.** Clamping `c59.w`, changing the shaders, or changing the timing would alter original semantics. Shortening LoadRace (T64) removes the symptom.
- **No new capture is required.** For free confirmation in T64's next run, add `RSX_VPC_WATCH=59`, an existing opt-in with no renderer change.
  - The w value at loading-screen exit gives the loading-screen lifetime directly: `(1 − w) / 0.5` s.

## 7. Regression check

`tools/check_fade_semantics.py` (private, offline): **18 PASS, 0 FAIL** (`logs/check_fade_semantics.log`). It pins:
- the EBOOT fade instructions, constants, time base and the absence of a clamp;
- the race-loader bracket around LoadRace;
- `c59.w = 1 − 0.5·c55.x` on all three draws of f6287;
- display target and blend state;
- the shaders' unsaturated `tc1` lerp.

A clamped model contradicts the captured `w` (−40.44 vs 0). The renderer is unchanged, so no other path changed.

## 8. Dependency on T64

- **Direct, one-way:** the whiteout ends only when `0x8EA00` passes `LoadRace` and reaches `0x8EE88`.
- The loading-screen thread neither blocks nor feeds LoadRace (30 ms sleeps, own thread).
- **Use for T64:** `c55.x` is a free, exact loading-screen timer for its runs.

## Track Selection Thumbnail Rendering

**Result: not a rendering defect (VERIFIED from the original asset).**
- The white squares are the game's own `small_ticket_unlocked.dds`: a plain white card with a dark frame and hanger tab. The renderer draws it correctly.
- **No correction.**

### Evidence

| Item | Evidence | Status |
|---|---|---|
| Page and resources | `ticket-select-earthzone.gui` handler `+0x190` runs `LoadGUIImageResource(guitickets, …)`; the icon row is spinner `Earth Ticket Icons`, filled by `PopulateGUITicketIcons` | VERIFIED |
| Asset | `MS2.PSARC:/gui/textureresources/guitickets.rpk`, a private copy in `assets/`; 129 texture resources | VERIFIED |
| Icon textures | resources 97/98/99 = `small_ticket_locked` / `_raced` / `_unlocked`: 80×92 DXT5, 43-byte header + 20×23 blocks (7403 B each) | VERIFIED (sizes exact) |
| Original pixels | decoded with `tools/rpk_dxt5.py` → `assets/png/`; `logs/guitickets_icons.txt` | VERIFIED |
| | **locked:** grey padlock card | |
| | **raced:** helmet card | |
| | **unlocked:** opaque white card in a dark frame (13.3 % of the texels are opaque white; the rest is the frame and transparent margin) | |
| Screenshot | T63 `05` crop (`assets/png/t63_05_icons_crop_x4.png`) next to the decoded icons (`icons_on_grey_x3.png`): the same frame, hanger tab, white face and padlock detail | VERIFIED (visual match to raw asset pixels) |
| Selection | EBOOT strings `small_ticket_locked/raced/unlocked` (`0xDF8480…`, TOC `−0x4DA4…−0x4D9C`) are loaded by the icon code at `0x68D38–0x692EC` (plus 4 other sites) | VERIFIED (references) |
| State mapping | tickets 1–2 are unlocked and not yet raced (fresh profile, `t63/hdd0` empty), the others locked → 2 white cards + 22 padlocks, as shown | INFERRED (names; branch conditions not decoded) |

### Answers to the investigation points

- **Intended texture:** `small_ticket_unlocked`, for unlocked tickets that have not been raced.
- **Bound texture and draw:** unknown. T63 has no RSXI capture of this screen; its only RSXI frame is the loading screen.
  - This doesn't affect the conclusion: the presented pixels equal the original texels.
  - The backend has no white fallback either: an unbound unit gets a null SRV, which samples as 0 (`rsx_d3d12_backend.c:6375`, `:6515`). A missing texture would show as transparent or black, not white.
- **Shared path with the ATV icon and the loading animation:** no defect was found here, so nothing is shared.
  - The ATV thumbnail comes from `guivehiclethumbs.rpk` (`festival_class_atv`); the loading symbol is the 1024² fmt `0x88` sprite sheet (fp `02538941`).
  - Both remain separate, open issues.
- **Optional confirmation, only if wanted:** one RSXI frame on the ticket page. The pass condition is an 80×92 DXT5 texture at the icon draws whose bytes equal resource 99's blocks.

### Regression

No code change, so there is no new test. The decoder and asset listing are reproducible:

```
py -3 -I generated/analysis/t65/tools/rpk_dxt5.py generated/analysis/t65/assets/guitickets.rpk <out> small_ticket
```

(set `MSYS_NO_PATHCONV=1` for `t20_extract_member.py` under Git Bash)
