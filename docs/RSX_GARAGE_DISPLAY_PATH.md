# Garage display path: how the garage image should reach the screen (offline, 2026-10-23)

## Update: the display path was found, and it was being dropped (run `20261023-200314`, then offline)

**VERIFIED:**
- The garage draws its display pass with ordinary DRAW_ARRAYS / DRAW_INDEX_ARRAY into the display buffers `0x10000`/`0x394000`, after the offscreen scene.
- The D3D12 backend discarded the whole pass because its fixed per-frame vertex-program vertex buffer (393,216 vertices) was already full: frame 1830's draw at op 552 ends exactly at vertex 393,216.
- So no display draw was recorded and nothing was presented. The "unrecorded final pass" hypothesis below was right about the effect and wrong about the mechanism: no inline-array or immediate vertices were used.
- Not the cause: the 2D engine, NV0039, aliasing, guest-memory writes and the gate.

**Fix:** the buffer now grows at the GPU-idle point. Details and the early-return inventory: `RSX_DRAW_REJECTION_AUDIT.md`.

**Runtime confirmation is still required:** that the display draws are recorded and Presents resume after the first garage frame.

---

MotorStorm was not launched for this analysis.

**Evidence used:**
- run `20261023-190803-garage-present` (exe `346f4e9e…`): logs, and RSXI pre frame 1595 (loading screen, presented);
- run `20261022-064218-fast-garage-capture2` (exe `7770ec7a…`): garage frames 4608, 4668 and 4728, all complete. Frame 4788 is empty: it was cut short;
- the lifted PPU code in `generated/ppu` and the decrypted `EBOOT.elf`, both read only;
- the backend source at ps3recomp-int `9bad862`.

Labels: **VERIFIED** (seen in a log, capture or code), **INFERRED** (follows from verified facts), **HYPOTHESIS** (needs runtime evidence), **UNSUPPORTED** (behaviour the backend does not implement).

## 1. Display-buffer configuration (VERIFIED)

| Event | Evidence |
|---|---|
| `SetFlipMode(2)`, then `SetDisplayBuffer(0, 0x10000, pitch 5120, 1280×720)` and `(1, 0x394000, 5120, 1280×720)` | stdout lines 145–150. These are the only two `SetDisplayBuffer` calls in the run, and the HLE prints every call |
| `SetFlipMode(1)` at lines 152, 1281, 2675 and 2728 | the flip mode changes; the buffers do not |
| `MapMainMemory(0x17000000 → io 0x01A00000)` and `(0x17400000 → io 0x01D00000)`, 3 MB each | stdout 2677–2680. `0x01DD0000` falls inside the second IO window, but every capture samples it with location 1 (local, `0xC1DD0000`), so the overlap is coincidental |
| Guest flips alternate buffers 0 and 1 | `[present_diag] display_buf=` toggles |

The two display buffers are contiguous: `0x10000 + 5120×720 = 0x394000`, and the second ends at `0x718000`. The garage's first render target, `0x00750000`, starts 0x38000 after that. Nothing in either run re-registers them, so **the offsets are constant through the garage transition**.

## 2. Timeline of the last run (VERIFIED)

| t | Event |
|---|---|
| 0–31 s | boot, splash, intro skipped |
| 31–47 s | loading screen. Each frame is about 3 records, drawn **directly into the display buffer** (pre frame 1595: `rt` = display, surface format `0x148`, pitch 5120, no anti-aliasing). Every replay presents (1,757 Presents, all `S_OK`) |
| 47.0 s | `loadscreen_renderer_exited` (guest frame 1748) |
| ≈48 s | last Present, at guest flip 1650 |
| 48–60 s | 66 more guest flips. Every replay is a 554-record garage batch with **no display draw**, so no Present (`replayed_no_present` 2 → 67) |

The present gate stayed in BOOT the whole run (see §6).

## 3. Garage render-target lifecycle (frame 4608; 4668 and 4728 identical)

| Guest offset (local) | Guest surface | D3D12 resource (pool slot) | Writers (ops) | Readers (ops, unit) | Role | Reaches the display? |
|---|---|---|---|---|---|---|
| `0x06FF0000` | 1024×2048, fmt `0x148`, pitch 4096, zeta at the same offset | slot 0, RGBA8 | clear 0/67/134; 198 draws, fp `0x047A6B41` (writes a constant) | none recorded. It is later bound as `0xB0` DEPTH24_D8 on unit 13, which the backend refuses | shadow map, 3 cascades. Needs depth sampling (UNSUPPORTED) | no |
| `0x00ED0000` | depth for the 1280×720 2×AA passes | slot 1 (as colour) | clear 201 | ops 515–522 (unit, 2558×719 `0xA5` view) | depth / zeta | no |
| `0x00750000` + MRT `0x01650000` | 1280×720 clip, **fmt `0x3148`, pitch 10240** | slots 14, 15, at 1280×720 | ops 203–513 (311 draws) | 520–522 (`0x00750000`); 523–552 (`0x01650000`, as a **2558×719** texture) | scene G-buffer-like MRT | indirectly (§4) |
| `0x077F0000`, `0x079D0000`, `0x0243AB00` | 640×360 | slots 2–4 | 514–519 | `0x079D0000`: ops 1–552 (572 reads, so the previous frame's value is used) | half-resolution passes, bloom/feedback | no |
| `0x02195900` → `0x02276900` → `0x022AED00` → `0x022BCE00` | 320×180 → 40×22, fmt `0x14B` (float) | slots 5–8 | 523–526, one each | the next one in the chain | luminance down-sample chain | no |
| `0x022C0500`, `0x022C1600` | small float targets (pitch 192/128; `0x022C0500` is sampled as 20×11). Their clip size was out of range, so the pool allocated them at 1280×720 | slots 9–10 | 527, 528 | `0x022C0500`: ops 528–552 | exposure values (INFERRED) | no |
| `0x01650000` (again) | 2×AA, pitch 10240 | slot 15 | clear 529 to (0.5, 1, 0.5, 0); 23 draws, 530–552. Op 552 samples the target it is bound to (`bound_as_target`) | none after 552 in the batch | **the last full-resolution image the batch produces** | not by any recorded op |
| `0x06A57000` | 320×180 | slot 12 | **clear 553, the last record of the batch. No draw follows** | none | the start of a pass whose draws are absent | — |
| `0x01DD0000` | texture: 1280×720, `0xA5` A8R8G8B8 linear, pitch 5120 (display-shaped) | none in the garage; the loading screen had an RT here (pool slot 6) | **no recorded garage op** | bound on unit 2 for ops 1–204, by fp `0x047A6B41` and `0x04D7D301`. **Neither program reads unit 2** (decompiled HLSL) | see §5 | — |

**Resource states** come from `bind_rt.state_before`: 4 is RENDER_TARGET and 128 is PIXEL_SHADER_RESOURCE. Each pool resource moves between those two states as it is bound or sampled. No state errors were logged, but the D3D12 debug layer was off.

**Anti-aliasing (VERIFIED, UNSUPPORTED):** surface format `0x3148` means
- colour A8R8G8B8 (`0x08`),
- depth Z24S8 (`0x40`),
- pitch layout (`0x100`),
- anti-alias mode 3 (bits 12–15), which libgcm calls DIAGONAL_CENTERED_2: two horizontal samples, so the surface is stored 2560×720.

The backend allocates these targets at 1280×720 and ignores the multisample layout. It does not explain the missing image, but such a surface must be resolved to 1280×720 before display, and **no recorded op does that resolve**.

## 4. How should the garage image reach the display?

| Candidate | Original RSX mechanism | Native backend | Evidence | Verdict |
|---|---|---|---|---|
| Direct 3D draw into a display buffer | `SET_SURFACE_COLOR_AOFFSET` = `0x10000`/`0x394000`, then draws | recorded as a display draw (`rt_off = 0`), and Present follows | the loading screen does exactly this. **0 of 543 recorded garage draws do** | if it happens, it is **not recorded** (next row) |
| **A final pass issued after the last recorded op** | after the clear of `0x06A57000`: a luminance pass, then a full-screen resolve/composite of the 2×AA image into the display buffer, then the flip | any draw path the D3D12 feed does not record vanishes (§4.1) | (a) every batch ends with a clear and no draw; (b) the next batch starts with unit 2 bound to `0x01DD0000`, but no recorded op binds it, so state was set by commands after op 553; (c) the loading screen's own display draws bind `0x01DD0000` on unit 2, the same layout; (d) the 2×AA image needs a resolve that no recorded op performs | **HYPOTHESIS, most likely**. The next run tests it (§7) |
| NV3089 scaled-image blit (the 2D engine as a resolve) | NV3062 destination plus NV3089 `IMAGE_IN` on subchannel 6 | a CPU copy in guest memory. It never reaches D3D12 surfaces or the swapchain (`RSX_TRANSFER_ENGINE_AUDIT.md`) | the game's libgcm builder for it (`func_00733468`) has **no direct call site and no function descriptor** in the EBOOT. No `[NV3089]`/`[NV3089G]`/`[GCM2D-UNH]` line in any run. The trace sampled 1 blit in 64 (now fixed) | **not supported by evidence**. Not excluded: SPU-built or inline-emitted commands were not searched |
| NV0039 memory-to-memory copy | subchannel 1, `0x230C..0x2328` | **not implemented**. Subchannel 1 is routed to the 3D object, so NV0039 methods would land as NV4097 blend/stencil state | the builder `func_007330A4` has no call site or descriptor. No trace evidence either way | not supported. The 3D routing is a latent defect for any title that uses NV0039 |
| RSX surface rebinding or aliasing (display offset reached through another address) | the same memory under another offset or location | detection compares the raw offset with registered display offsets only | the display buffers are never re-registered. No recorded surface overlaps `0x10000..0x718000` | not supported |
| CPU/SPU writes the display buffer | SPU or PPU DMA into local memory | invisible: the backend never presents guest memory | not measured until now (`PS3_DISPMEM_PROBE`, §7) | UNKNOWN |
| Texture-to-display composite through `0x01DD0000` | sample a copy of the screen | screen-copy stand-in (§5) | no recorded garage draw reads it | not the display path |

### 4.1 Draws the D3D12 feed does not record (VERIFIED in code)

- **`NV4097_INLINE_ARRAY` (0x1818)**, vertices inside the push buffer: `rsx_commands.c` has no handler. The platform-neutral `rsx_dispatch.c` engine has one, but the D3D12 path does not use it.
- **Immediate-mode vertices** (`SET_VERTEX_DATA*` between BEGIN and END with no DRAW): a BEGIN/END pair with no DRAW records nothing. `SET_VERTEX_DATA4F_M` is stored only as a constant attribute.
- **Backend early returns** in `d3d12_draw_arrays`/`d3d12_draw_indexed` drop draws without a record or a counter:
  - no pipeline;
  - a vertex count of 0 or more than `MAX_VERTICES`;
  - an upload that produced 0 vertices;
  - an unconverted primitive;
  - a full batch.

Whether the garage's final pass uses any of these is **UNKNOWN**. The PPU code emits BEGIN/DRAW only from libgcm's own builders. The game's own draw stream (SPU or precompiled) was not decoded offline. `PS3_DRAW_ACCT_MS` (new) counts all of these, with the surface each one targeted.

## 5. Screen-copy stand-in at `0x01DD0000`

- **Why it exists:** another title rendered a reflection into the backbuffer and sampled it as a texture. `screen_copy_capture` copies the D3D12 backbuffer into `s_screen_copy`, either mid-frame (after reduced-viewport passes) or at the end of the frame.
- **When it is bound:** any 1280×720 (display-sized) A8R8G8B8/D8R8G8B8 texture that is not an offscreen RT is bound to that copy (`SCREEN_AS_TEX`, on by default). This check comes **before** the guest-memory upload, so it would also hide real guest-written data. The run's `[TEXLOC]` shows the guest memory at `0xC1DD0000` empty when sampled.
- **RSX semantics:** none. On the RSX, a texture at `0x01DD0000` reads whatever the guest last wrote there. The stand-in substitutes the backend's last backbuffer, which depends on display draws having been presented. That is a **circular dependency on presentation**: with no garage Presents, it holds the last loading-screen image.
- **Programs seen binding it:**
  - garage (capture 4608): `0x047A6B41` and `0x04D7D301`, both on unit 2, and **neither reads unit 2**;
  - the last run's SCREENTEX lines: `0x2193941`, `0x2537E81`, `0x2538DC1`, `0x4D7D301` and `0x47A6B41` on unit 2, plus `0x74D0C1` and `0x7400C1` on unit 0. Run-wide, so loading-screen programs are mixed in.
- **What the game expects:** in the loading screen, `0x01DD0000` is a render target the loading renderer draws into (pool slot 6, `rt_exact`). It is that renderer's own surface, not "the previous presented frame". In the garage, no recorded op writes it.
- **Not removed:** it does not affect any recorded garage draw. Removing it would change loading-screen behaviour that is not under investigation.

## 6. Present gate (`present_gate.h`)

- **BOOT means `clear_presents == 0`:** no display colour clear has ever presented a frame. In BOOT, every ticker call replays the batch and presents it if it holds a display draw. This is the "flip is the frame boundary" behaviour.
- **Leaving BOOT** needs a display colour clear that presents (CLEAR mode). FLIP mode follows only after clears lapse. With the intro skipped, no display colour clear ever presented, so **staying in BOOT is expected and is not what suppresses the garage**.
- **The Present decision** is `has_display`: a recorded non-clear draw whose colour target is a registered display buffer. Replay is not coupled to it; offscreen batches always run.
- **The garage is suppressed because no recorded draw targets a display buffer.** That matches RSX semantics: a flip of a buffer nothing wrote shows its old contents, and the backend keeps the last presented image.
- The detection matches raw offsets exactly. That is correct for the RSX (a surface offset equal to the display offset) but blind to aliases. None was observed.
- **Not changed:** forcing a mode change or a Present has no evidence behind it.

## 7. What the next run measures (prepared, not run)

| Question | Instrument |
|---|---|
| Is there an undrawn BEGIN/END group (inline array, immediate vertices) on a display buffer? | `PS3_DRAW_ACCT_MS`: `event=unrecorded_display_group` |
| Does the backend drop a display-buffer draw? | `PS3_DRAW_ACCT_MS`: `event=dropped_display_draw` and `callbacks.dropped` |
| Does anything write the display buffers in guest memory? | `PS3_DISPMEM_PROBE`: `[dispmem]` on change, at every flip |
| Any transfer-engine method after the handoff? Which object is on each subchannel? | `PS3_XFER_TRACE` (all subchannels 1–6, latched), `NV3089_GATE` (no sampling gap), `GCM_OBJDBG=1` |
| What do the garage's GPU targets contain? | RSXI `RSXI_EVENT=no_present`: 6 offscreen garage replays with all pass and end snapshots (GPU readback after a fence wait) |

## 8. Verified, hypothesis, unsupported

- **VERIFIED:**
  - the display buffers are constant;
  - the loading screen draws directly into the display buffer;
  - no recorded garage draw targets a display buffer;
  - the garage's final image is a 2×AA surface that no recorded op resolves;
  - every batch ends with an undrawn clear, and texture state changes after the last recorded op;
  - no recorded garage draw reads `0x01DD0000`;
  - the D3D12 feed has no INLINE_ARRAY or immediate-vertex draw path and drops some draws without counting them;
  - the libgcm NV3089/NV0039 builders have no direct callers.
- **HYPOTHESIS (most likely):** the garage's final resolve/composite to the display buffer is issued after op 553 and is never recorded by the D3D12 path, through an unsupported vertex path or a silent drop.
- **UNSUPPORTED:** 2×AA surface layout, depth-texture sampling (`0xB0`), the `0xB4` LUT, NV0039, and GPU synchronization of NV3089.
