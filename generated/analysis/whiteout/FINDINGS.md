# First loading-screen whiteout: offline findings (2026-10-24, no launch)

Inputs: runs `20261023-172442-present-stall` (RSXI f1340/1350/1360), `20261023-180259-present-gate` (`[vpc-watch] c[59]`), decrypted EBOOT, `generated/analysis/c38/global.rpk`.

- VERIFIED writer: `0x329048` (loading-screen render loop; `sys_timer_usleep(30000)` per iteration, exits when byte `[obj+0]` != 0).
  - start = seconds at entry (`0x4361B0` = `sys_time_get_system_time` NID 0x8461E528 × 1e-6, TOC 0x109FBF0+0x7248).
  - each iteration: t = now − start; c55 = (t, [obj+0x5E0], [obj+0x5E4], 0); c59 = (0,0,0, 1.0 + (−0.5)·t) (TOC 0x109FBF0 +0x3D88 = 1.0, +0x3D8C = −0.5). No clamp, no cap.
  - Capture f1340: c55.x = 3.1222, c59.w = −0.561099 = 1 − 0.5·3.1222 (exact).
- VERIFIED shading path is faithful:
  - VP F69565E0 (global.rpk 0x6CDDC) struct: 5 instrs, input mask 0x101, output mask 0xC000 (TEX0|TEX1): TEX1 reaches the FP on hardware.
  - FP 0x02538941 (global.rpk 0x6CB14): the tc1 read and final ADD/MOV/MAD use precision 1 (FP16), not FX12/FX9; no saturate. Output = X·(1 − w).
  - Blend 0x0122418B straight alpha (earlier, verified). Gain prediction matches measured.
- Whiteout begins when t > 2.0 s after the loop starts (w < 0): frame ≈1303 (≈33.3 s) in run 172442; the loop runs until ≈45.8 s (AsyncRenderThread exit), so t ≈ 14.5 s, gain ≈ 7.
- Conclusion: no RSX/backend defect on this path. The guest's own unclamped 2 s fade-in overshoots for as long as the loading screen stays up. Magnitude ∝ loading duration.
- Open (HYPOTHESIS): the PS3 shows this screen for ≲ 2–3 s; the port's ≈14.5 s load is the actual defect (garage-loading investigation, not this one).
- Helpers: `fpscan.py`, `vpscan.py` (find FP/VP ucode by the backend hashes).

## Loading-screen completion (offline, 2026-10-24)

- VERIFIED flag protocol: start `0x329660` (stb 0 → [obj+0], sys_ppu_thread_create AsyncRenderThread, entry OPD 0x1088970 → 0x329410 → loop 0x329048);
  stop `0x329D90` (stb 1 → [obj+0], then sys_ppu_thread_join (sc 44) on [obj+8]). Other start variants 0x329448, 0x32A058.
- VERIFIED garage caller: `0x8D9F0` (refs "track_garage", "Track0a_Garage_Sky1_driver", "garage-viewer-character.gui", "garage-viewer.gui")
  starts the screen at 0x8DA54 and stops it at 0x8E6A8 at its end (0x8E938 is the unwind path). The load runs synchronously on the
  calling thread; no poll on an external completion — the flag is set when the whole garage load sequence returns.
- Run 172442: tid 28 arg 0x0FEFF510 (flag EA). Create t_ms 122372906 → join ≈122389260 (16.3 s). 2045 PSARC (fd 5) reads, 66.5 MB,
  ~4.5 MB/s; 5 gaps ≥200 ms = 3.9 s (largest 2.59 s); fd 4 (FIOS cache.dat) reads are not logged.
- Process CPU during the window: 12.25 CPU-s / 15.5 s ≈ 0.8 cores (vs ≈2.4 before) → latency/wait-bound, not compute-bound.
- Same duration across builds: loadscreen_page_read → loadscreen_renderer_exited 16.0 / 14.2 / 14.4 s (runs 180259, 142859, 180419); garage_world_read_complete at +2.5 s;
  ≈10.6 s remain after garage_resources_requested.
- Not the cause: tid 15 "Multistream PPU Update Thread" blocked on SPU flag 0x0140F000 the whole window (audio, not on the loader path).
- UNKNOWN: what the loader thread waits on (FIOS op waits / lwcond slices / SPU decompression / sleeps). Diagnostic: loadscreen_completion_cmd.txt.
