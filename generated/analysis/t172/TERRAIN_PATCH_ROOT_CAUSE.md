# T172: rectangular terrain patch root cause

Source: ps3recomp worktree `ps3recomp-t172`, branch `agent/t172-terrain-patch-fidelity`, base `b282e26` (T171 WPOS correction preserved). **Changes uncommitted.** Offline only: no build, launch, merge or push. Evidence is existing private T165, T169 and T171 captures.

## Result

The patches are **two defects from one draw family**, not one.

| Class | Appearance | Status |
|---|---|---|
| 1. Large faint polygons, including over sky | translucent quads and wedges on sand and sky, such as VB's sky rectangle at 00:02.46 | **Cause VERIFIED. Correction is opt-in and unverified in game** |
| 2. Small dark squares on sand | about 25 px tiles near the rider, such as 725-751 × 287-308 in T171 arm A | **Cause NOT identified.** Same draws, but survives `RSX_DEPTH_STATE=1` |

WPOS is ruled out: both classes appear with the correction on and off, and fp `0x022C20C1` doesn't read WPOS.

## First affected RSX operation

| Frame | Ops | First FIFO offset | Clean surface | First defective surface |
|---|---|---|---|---|
| T171 arm A `f005564` | 1888-1899 (12 draws) | `0x00250180` | `snap04` op 1887 | `snap05` op 1899 |
| T169 D1 `f005110` | 1113-1142 (30 draws) | `0x00253084` | `snap05` op 1112 | `snap06` op 1142 |

The dark squares and polygons are absent from the clean surface and present in the next one, with no other draw in between. So they arise in **intermediate rendering on `0x00750000`**, not in terrain geometry or final compositing. Snapshots cover the op range only, so the individual box can't be named.

## Responsible draws: fp `0x022C20C1`, vs `0xC163B50D`

Unit cube (8 vertices, 18 indices, a0 in [-1, 1], index local `0x0826CB80`), one draw per box, target `0x00750000`, viewport 1272×715.

| State | Guest (VERIFIED, RSXI) | Host default (VERIFIED, source) |
|---|---|---|
| Cull | front faces (`0x0404`), so back faces draw | honoured |
| Depth | test on, **GREATER, writes off** | **LEQUAL, writes on** |
| Zeta bound | **`0x00ED0000`** | **shared buffer, empty**: the draw samples its own zeta, so `want_z = -1` |
| Stencil | NOTEQUAL, ref per box (3, 5, 8, 7, ... 2, 2), mask 255 | none |
| Blend | on, key `0x0122418B` | honoured |

The shader rebuilds position from unit 0 (`0x00ED0000` read as A8R8G8B8, `zeta_as_color`), projects it, and outputs alpha = 1 − unit 1 byte. Unit 1 is one of four small B8 textures: `0x0826CC00`, `0x08CEE380`, `0x0944A600` (16×16), `0x0A142300` (8×8). Remap `0xA9FF`, clamp to edge, linear filter. What these boxes represent in the game is a HYPOTHESIS: per-vehicle projected shadows.

## Class 1: root cause

With the guest's state, a back face passes only where the scene lies in front of it, so sky at the far plane never passes. The host instead tests against an empty shared buffer: every back face passes, sky included, and its depth writes then reject later boxes behind it.

Evidence:
- **Source:** `rsx_d3d12_backend.c` zeta selection falls back to the shared buffer. Its own comment on `zeta_sampled_only_as_color` says this fallback "tested them against nothing".
- **Pixels (arm A, op 1887 → 1899):** a sky band is scaled by 0.957 with offset 0 and correlation 1.000, so a volume is shading sky, which guest state forbids. Ground left: 0.88, correlation 0.997.
- **A/B (T169, same exe family):** VB (`RSX_DEPTH_STATE=0`) shows the sky rectangle at 00:02.46; VA (`=1`) at 00:02.39 doesn't. The clocks differ by 0.07 s and the camera differs.

### Correction (opt-in, not default)

`RSX_DEPTH_VOLUME=1`: draws with a read-only GREATER or GEQUAL test (`rsx_ds_is_volume`) keep their zeta bound and the guest depth/stencil key. All other draws stay as they are, which is what separates this from `RSX_DEPTH_STATE=1` and its vehicle speckle. It is generic state selection, with no shader or terrain rule. The effective log line gains `depth_volume=%d`. No per-draw copies: the zeta colour image is rebuilt only after other draws may have written depth.

Limit: without `RSX_DEPTH_STATE` the opaque draws don't write stencil, so NOTEQUAL always passes and a vehicle's box also shades that vehicle. A ref of 0 would reject everything; no captured box uses 0.

## Class 2: not explained

**Earlier theory rejected:** I first attributed all patches to depth state. VA, with guest depth and stencil, still shows the dark square, so that can't be the whole cause.

Measured: one square fits after = 0.74 × before, offset about 0, correlation 0.93, which means near-uniform black at alpha about 0.26. The other fit is unreliable (r about 0.4) because the rider's fragments overlap it. Edges are sharp, with no visible linear-filter ramp.

| Candidate | Evidence | Status |
|---|---|---|
| Unit 1 contents flat or wrong (bad deswizzle, stale, edge texel not transparent) | Alpha is flat over the tile. Contents were never captured; the `csum` field reads 0 for every upload, so it says nothing. Host replication of B8 to all channels matches the remap for `.z` | HYPOTHESIS, leading |
| Rebuilt depth wrong (zeta read as colour), so projection clamps to one edge texel | Byte order and exact conversion exist behind `RSX_ZETA_EXACT`; arm A and VA had it on. Not checked against real values | HYPOTHESIS |
| Host window mismatch, zeta 1280 wide against guest 2544 | About 0.6 % scale at most; too small to explain a flat tile | Unlikely |
| Feedback loop | Unit 2 is bound but this shader doesn't sample it | Ruled out for this draw |
| Texture reinterpretation | `RSX_RT_REINTERP` concerns velocity and fp `0x022C20C1` doesn't use it | Ruled out |
| Real PS3 appearance | No PS3 reference exists | Cannot be excluded |

## Other checks

- **Viewport and scissor:** 0,0,1272,715 on a 1280×720 target, matching the frame's other main-pass draws. No mismatch found.
- **Alpha test:** off (`0x000700`).
- **Terrain geometry:** terrain draws are complete before the clean surface, so geometry isn't where the patches arise.

## Offline regression tests

`tools/test_t172_volume.py` → `libs/video/tests/test_t172_volume_warp.c`: **22 checks, 0 failures**, WARP with the debug layer. Hand-built from the verified state, not the game's ucode, and it doesn't exercise the backend's zeta binding path.

| Arm | Sky layers | Terrain layers | Shows |
|---|---|---|---|
| Guest state | 0 | 2 | reference |
| Host default | 1 | 1 | defect reproduced |
| LEQUAL on real zeta | 2 | 0 | inverted, control |
| Volume in front of terrain | 0 | 0 | control |
| Blending off | 0 | opaque | control |

Also: `rsx_ds_is_volume` selection and decode. `test_depth_state`, `test_stencil_exact`, `test_shader_window`, `test_t171_track`, `test_t169_visual`: 0 failures, with the first two's text pins moved to the new code. The backend passes a clang-cl syntax check with the T171 build's includes. Full suite and WARP results: see the end of this report.

## Remaining uncertainties

- Class 2 cause, as above.
- Whether `RSX_DEPTH_VOLUME=1` works in game or disturbs anything else there. In the 5 captures with draw records (T171 A and B, D1, F1, B3) its condition selects only fp `0x022C20C1`: 12, 0, 30, 26 and 15 draws, with no box ref of 0. Those captures stop at about 2,043 draws, so draws after that are unseen, and they don't cover every scene.
- Box identity: c256-c267 were not recorded (the RSXI constant limit was 48), so box silhouettes couldn't be matched to patch pixels.
- Depth written by other draws is still the forced default, so even a correctly bound test compares against an imperfect zeta.

## Runtime capture requirements (requested, not authorized)

**Build:** a new game build of this tree is required first. No build has been made, so there is no exe hash yet. The request should name the SHA-256 and the commit once built.

| Item | Request |
|---|---|
| Launches | 2, same exe, sequential, no retries, idle machine |
| Arm A | `RSX_DEPTH_VOLUME=0` |
| Arm B | `RSX_DEPTH_VOLUME=1` |
| Base flags | T171 arm B set (`RSX_SHADER_WINDOW=1`, `RSX_DEPTH_STATE=0`) |
| Route | same automatic route and vehicle as T171, fresh private HDD, no manual driving |
| Cap | 205 s game, 210 s host, stop at race entry + 45 s, 4 s watchdog unchanged |
| Capture | `RSXI_NEED_FP`-style targeting isn't in this tree, so use `RSXI_MINDRAWS=700`, `RSXI_MAX_EVENTS=4096`, `RSXI_VP_CONSTS=512` only if it stays under the watchdog, `RSXI_UNITS=0002` for unit 1, `RSXI_SNAP=textures` for the 16×16 B8 contents |

Stop on: effective-line mismatch, watchdog, crash, PSO failure, session change.

Expected evidence:
1. Sky unshaded in arm B, and large polygons gone at matched race clocks.
2. Dark squares: present or gone, with their cause isolated by unit 1 texture contents and box constants.
3. No vehicle speckle or new debug-layer messages.

The capture configuration above trades risk against the watchdog, and may need trimming: `RSXI_SNAP=textures` and pass snapshots are alternatives, not both, so one launch can't provide both without code changes. Class 2 needs per-box surfaces, which likely means a small RSXI addition.

## Full suite and WARP results

WARP list: **0 failed**. Full suite: PASS 122, FAIL 4, SKIP 43, TIMEOUT 0.

| Failure | Cause | Status |
|---|---|---|
| `test_d3d12_depth_state` | Caused by this change: its harness lifts `dr_depth_key` and had no `dr_volume` stub | **Fixed.** Rerun alone with the compiler: 0 failures. `test_t172_volume`, `test_depth_state`, `test_stencil_exact` rerun after the fix: 0 failures |
| `test_rt_pool_srv_layout`, `test_vpc_watch` | Inherited: also fail in the T169 baseline and T171 | Not addressed |
| `test_spurs_kick_wake` | Passed in T171. Compares medians of bimodal wake-off latency (48, 13867, 49, 52 us this run); no SPURS code changed here | Known flaky, not rerun |

The full suite was not repeated after the stub fix. `scratch/ppu_conformance.cpp` and `ppu_conformance_run.bat` show as modified only because `test_ppu_lift.py` rewrites them during the suite; they aren't part of this change.
