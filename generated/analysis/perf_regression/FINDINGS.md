# T12 garage performance regression (offline, 2026-10-24, no launch)

Runs: A = 20261024-194334-garage-rtvis (exe 1f7d5947, src 1bc3b93), B = 20261024-204223-garage-rtrb (exe db479495, src 496485b).
Only differences: commits 5b1988f + 496485b (RT readback) and env RSX_RT_READBACK=1, RSX_RT_READBACK_LOG=160.

## Measured
- Same guest work per frame in frames 1790-2090: 630 draws/frame, same SPU dispatches (~24/frame), same HOTREAD/SPURS lines (hist.py).
- Same speed until frame 1788 (both at frame ~1778 at 50 s). B then has 7 periodic stalls (~every 45 frames): 51.0-61.7, 64.8-76.0,
  79.2-90.3, 99.0-104.7, 109.7-119.1, 122.2-133.5, 136.6-147.9 s = ~70 s of 105 s. Each = ~3 frames of ~3.5 s. Between stalls ~10 fps = A.
- Process CPU during stalls 5-7 cores (kernel 1.4-2.2) vs A 3.1 (0.6-0.9). Per-thread samples too skewed to identify the RSX thread's share.
- Memory identical (814 MB WS / 890 MB private). A's +500 MB at 83 s = VPVB growth to 1M verts at frame 2028; B never grew.
- Watchdog (8 reports, all in B): RSX/frame-clock thread in rsx_fetch_attrib <- upload_strip_vp_indexed (6), vp_record_tex_snap (1), vp_record_cb -> ntdll (1).
- Hot vertex functions byte-identical in size in both maps (fsz.py); readback bookkeeping is O(32)/draw; no copies queued.
- No project builds/tests ran during either run window (file mtimes). Host load outside the project not recorded.
- Microbench (bench_vertex_fetch_vp.c): 45-150 ns per emitted VP vertex -> 18-60 ms for a 393216-vertex (cap) frame. One first run gave 1.4 s for WC sequential, not reproduced in 2 reruns.
- SPU async job = new 256 MB-reserve thread: ~110-130 us CPU each, ~2-3% of a core at 204/s (bench_thread.c).

## Conclusion
BLOCKED for a verified cause. Budget-capped vertex work cannot account for 3.5 s frames at measured cost (>50x), so the stall frames
were either not CPU-bound on the RSX thread (preempted/blocked) or hit a cost the logs do not show. Readback code is not shown to cause it;
not excluded either (only code+env delta). Needs RSX_CPU (b45919c) on one bounded run.
