# Garage loading: runtime diagnostics (2026-10-23)

All of these are opt-in and off by default. They only log; guest state is never changed.

## Runtime (ps3recomp-int `2f6c7cf`)

| Knob | Logs | Cost / bound |
|---|---|---|
| `FS_CALLER=1` (existing) | `[fs] open '…' -> fd N (opened by …)`, `lseek`, `close` with the guest caller. **New:** `[fs] open FAIL '…' -> '…' (flags=0x0, errno 2)  (by …)`. | One line per open, seek or close |
| `PS3_FSLOG_READS=<fd>` (existing) | `[fsread] fd=N want=W got=G pos=P t_ms=T` for every read on that descriptor. **Fixed:** `pos` is the full 64-bit start (it was -1 past 2 GiB). **New:** `t_ms`, a monotonic ms. | One line per read on one fd. The run is bounded by the 210 s cap; no data bytes are printed. |
| `PS3_VIDEO_STATS`, `RSX_HEARTBEAT_MS`, `PS3_FC_WATCHDOG_MS` (existing) | Presents, draws, frame-clock stalls | — |

**Correlation:**
- by descriptor: `fd` 5 = `ms2.psarc`;
- by archive member: `pos` → member, offline with `tools/psarc_read_map.py RUN --fd 5` or `generated/analysis/garage_seek_map.py`;
- by time: `t_ms` and the heartbeat.

**Gaps (not instrumented):**
- **Decompression** happens on SPU in guest code. Its completion is seen only indirectly, through the FIOS wait completing.
- **Resource parsing** and **object creation** are guest code.
- **Cache writes:** `cellFsWrite` is not logged.

Adding guest hooks for these would need traced function addresses first. That has not been done,
and nothing was guessed.

## Runner (ps3recomp-int `2f6c7cf`)

New milestone type `span_read`. It follows the descriptor of an earlier milestone and a byte range:
- `mode: first` fires on the first read that overlaps the range;
- `mode: complete` fires once all of the range has been read (in any order; short reads count by `got`).

It needs `[fsread]` lines (`PS3_FSLOG_READS`). It shows that bytes were **read**, not that they
were decompressed, parsed or used.

## Proposed milestones (`generated/profile/motorstorm_milestones.garage.proposed.json`)

This file is **not live**; it is passed with `--config`. It is the earlier proposed config plus the following:

| Milestone | Definition | Means |
|---|---|---|
| `loadscreen_page_read` | `span_read complete` over `/gui/loadscreen-garage.gui` [2,536,802,865, +588,359) | the loading page's stored bytes were read |
| `garage_world_read_started` | `span_read first` over `/worlds/track_garage.rpk` [1,917,461,852, +23,207,184) | the first read of the garage world |
| `garage_world_read_complete` | `span_read complete` over the same range | every stored byte of the garage world was read from the archive |
| `garage_rendering_started` (existing, extended) | first `[CUBE] … compiled with cube units` | 3D scene pipeline (indirect) |

All of them are `after: intro_video_closed` and `extended: true`, so they need `--allow-extended`.

**Offline checks:**
- Replaying all saved runs: unchanged results. None of the saved runs logged archive reads.
- A synthetic replay of the member's 355 reads fires `started` and then `complete`.
- The archive spans come from the TOC.

**Caveat:** a member served from the FIOS cache would not appear on fd 5. With a cleared cache
at every boot, the first load comes from the archive (HYPOTHESIS for the garage world).

## Not done

- No title-specific code in the runtime.
- No change to the live `tools/motorstorm_milestones.json`.
- No change to the default stop (`garage_resources_requested`).
