# T162 — GPU-driven vertex fetch: design

## 1. Goal

Remove the per-corner CPU fetch, convert and write (`emit`, 86–88 % of the draw-callback cost, `RSX_VERTEX_PIPELINE_PROFILE.md` §3). Rendering semantics must stay bit-identical. The CPU expansion stays as the reference and as the fallback.

## 2. Options

| | A: native D3D12 input layouts | **B: shader-side fetch (chosen)** |
|---|---|---|
| Byte order | DXGI formats are little-endian. Guest arrays are big-endian, so the CPU would still have to swap every element, i.e. touch every byte | `ByteAddressBuffer` loads plus a swap in the VS |
| RSX conversions | No DXGI format for CMP 11/11/10 signed, 3 × u8, UB256 as float or S32K as float. SNORM16 clamps −32768 to −1.0 where RSX gives −32768/32767 = −1.00003. HALF matches only if denormals are flushed, which DXGI does not do | Every type decoded exactly as `rsx_fetch_attrib`. UB, S1 and CMP go through a table built by the CPU with the same expressions, so the GPU cannot round differently |
| Missing components | The IA fills (0,0,0,1). RSX keeps the **constant register** (`vertex_data4f`) | Each attribute starts from its constant register, then the supplied components overwrite it |
| Constant / disabled attributes | Need a stride-0 view on a template (as compact does) | A descriptor with 0 components returns the register |
| Strips/fans, restart, batch seams | Not expressible without CPU assembly | CPU assembles the triangle list as today, but as **u32 guest indices** (4 B/corner) |
| Verdict | Covers at most UB4 normalised and float, and still needs a CPU swap: rejected | Covers every type the CPU path handles |

A hybrid (A for the formats it can express) is not needed: B covers them all, and the conversion costs the GPU nothing measurable (§6).

## 3. Data flow (per indexed strip/fan draw)

```
guest index array --(CPU: prim_stream assembly, restart, seams, odd order)--> u32 guest indices  [ring]
guest vertex arrays --(CPU: one memcpy per referenced span, unconverted)----> raw block           [ring]
rsx_state attribs + vertex_data4f --(rsx_gvf_plan)--> 512-B descriptor CB (addr, stride, type, n; 16 registers) [ring]
VS: SV_VertexID = guest index -> gvf_fetch(k, vid) for k = 0..15 -> float4 v[16] -> the unchanged program body
DrawIndexedInstanced(corners, 1, 0, 0, 0), R32_UINT index buffer, triangle list
```

- **Ring:** one UPLOAD-heap buffer with two halves (default 2 × 32 MB, `RSX_GPU_VERTEX_FETCH_MB` 4–512).
  - It follows `vp_vb`'s parity and its offset resets at the same two sites. The CPU writes a half only after `render_frame` has waited for the GPU on the pass that read it.
  - A full half or a full record table triggers the same early replay as `vp_make_room`, before anything is written.
- **Spans:** the referenced index range lo..hi of every active array.
  - Overlapping or touching intervals of one location are merged, so interleaved arrays are copied once.
  - Each span gets 16 bytes of zero slack, because the VS reads aligned dwords.
  - A span is taken only when the resolver maps it linearly (checked at every 1 MiB page).
- **Table:** 68,864 floats (275 KB), built once:
  - u8 / 255;
  - s16 / 32767;
  - CMP x,y / 1023 and z / 511 on the sign-extended fields.

## 4. Supported formats and fallback coverage

- **Taken on the GPU:**
  - indexed TRIANGLE_STRIP and TRIANGLE_FAN with u16 or u32 indices, restart enabled or not;
  - every attribute type (1–7, plus unknown types as float), sizes 0–4, any stride and offset alignment;
  - disabled and stride-0 attributes, LOCAL arrays, MAIN arrays whose span is linear.
- **Left to the CPU path, with a counter in `[gvf]`:**
  - frequency dividers;
  - MAIN spans across a non-linear IO page (`span`);
  - sparse draws, where the range would copy over 64 KB and more than twice the compact record (`sparse`);
  - draws needing over a quarter of a ring half (`big`);
  - draws producing no triangle (`empty`);
  - a VS compile failure (`vs`);
  - no room after an early replay (`room`).
- **Not attempted:** non-indexed draws, indexed TRIANGLES and QUADS, inline arrays. In game these are under 1 % of indices (profile §2).
- **Replay:** a GPU-fetch record whose guest-FP pipeline cannot be built is counted (`nopso`) and **not drawn**. The fallback pipeline reads vertex buffers, which a GPU-fetch record doesn't fill. The CPU path would draw it with the fallback colour/atlas shader. Tests require `nopso` = 0, and the game A/B checks it (open item: a GPU-fetch fallback PSO).

## 5. Shader integration

- **One compiler:** `rsx_vp_decompile_gvf_ex` is the existing decompiler with a third input mode. Only the `VSInput` struct and the `v[k]` assignments change; the program body is the same text.
- **Variants and caching:**
  - one extra VS variant per vertex program that a GPU-fetch draw uses, cached in the same VS cache under a salted hash, with its own last-lookup memo;
  - PSOs are keyed by VS slot, so at most one extra PSO per (program, FP state) actually drawn on the GPU path. No permutation by format: formats are data in the descriptor CB.
- **Root signature:** three vertex-visible root parameters are appended when the switch is on:
  - CBV b1 (pixel b1 remains the FP texscale);
  - SRV t20 (raw block);
  - SRV t21 (table).

  Off, the root signature and its pipeline-library identity are unchanged.
- **Input layout:** the PSO's 16-slot layout is kept. A VS that declares only `SV_VertexID` consumes none of it, which D3D12 allows; the debug layer reports 0 messages.

## 6. Memory and bandwidth

- **Ring:** 64 MB of upload heap by default, plus the 275 KB table.
- **Per draw:** 512 B of descriptors, 4 B per corner, and the raw spans.
- **Race shape (2,000 draws):**
  - CPU compact writes 38.2 MB/frame (fat: 150 MB);
  - GPU fetch writes 16.5 MB raw + 2.3 MB indices + 1 MB descriptors.
- **GPU time per pass is unchanged or lower** on the RTX 5060 (§7 of the implementation report): fewer bytes are fetched, against about 20 ALU ops per attribute.

## 7. Radeon 890M (integrated, shared memory)

- **What carries over (VERIFIED offline on this host's Radeon iGPU):** the fetch is bit-identical on AMD as on NVIDIA and WARP.
- **Bandwidth.** On UMA the upload heap is system memory read by the GPU, so bytes written by the CPU and bytes read by the GPU compete for the same DRAM. GPU fetch writes about half the bytes of compact, and a fifth of fat.
- **Shader cost.** Each fetched attribute adds an aligned-load pair, a byte swap and at most one table load. That is small against the RSX programs (64–100+ instructions). The table is 275 KB, read with high locality.
- **Not transferable without measurement:**
  - the CPU/GPU split on an 890M;
  - cache behaviour of the raw loads;
  - the cost of the extra root binds per draw.
- **Fallback for a measured loss:** the switch is per run, and the `sparse`/`big` thresholds are the knobs for workload-dependent selection.
