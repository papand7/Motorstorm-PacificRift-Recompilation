# T167: async fetch compilation review

**No game has run with `RSX_GVF_ASYNC=1`. Nothing here shows it improves or worsens the game.** It played no part in arm A's failure (`T162_T167_EXECUTABLE_DIFF.md`).

Code: `include/ps3emu/vs_compile_async.h`, `vp_get_vs` in `libs/video/rsx_d3d12_backend.c`.

## Review, by reading the code

| Item | Finding |
|---|---|
| Worker start | Lazily, at the first accepted submission |
| Disabled path | No queue, no thread: fetch off short-circuits before `gvf_async_on()` |
| Locks | One SRW lock, released during the compile. `rsc_compile` takes its own lock only around cache updates. No lock order problem found |
| Render-thread waits | None: `vca_query` returns at once; pending or failed sends the draw to the CPU path |
| Stuck pending | A slot leaves PENDING only when the compile returns. A hung `D3DCompile` leaves that program on the CPU path indefinitely, and blocks later jobs, since there is one worker |
| Duplicates | `vca_find_` prevents a second job per hash |
| Queue bound | 256 slots. A full table refuses, and the draw falls back |
| Blob lifetime | Ownership passes once via `vca_query`; released on a decompile failure |
| Failed programs | Sticky, CPU path |
| Shutdown | No join. The worker dies with the process, possibly mid-compile. Harmless for a process exit; not tested in game |

No defect that needs a fix was found. `D3DCompile` running on a second thread in the game itself is unverified.

## Diagnostic added (ps3recomp `61d32fd`)

`RSX_ASYNC_COMPILE_DIAG=1`: bounded `[vca]` lines, at most 4,000: queued, start, done, failed, refused, with hash, duration, pending depth and totals. No source text. Off by default.

Offline results are in `OFFLINE_VALIDATION.md`.
