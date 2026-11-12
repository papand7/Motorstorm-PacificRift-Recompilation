# T167: the ~84 ms GPU wait

Source: ps3recomp `8a12a61` (branch `agent/t167-gpu-wait-shader-stall`, base `69489f2`). No game launched for T167. Older runs are existing logs.

## Result

**VERIFIED offline, on the real backend without game code:** in this remote desktop session, `Present(1, 0)` holds the D3D12 queue for about 94 ms per frame. The CPU then blocks on the fence in `render_frame`'s entry drain. `RSX_PRESENT_INTERVAL=0` removes the wait.

**VERIFIED from logs:** the game's 84 ms frames occur only in remote sessions (table below).

**HYPOTHESIS:** 92 ms is 3 × 31.25 ms of the Remote Display Adapter's 32 Hz. It fits, but nothing proves it.

**NOT VERIFIED:** the fix inside the game. It also remains unknown what makes a remote session enter the mode: 6 of 23 remote runs, including T162 A1, never did. Transitions happen mid-scene with constant draws, so this looks host-driven.

## Where the wait is

| Question | Answer | Status |
|---|---|---|
| Timer | `wait_ms` is `rf_wait_us`, around `wait_for_gpu()` at `rfp_at(RFP_GPU_DRAIN)` | VERIFIED |
| CPU or GPU work | CPU blocked. GPU work is `gpu_total` 0.11 ms against `gpu_idle` 92 ms (`[gpu-prof]`, T162 B1) | VERIFIED |
| Primitive | Fence wait on the frame's last signal. `[wait-diag] why=drain`, 3 fence values per frame, `blocked_ms` 79–94 | VERIFIED |
| Present call | Not blocking: `present_ms` is about 0.2. The hold shows up in the queue after it | VERIFIED |
| Intentional | The drain is. Its length is not; it inherits whatever holds the queue | VERIFIED |
| Includes shader compile | No. Compiles run outside this timer, and the wait reproduces with no compile in the frame | VERIFIED |
| Frame parity or pass | Not established for the game. The probe has no parity effect: every frame is slow once in the mode | PARTIAL |

Order of signal and Present does not matter: in `probe_present_pace`, signalling before Present gave the same slow frames, so the queue itself is held.

## Natural experiment (84 runs since 20 Oct, `rdp_natural_exp_t167.py`, `ev/natural_exp.txt`)

| Session state during run | Runs | With slow frames | Slow / all frames |
|---|---:|---:|---:|
| Connected, local console | 32 | 0 | 0 / 210,855 |
| Disconnected | 31 | 0 | 0 / 194,889 |
| Connected, remote client | 23 | 17 | 16,486 / 52,002 |
| State changed during run | 2 | 2 | 5 / 12,023 |

Slow means `wait_ms` above 50. This is correlation over runs that were not randomised, though the split is total.

## Reproduction

`bench_draw_path`, this RDP session, interleaved, 3 repeats (`ev/val_interval.txt`; T167 binaries, synthetic):

| Case | Interval | FPS | Wait p50 ms | Slow frames |
|---|---:|---:|---:|---:|
| 10 draws | 1 (default) | 11.0 / 11.0 / 10.6 | 93.7 / 93.4 / 93.7 | 595/595 each |
| 10 draws | 0 | 4857 / 4467 / 4609 (uncapped) | 0.0 | 0/595 each |
| 2000 draws | 1 (default) | 10.8 / 10.6 / 10.8 | 73.8 / 68.8 / 75.3 | 395/395 each |
| 2000 draws | 0 | 54.1 / 56.1 / 56.6 | 0.0 | 0/395 each |

`probe_present_pace` (no backend at all), 20 s × 3 cycles, was less uniform: interval 1 ran at 10.9–31.7 FPS and moved between modes; interval 0 ran at 23.7–31.7 FPS with wait p99 at most 4.45 ms and at most 1 slow frame.

No local or disconnected offline run exists, because this session is remote. That side rests on the logs.

## Remaining uncertainties

- Why the mode starts and stops, and whether client or encoder state drives it.
- Whether `RSX_PRESENT_INTERVAL=0` behaves the same in the game (see `GAME_AB_PLAN.md`).
- D3D12 timestamps exist (`RSX_GPU_PROF`), but only the host holds queue state, so nothing here observes the hold directly. The evidence is the fence, the GPU time and the switch.

## T167 arm A (remote from 16 s, 205 s)

The 84 ms mode did **not** occur. 5 of 6,737 frames had `wait_ms` above 50: gframes 773 and 782, about when the session reconnected, and 3083, 4006 and 4018 at about 62 ms wall time. Frames kept 32 FPS, so the mode played no part in the loading stall. This run has one more remote-connected case that never entered the mode, and it adds no evidence on why the mode starts. `wait_ms` is CPU blocking on a fence, not GPU execution, as above. Windows' event logs and the backend, which has no resize handler, show no swapchain or display event. Finer display logs were not enabled.
