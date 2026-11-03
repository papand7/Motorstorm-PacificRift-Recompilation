# T162 — RSX vertex pipeline: path and profile

2026-10-30. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. No game launch in T162. Sources:
- the T161 baseline runs C1 and C2 (`generated/runs/20261030-0651*-CC1`, `…0658*-CC2`; exe `b1fdb0bd…c01fc`, ps3recomp `afdcabd`, arm C environment);
- the RSXI race captures of T145;
- the synthetic backend harnesses below.

Tools: `vtx_profile_t162.py`, `perf_summary_t162.py` and `cmp_snaps_t162.py` (committed in `t162/tools/`, working copies in `t162/gpuvtx/`); the private harness is in `t162/gpuvtx/harness/`.

## 1. The vertex path (ps3recomp `libs/video`, VERIFIED from source)

| # | stage | where | what it does |
|---|---|---|---|
| 1 | Guest vertex-array state | `rsx_commands.c` → `rsx_state.vertex_attribs[16]` (offset, stride, size, type, frequency), `vertex_data4f[16]` (`SET_VERTEX_DATA4F_M`), index array (offset, dma: u16/u32, LOCAL/MAIN), restart | FIFO methods decoded on the drain thread |
| 2 | Attribute format decoding | `rsx_fetch_attrib` (`rsx_vertex_fetch.c`) | Big-endian. Types: FLOAT, HALF (denormals flushed), UB /255, S1 /32767, S32K, CMP 11/11/10 (/1023, /511, w = 1), UB256; unknown types read as float. Size 0 = 4. **Components the array does not supply keep the constant register's value, not (0,0,0,1)** (Rubber Ducky fix). Disabled or stride-0 arrays give the register |
| 3 | Vertex buffer addressing | `cellGcmResolveLocated` | Offset bit 31: MAIN (IO table, whole 1 MiB pages) or LOCAL (VRAM, linear). Element = offset + index × stride (u32 arithmetic). Dividers: index / freq or index % freq |
| 4 | Indexed / non-indexed draws | `d3d12_draw_indexed_body`, `d3d12_draw_arrays_body` | Indexed: TRIANGLES, STRIP, FAN, QUADS. Others are refused |
| 5 | CPU vertex expansion | `upload_strip_vp_indexed` / `upload_tris_vp*` / `upload_quads_vp*` / `upload_strip_vp`, `vpx_cache` (`ps3emu/vp_expand.h`), `prim_stream.h` | **De-indexing**: every triangle corner is written. Strip/fan/quad becomes a triangle list, with restart, odd-triangle order and continuity across libgcm's 256-index batches. Each corner is 16 float4 slots (fat, 256 B) or the active slots after a template (compact, `RSX_VP_COMPACT`, T119) |
| 6 | Host vertex-buffer allocation | `vp_vb` (two parity halves, `vp_vb_budget.h` growth to 1 M vertices), `vp_reserve`, `vp_make_room` | Reservation in 256-byte units. A full half or 2,048 records triggers an early replay (`vp_flush`) before writing |
| 7 | Upload | — | No copy: the expander writes the persistently mapped UPLOAD-heap buffer, which the GPU reads directly |
| 8 | Input layout | VP PSO: `ATTR0..15`, R32G32B32A32_FLOAT | Fat: one view. Compact: one view per active slot at its record offset (`vpc_bind`); constant slots use stride 0 on the template |
| 9 | VS inputs | `rsx_vp_decompiler.c` | `VSInput { float4 a0..a15 }` → `float4 v[16]` → translated program |
| 10 | VS execution | GPU | vs_5_0, `vp_c[512]` CBV b0 |
| 11 | Recording / submission | `D3D12DrawRecord`, `render_frame` | Records are built during the drain. The replay sets the PSO, bindings and views and issues `DrawInstanced(vertex_count, 1, vb/256, 0)`. One `ExecuteCommandLists` per pass |

**Why the CPU expands.**

What the expansion has to preserve (required for correctness):
- **Primitive semantics.** RSX fans, restart inside fans, strips continued across 256-index batches with the right winding, and quads. D3D12 has no fan or quad topology and cannot continue a strip across draws.
- **Formats.** Big-endian data and RSX-only conversions (CMP, S1 = c/32767 including −32768 → −1.00003, the half-denormal flush) that no DXGI format reproduces.
- **Missing components** come from the constant register.
- **Address resolution** through the IO table.

What is an artifact of the implementation:
- doing all of this **per triangle corner** (about 1.5–3× duplication; T119 counts about 205 unique vertices per 309 corners);
- in **float4 slots**: 64–256 B per corner, against 12–28 B of guest data per vertex.

## 2. Light and heavy scene, baseline C (T161 arm C, wakeups off; medians per guest frame)

| metric | light (race frames 40–499) C1 / C2 | heavy (frames 600–690) C1 / C2 |
|---|---|---|
| draws/frame | 2,004 / 2,004 | 6,956 / 6,973 |
| RSX passes | 1 | 4 (2,048-record limit; early replays) |
| vertex-buffer units/frame ("verts", 256 B each) | 100.8k | 412k |
| vertex upload bytes/frame | 24.65 MB | 100.6 MB |
| vertex expansion CPU (`expand_ms`, draw callbacks) | **13.5 / 13.0 ms** | **47.3 / 49.3 ms** |
| in-drain early replays (`flush_ms`) | 0 | 199 / 222 ms (texture recording, see below) |
| draw recording (`record_ms`): textures / PSO / commands | 5.1 / 5.0: 1.3 / 1.3 / 2.5 | 209 / 234: **190 / 216** / 8.2 / 9.3–9.7 |
| frame wall (`wall_ms`) | 47.4 / 46.9 (21 FPS) | 270 / 298 (3.5 FPS) |
| GPU time | not measured (GPU wait ≈ 0) | not measured |

Interpretation (VERIFIED unless noted):
- **The `verts` and `upload_mb` counters count 256-byte reservation units.** So "256 B per vertex" holds by construction, and T157's "244 B/vertex, mostly fat" reading was this artifact. The logs cannot tell compact records from fat ones, or give guest vertex counts.
- **Light scene.** The PPU is the bound (Havok wait about 17.5 ms, T154/T161). Expansion (13 ms) runs on the RSX thread, which is idle about 21 ms per frame, so removing it would not raise light FPS (HYPOTHESIS, strong).
- **Heavy scene, today.** The texture table overflow (`rec_tex` 190–216 ms) dominates. Expansion is 47–49 ms, about 17 % of the frame.
- **Heavy scene, once texture residency lands.** T157 Br1 (`RSX_TEX_SLOTS=1024`, one run, another exe) measured expansion at **67.3 ms of a 131.7 ms frame**, the largest remaining RSX item. That figure is historical; it must be re-measured on the integrated build (BLOCKED, needs a launch).
- **Primitive mix** (RSXI, 6 race frames, 3 runs of T145): indexed TRIANGLE_STRIP is 438/485 and 961/961 draws, and over 99 % of the indices. The rest are 20 non-indexed QUADS, 23 non-indexed strips of 4 vertices, and 4 TRIANGLES draws (VERIFIED for those frames).
- **Allocation:** none per draw (one growing buffer). Vertex format conversions are one per corner per active slot. Recording costs 1.3 ms (light) and 8.2 ms (heavy) for PSO, and 2.5 and 9.5 ms for commands.

## 3. Synthetic split (race shape: 2,000 indexed u16 strips of 256 with restart, stride-28 float3/ubyte4/ubyte4/float2)

`bench_draw_path` with `RSX_DRAW_SPLIT=1`, CPU compact path (the preset):
- **`emit` (fetch, convert, write) is 9.3–13.4 ms of a 10.8–15.3 ms callback total, 86–88 %.**
- Room, count and VS lookup take 0.4–0.9 ms.
- 613,797 corners and 38.2 MB per frame.

On the CPU path the vertex work is the draw-callback cost.

## 4. Missing game measurements: `RSX_VTX_STATS` (new, opt-in, read-only)

These are not available from any existing log:
- the compact/fat share;
- the guest index range and referenced bytes per draw;
- the in-game vertex-format signatures.

`RSX_VTX_STATS=<ms>` (ps3recomp `d1bec5b`) prints, per primitive × indexed × path:
- callbacks, guest indices, corners, upload MB and callback µs;
- the referenced index range and raw-span MB;
- the format signatures by corners.

Collecting it needs one diagnostic launch (`GAME_AB_PLAN.md` §1).
