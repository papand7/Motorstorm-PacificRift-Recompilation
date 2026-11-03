# T179: RSX visual corrections

Status: **PARTIAL. The dark terrain squares are not fixed; their cause is still unknown.** One verified defect (large faint polygons, including over sky) has an opt-in correction, unproven in game. No game was launched. Polygon offset stays off.

Code: branch `agent/t179-rsx-visual-corrections` (`ps3recomp-t179`), base `0eb257f6` (T176, which includes T171). Report: branch `agent/t179-rsx-visual-corrections-report` (`root-t179`).

## 1. Ranked defects

| Rank | Defect | Status |
|---|---|---|
| 1 | Small dark squares on terrain, about 25 px, near the rider | Narrowed to one draw family. Cause open (HYPOTHESES below) |
| 2 | Large faint polygons on sand and sky | Cause VERIFIED. Correction opt-in, fixture-tested only |
| 3 | Horizon dark box, faint patches, shoreline marks (T176 frames) | Not investigated beyond being present with polygon offset on and off |
| 4 | Stencil on the same box draws: opaque draws don't write it in default mode | VERIFIED limitation of the correction, see section 8 |

## 2. Evidence by cause

Dark squares come from the box draws: fp `0x022C20C1`, vs `0xC163B50D`, target `0x00750000`, zeta `0x00ED0000` read as colour (T172, T178). Their alpha is 1 minus the unit 1 byte.

| Cause | Evidence | Result |
|---|---|---|
| Shader translation | T178 replayed the real shaders against an analytic reference | Ruled out, given correct inputs (VERIFIED) |
| Depth reconstruction formula, byte order | T178 matrices; T179 read the shader and `zconv` source | Ruled out (VERIFIED) |
| Swizzled B8 decode, mips, remap | T178 test; `0xA9FF` keeps the source channels, 1 level | Ruled out (VERIFIED) |
| B8 view mapping | Mapping `0x1000` puts the byte in every channel; the shader reads `.z` | Ruled out by source (VERIFIED) |
| Polygon offset | Box draws don't write depth and flat alpha isn't a depth-fight pattern (T178); T176's flag showed no visual improvement | Not supported |
| Feedback, WPOS, RT reinterpretation | T172 | Ruled out |
| Zeta window scale | Guest reads 2500×703 of a 1280×720 surface (up to 2.3 % scale). T171 TA ran with `rt_window=1` and logged windowed zeta, and still shows squares. T165 B1 had no window, so its constants and pixels aren't comparable | Not the cause in TA (VERIFIED) |
| Unit 1 contents flat, stale or wrong | Guest and host bytes never captured | **Open** |
| Wrong zeta values with a non-transparent texture rim | Far boxes are very depth-sensitive; no zeta dump exists | **Open** |
| Missing D3D12 depth bounds test | The backend ignores it, Vulkan applies it. Game use unknown | **Open** |
| Real PS3 appearance | No reference exists | **Open** |
| Vertex attributes, draw order, SPU command buffers, other RSX methods | Not reviewed in depth for this defect. Of 105 method names in `rsx_commands.h`, the ones used by neither the decoder nor the D3D12 backend are mostly per-unit texture and DMA names handled by range, plus blend colour and depth bounds. The decoder check only covers names, not behaviour | Not established |

New observation (T165 B1): 4 of 7 boxes use one 8×8 texture and 2 use one 16×16, each with its own stencil ref. Squares of about 34 %, 5 % and 1 % darkening (T178) can't all be one clamped rim value if they share a texture, but TA has no constants to tie squares to boxes. HYPOTHESIS only.

## 3. Verified root cause: large faint polygons

Guest state for these boxes is GREATER, no depth writes, front faces culled, so a back face passes only where the scene is in front of it. Sky never passes.

Host default: a draw that samples its own zeta is moved to an empty shared depth buffer with LEQUAL and writes on. Every back face passes, sky included, and its writes reject later boxes. Pixel and A/B evidence is in T172.

## 4. Fix and commits

| Commit | Content |
|---|---|
| `0f68dd20` | `RSX_DEPTH_VOLUME=1`: read-only GREATER or GEQUAL draws keep their zeta and the guest depth/stencil key. Reviewed from T172's uncommitted work; fixture extended to every adapter. Off by default |
| `505a4d0a` | Cherry-pick of T178 `b2240f2c`: `RSXI_TEX_BYTES`, `RSXI_SNAP_FP`, guest depth bounds in draw events. Diagnostics only |

The selection is state-based, with no shader or terrain rule. In all 15 RSXI captures from T16x and T17x it selects 108 draws, all fp `0x022C20C1`, none with stencil ref 0. Those captures stop at about 2,044 draws, so later draws are unseen.

T172's other uncommitted edits to `scratch/` come from the test suite and were not taken. T173's and T174's changes aren't in this branch.

## 5. Before and after (fixture)

`tools/test_t172_volume.py`. Hand-built from the verified state; it doesn't run the backend's zeta binding or the game's ucode.

| Arm | Sky layers | Terrain layers |
|---|---|---|
| Guest state (the corrected behaviour) | 0 | 2 |
| Host default (the defect) | 1 | 1 |

Against the pre-fix tree the same test fails its 4 source pins and stops before the fixture.

## 6. GPU compatibility

| Adapter | Checks | Failures |
|---|---|---|
| NVIDIA GeForce RTX 5060 | 22 | 0 |
| AMD Radeon integrated | 22 | 0 |
| Microsoft Basic Render Driver | 22 | 0 |
| WARP | 22 | 0 |

## 7. Regression and performance

- Full suite on `505a4d0a`: PASS 151, FAIL 0, SKIP 43. `test_spurs_wws_concurrency` is intermittent and remains an open, separate issue regardless of this result.
- Audits: `audit_public.py --tree` on a copy of the fix, rc=0; the same on the T178 commit's files; report with `--staged --private-reports`.
- Performance: **not measured.** By source, with the flag off the cost is one cached flag check per affected path. With it on, up to one zeta-to-colour rebuild per box run; captures held at most 30 box draws. The zeta colour image already exists, so no new resource.
- Exe built: SHA-256 `0d66736ab6d75b2c75a682074705ef857ae97f871d559cdd02a98266794075a7`, from `505a4d0a`, at `build/motorstorm-t179`.

## 8. Remaining unresolved

- Dark squares: cause unknown. No fix attempted, because the remaining candidates need game data.
- `RSX_DEPTH_VOLUME=1` in game: unproven. In default mode opaque draws don't write stencil, so NOTEQUAL always passes and a vehicle's box also shades that vehicle.
- Depth values other draws write are still the forced default, so a correctly bound test compares against imperfect zeta.
- T173 and T174 items weren't re-examined here. Rank 3 defects are open. The polygon offset -2 draws are still unidentified.

## 9. Proposed runtime validation

**Not run. Needs authorization.** Two launches of the pinned exe, local console session, Godot and other GPU workloads closed (`query session`, `nvidia-smi --query-compute-apps` empty). Note `llama-server` and Ollama were running in T176.

```
py -3 generated/analysis/t179/ab/run_t179.py prepare t
py -3 generated/analysis/t179/ab/run_t179.py launch A a1
py -3 generated/analysis/t179/ab/run_t179.py launch B b1
```

Runner: `generated/analysis/t179/ab/run_t179.py` (main checkout, private), generated from the T171 runner. Same route and vehicle, stop at race + 45 s.

- Both arms: T171 arm B flags, `RSXI_VP_CONSTS=512 RSXI_UNITS=803 RSXI_TEX_BYTES=32 RSXI_SNAP_FP=022C20C1`.
- Only difference: `RSX_DEPTH_VOLUME=0` (A), `=1` (B).
- Stop on: effective-line mismatch, watchdog, crash, PSO failure, session change.

Compare at the nearest race clocks: frames, per-box snapshots, box draw state, unit 1 bytes, frame time, VRAM, debug-layer messages.

| Result | Meaning |
|---|---|
| Sky polygons gone in B, no vehicle damage | Correction supported; still one run each |
| `depth_bounds.test=1` on box draws | Implement D3D12 depth bounds |
| Unit 1 bytes flat, near the observed value | Host texture path innocent: asset, guest state or real appearance |
| Bytes have a transparent rim, per-box snapshot flat | Stale texture or wrong zeta. Next step is a `TEX_NOCACHE=1` launch, then a zeta dump |
| New debug-layer errors or vehicle speckle in B | Correction stays off |
