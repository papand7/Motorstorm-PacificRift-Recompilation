# RSX frame capture plan (2026-10-23)

## Existing facility (reused, not replaced)

RSXI (ps3recomp-int `libs/video/rsx_d3d12_backend.c`, `docs/RSX_INSPECTOR.md`, `tools/rsx_inspect.py`):
- off unless `RSXI=1`;
- one branch per frame and per op when off.

| Requested field | RSXI |
|---|---|
| Frame identifier | `frame` (presented-frame counter) |
| Guest RSX command position | **not available** (`cmd_offset: null`; the replay does not keep the FIFO position) |
| Active render targets, formats, sizes | `bind_rt`, `rt_pool`, `rt_life` (guest address, native slot, DXGI, w×h) |
| Texture bindings | `draw.tex` per unit: guest request against the native resource, and how it was chosen |
| Shader identifiers, compile result | `shader` events (address, code hash, decompile status, HLSL file); **new** `RSX_SHADER_TRACE` for compile/PSO/bind outside captured frames |
| Shader constants | up to 16 non-zero fragment constants per draw; the vertex-constant count |
| Draw counts | `frame.records`, `clears`, `legacy_draws` |
| GPU submission/completion | one GPU wait per captured frame; `meta_ms` / `snapshot_ms` |
| Presentation result | `frame.present`; **new**: a failed `Present` is logged with its HRESULT and the device-removed reason |
| Render-target contents | `RSXI_SNAP=targets\|passes\|textures` BMP snapshots, with content hash and non-zero fraction |

**Triggers:** frame range, `RSXI_AFTER_FP` (first draw with a program), `RSXI_AFTER_MS`, `RSXI_TRIGGER_FILE` (the runner's `--capture-rsx --capture-at <milestone>`), `RSXI_COUNT` ≤ 64, `RSXI_STRIDE`, `RSXI_MINDRAWS`.

## Added for bounded use (ps3recomp-int `dadfcaa`)

- **`RSXI_MAX_MB`** (default 1024): a total snapshot-byte cap for the whole capture. Before, the bound was per frame (≤ 64 snapshots × ≤ 64 frames, up to ~11 GB of 1280×720 BMPs). Past the cap, snapshots become `snapshot_skipped` (`disk_cap`) and the metadata continues; the manifest records the bytes written.
- **`RSX_SHADER_TRACE=1`**, capped by `RSX_SHADER_TRACE_MAX` (default 512): `[shader]` lines on stderr with these stages:
  - `translated` / `translate_fail`;
  - `compile_fail` (first error line);
  - `pso_fail` (HRESULT) / `pso_ready`;
  - `bound` (first replayed draw per code hash: frame, target, size);
  - `fallback` (the draw used the built-in shader).
- **`RSX_REPORT_TRACE=1`**: `[gcm-report] new` for each distinct `GET_REPORT` (type, offset, destination), at most 64, labelled `(not measured)`.

All are read once and change nothing the guest sees. Tests:
- `tools/test_d3d12_shader_trace.py`;
- `tools/test_gcm_report_trace.py`;
- the existing `tools/test_d3d12_rsxi_hooks.py`.

## Capture strategies

**A. Loading page and first garage frames** (in the next run, `NEXT_GARAGE_RENDER_VALIDATION.md`):
- `--capture-rsx --capture-at garage_world_read_complete --capture-frames 3 --capture-stride 10 --capture-snap targets`, `RSXI_MAX_MB=384`;
- it records the post-FX chain and its constants on the loading screen. This is the baseline for strategy B.

The run stops at the first cube program build, through a stop line that does not wait for the capture. An incomplete capture keeps `manifest.json` status `capturing` with whatever frames were written.

**B. White-to-black** (a later, separate run; do not combine):
- No fixed timestamp: the 2026-10-21 timing came from a no-skip run on an older build.
- Trigger: `RSXI_AFTER_FP=0x0074C781`, the luminance pass, which runs on every post-FX frame. Combine it with the runner trigger `--capture-at first_cubemap_draw` (trigger file), so the capture starts only after the garage pipeline exists. All configured triggers must hold together.
- Spread: `RSXI_COUNT=16`, `RSXI_STRIDE=90` (~16 frames over ~1,440 qualifying frames, covering the ~25 s ramp at the observed present rate; the stride is in qualifying frames, not seconds). `RSXI_SNAP=passes`, `RSXI_RTS=0x01DD0000,<640×360 and 320×180 luminance targets from capture A>`, `RSXI_MAX_MB=1024`.
- Fallback if no trigger fires: a manual trigger file (`RSXI_TRIGGER_FILE`, created by hand while watching).
- It must also run past the black transition. That needs its own stop rule: N frames after capture complete (`--stop-after-capture`), plus the 210 s cap.
- If the ramp starts later than 210 s after launch, this experiment cannot reach it under the cap. Report that instead of raising the cap.

**C. Manual / time window:** `RSXI_TRIGGER_FILE=<abs path>`, touched by hand, with `RSXI_COUNT`/`STRIDE`. Use it only when no event fits.

## Analysis

- `py -3 ps3recomp-int/tools/rsx_inspect.py <run>/rsxi` gives a report and a viewer.
- For B: tabulate per frame the constants of `0x0074C781` and `0x02193941`, the luminance-target non-zero fraction and hash, and the backbuffer mean.
- Keep every capture under `generated/runs/<run>/rsxi/` (private).
