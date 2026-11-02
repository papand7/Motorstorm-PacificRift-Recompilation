# T182: runtime validation, R, B, D

Status: **PARTIAL. All three arms ran stably and the performance question is answered for this run set, but rendering correctness is not established: these arms have no frame captures.**

- **`RSX_VP_DIRECT` gave no steady race FPS gain:** 14.62 FPS (B) against 14.61 FPS (D). It cut vertex expansion by 14 %, but that time did not reach the frame rate.
- **Candidate B's real gain is mainly loading:** 88.5 s down to 19.6 s. Its race gain is about 4-5 % (one run per arm).
- **The render thread no longer sets the frame rate** (see section 7). Further vertex work is unlikely to raise FPS until `other_ms` is attributed.

Each figure comes from one run per arm, so small differences are not proven repeatable.

## 1. Identity

| Item | Value |
|---|---|
| Code | `e9ba485f8f9cbb2556e19fdfb45acd7867cb5aa1`, `ps3recomp-t182` |
| Exe SHA-256 | `a1cd6f1f0080413edf9a4ae2b8b2e922aa48198a9fb8883e5b397e5445d53786`, checked before every launch; not rebuilt |
| `EBOOT.BIN` | `218cd8aa99355583026f203fcbbda03e17f6900118a942f7f086b556ea4994af` |
| `PARAM.SFO` | `7cc3a4bd552a600d61acfb3eec6dc017d8b426372f54987019cbf4dd4cff608e` |
| `EBOOT.elf` | `bbb7fe2545e54847483439f59cda54e907db23a111d7afe9a1b655624886b287` |
| Launches | **3 of 3, no retries** (`launches_used.jsonl`): `Rr1` 21:50:49, `Bb1` 21:54:35, `Dd1` 21:56:53 |
| Runner | `generated/analysis/t182/ab/run_t182.py` |
| Scene | Same pad route and race (`Track1a`), RTX 5060. The same resolution and settings come from the shared runner, not from a separate check |

## 2. Arm configuration

All arms share the lean flags, with no debug layer, RSXI, frame dumps or `RSX_PERF_DEEP`.

| Flag | R | B | D |
|---|---|---|---|
| `PS3_LWCOND_WAKE` | Off | `1:poll_ms=100:stats_ms=1000:heavy_draws=200` | Same as B |
| `RSX_VP_FAST_FETCH` | 0 | 1 | 1 |
| `RSX_FP_SCAN_MEMO` | 0 | 1 | 1 |
| `RSX_VP_INDEXED` | Off | 1 | 1 |
| `RSX_SHADER_CACHE` | 1 | 3, cold directory | 3, reusing B's cache |
| `RSX_VP_DIRECT` | Off | Off | 1 |

Logs confirm `[vp-indexed] on` in B and D, `[vp-direct] on` only in D, and `pipeline library on (loaded, 2067718 bytes)` in D.

## 3. Preflight

| Check | R | B | D |
|---|---|---|---|
| Local console (`query session`; `TerminalServerSession` False checked for R and B) | Pass | Pass | Pass |
| llama-server, Ollama, Epic and EA processes | None | None | None |
| Free VRAM, runner's check (at least 6,000 MiB) | 7,625 | 7,578 | 7,599 |
| Free RAM (at least 16 GB) | 37.2 GB | 37.2 GB | 36.6 GB |
| Exe, game-data hashes | Pass | Pass | Pass |
| Dry run and flags | Pass | Pass | Pass |

**Changes made to the machine:**

- I stopped `llama-server` (PID 11460), as the brief asked.
- I also stopped the Windows service `EABackgroundService`, which the brief did not name, because the runner's preflight refuses to launch while it runs.
- Neither has been restarted.

**Limits of the "unnecessary profiling off" check:**

- `RSX_FRAME_PERF` and the `PS3_TRACE_FILE` function trace stayed on in all arms: the measurements and the pad route depend on them.
- Logging ran at about 1,200-1,900 lines/s (40-44 MB per run), so absolute FPS may rise slightly without it.
- LeOffice stayed open, as you decided earlier, and used some CPU (about 0.3 core in the D sample inspected).

## 4. Stability

| | R | B | D |
|---|---|---|---|
| Stop | Race + 75 s | Race + 75 s | Race + 75 s |
| Unresolved indirect calls, `Present() Timeout`, device removal | 0 | 0 | 0 |
| Frames over 1 s | 3 | 2 | 0 |
| `[stall]` snapshot lines | 49 | 49 | 0 |

- **T173 fix: VERIFIED in these runs.** All three arms passed the T170 crash point at race + 54 s, and R ran with lean polling flags.
- **Exit code 1 is the stop itself:** the wrapper reports `exited_error` in every arm, and the runner stops the game with `taskkill /F`. No fatal line was logged.
- **Long frames are shader work (inferred):** each frame over 1 s also has at least 16 PSO misses and over 800 ms of miss time.
- **Other log lines:** the failed-open and unresolved-NID lines are identical across arms. B and D differ only in `[stall]` and normal trace lines.

## 5. Loading

| Seconds | R | B | D |
|---|---|---|---|
| Last menu press (loading-screen entry proxy) to race entry | **88.5** | **19.6** | **17.1** |
| Race loader `0008EA00` | 85.46 | 16.75 | 16.56 |
| Loader return to race entry | 2.54 | 2.65 | 0.36 |
| Process start to race entry | 123.9 | 41.3 | 38.6 |
| Average host CPU cores during load | 0.50 | 1.71 | 1.61 |

- **R to B: VERIFIED as a measurement.** Flags were not tested singly, so the attribution to the wake gate is a HYPOTHESIS, though it matches T161's 85-90 s and 20-22 s.
- **B to D:** the 2.5 s saving falls after the loader returns, where the shader cache acts. It reflects cache warming, not `RSX_VP_DIRECT`.

## 6. Race performance

Frames with at least 1,000 records.

| All race frames | R | B | D |
|---|---:|---:|---:|
| Frames | 1,063 | 1,092 | 1,124 |
| Average FPS | 13.73 | 14.07 | 15.08 |
| Median ms | 70.0 | 67.4 | 68.0 |
| p95 ms | 80.4 | 76.4 | 75.9 |
| p99 ms | 129.6 | 122.6 | 80.1 |
| Max ms | 2,400 | 2,507 | 618 |

**D's higher all-frame FPS is cache warming, not a direct-path gain.** The steady window removes it. It starts 20 s after the first race frame and drops frames with a shader miss, plus the 5 frames after each.

| Steady frames | R | B | D |
|---|---:|---:|---:|
| Frames | 768 | 810 | 773 |
| **Average FPS** | **14.00** | **14.62** | **14.61** |
| Median ms | 71.0 | 68.1 | 68.6 |
| p95 ms | 79.2 | 74.7 | 73.7 |
| p99 ms | 84.9 | 79.9 | 77.7 |
| Records | 4,322 | 4,393 | 4,311 |
| Vertices | 304,752 | 155,522 | 157,542 |
| Upload MB/frame | 74.4 | 38.0 | 38.5 |
| Expand ms (vertex conversion) | 23.0 | 18.4 | 15.7 |
| Flush ms (upload path) | 15.1 | 8.0 | 8.0 |
| Drain ms | 44.4 | 31.9 | 28.9 |
| Record ms (D3D12 recording) | 15.9 | 8.7 | 8.4 |
| Texture ms | 2.7 | 2.5 | 2.5 |
| PSO ms | 5.9 | 0.4 | 0.4 |
| Command ms | 7.0 | 5.6 | 5.5 |
| GPU wait ms | 0.1 | 0.0 | 0.0 |
| **Other ms** | **21.9** | **33.3** | **35.4** |

Values are medians, except average FPS.

| Resources, race | R | B | D |
|---|---:|---:|---:|
| Average host cores | 3.43 | 3.24 | 3.25 |
| Busiest thread, average of one core | 0.65 | 0.57 | 0.57 |
| System busy | 57 % | 51 % | 50 % |
| GPU utilization, 15 s samples, whole run | 3-12 % | 0-12 % | 0-14 % |
| Peak VRAM, same samples, MiB | 1,112 | 1,065 | 1,128 |
| Peak working set, MB | 669.8 | 671.0 | 669.5 |
| Peak private, MB | 1,162.7 | 1,168.8 | 1,167.2 |

Shader counters, race frames:

| | R | B | D |
|---|---:|---:|---:|
| PSO misses, time | 131, 4,371 ms | 134, 4,697 ms | 131, 1,068 ms |
| VS misses, time | 56, 2,113 ms | 59, 2,345 ms | 55, 8 ms |
| Frames with a miss | 16 | 16 | 17 |

The log has no direct cache hit or miss count. A "miss" here is the backend's own lookup missing, so D still counts one even when the disk cache makes it cheap. D was not fully warm: the cache grew from 193 to 211 files during D, so it wrote new entries.

## 7. B against D

| Confounder | Handling | Result |
|---|---|---|
| Cache warming | Steady window | Removed from the steady figures; D's first 20 s gain is excluded |
| Remaining shader work | Frames with misses and the next 5 dropped | Removed |
| Draw workload | Bins of 250 records, at least 10 frames in each arm | 705 of 810 and 773 frames matched |
| Vertex reuse | `[vp-indexed]` | 3.139 and 3.134, close to the bench's 2.93x column |
| Uploaded bytes | Matched frames | 37.69 and 38.25 MB, D 1.5 % higher, with 1.5 % more vertices |
| Fallbacks | `[vp-indexed]` | 0 in both |
| Same route | Same input script | Per-phase records track closely, but frames were not compared one by one |
| Repeatability | None possible with one launch per arm | **Noise is unmeasured** |

| Matched steady frames | B | D | Change |
|---|---:|---:|---:|
| Frame ms | 67.98 | 68.69 | +1.1 % |
| FPS | 14.71 | 14.56 | -1.0 % |
| **Expand ms** | **18.36** | **15.75** | **-14.2 %** |
| Flush ms | 9.28 | 8.85 | -4.6 % |
| Drain ms | 32.48 | 29.53 | -9.1 % |
| **Other ms** | **31.86** | **35.66** | **+11.9 %** |

Both halves of the steady window show the same pattern: expand 18.2 to 15.2 ms and 18.6 to 16.0 ms, median frame 66.9 to 67.0 ms and 68.7 to 69.8 ms.

**Findings:**

- **Expand gain: VERIFIED in this run set.** It held across every matched bin and both halves.
- **FPS gain: none measured.** The 1 % difference is too small to call a loss without repeats.
- **Why the saving disappears: HYPOTHESIS.** The 2.6 ms expand saving and the 3.8 ms rise in `other_ms` nearly cancel. R to B shows the same pattern: drain fell 11.7 ms on matched frames, `other` rose 8.6 ms, and the frame fell 3.5 ms. That fits a render thread now waiting on the guest (PPU, SPU or their sync), but `other_ms` isn't split into waiting and work.
- **What's ruled out:** the GPU (0.0 ms wait, under 15 % utilization). Frame times spread across 60-80 ms, so there is no sign of fixed 16.7 ms pacing. No host thread averages above 0.65 of a core, so one saturated host thread isn't an obvious cause, though averages can hide bursts.

**R to B, steady:** frame time fell about 4-5 % (matched 71.8 to 68.3 ms) while upload fell about 50 %. R and B also differ in the wake gate and cache mode, so no single flag gets the credit.

## 8. Rendering correctness: not established

**R, B and D captured no frames and I did not look at the game window** (`frames` directories are empty; the runner strips dumps from these arms). Nothing below is visual evidence.

| Check | Status | Evidence |
|---|---|---|
| Missing or corrupted geometry | **Not assessed** | Logs only: 0 indexed fallbacks, no device errors |
| Vertex attribute errors | **Not assessed in game** | T182 source review and synthetic pixel match only |
| Textures, materials | **Not assessed** | |
| Dark terrain squares | **Not assessed** | No cause or fix known; no change expected |
| Faint polygon overlays | **Not assessed** | `RSX_POLY_OFFSET` and `RSX_DEPTH_VOLUME` off in all arms |
| Vehicle reflections | **Not assessed** | |
| New B and D differences | **Not assessed** | Similar records and vertices per phase; that is workload, not pixels |

The stop condition for substantial corruption could not fire from logs alone, so proceeding to D doesn't show B rendered correctly.

### T162 SRC2 abs

**PARTIAL.** The correction ran in all three arms without a shader failure line. T162's corpus check (`t162/VEHICLE_RENDERING_FIDELITY.md`) found 151 of 151 race fragment programs byte-identical in HLSL, with no `abs` sources at all. So for that corpus it changes nothing. These runs did not capture fragment programs, so that corpus was not re-verified against them, and menus or other tracks may differ.

## 9. Measured against hypothesis

| Claim | Label |
|---|---|
| T173 fix passes race + 54 s, in these arms | VERIFIED |
| Load 88.5 s to 19.6 s, R to B | VERIFIED, one run each |
| Upload halved at 3.14x reuse, R to B | VERIFIED, one run each |
| Steady FPS +4-5 %, R to B | Measured; noise unmeasured |
| `RSX_VP_DIRECT` expand -14 % | Measured, consistent within the run |
| `RSX_VP_DIRECT` FPS gain | **Not found** |
| Warm cache removes stalls over 1 s | Measured once; also depends on the cache state from B |
| Wake gate causes the load gain | HYPOTHESIS |
| Guest side is now the limit | HYPOTHESIS |
| In-game rendering matches across arms | **Unknown** |

## 10. Remaining risks

- One run per arm, with no measure of run-to-run noise.
- No in-game visual check of any arm.
- `RSX_SHADER_CACHE=3` in D reused B's cache from the same exe and flags; a stale-cache case was not tested.
- AMD remains unvalidated in game; its indexed pixel difference is still unexplained.
- Absolute FPS includes tracing and logging overhead.
- The goals of 60 FPS and sub-10 s loading have no path in this data.

## 11. Recommendation

**Do not integrate `RSX_VP_DIRECT` as default-on, and do not treat it as an FPS improvement.** Keep it recovered and off. It adds no measured FPS benefit today, and correctness is unchecked in game. It may become useful only after the guest-side limit moves. Merging nothing was part of this brief, so nothing was merged.

Candidate B's load gain is the strongest result, but it also needs a visual check before any default changes.

**Further testing needs separate authorization.** These would answer the open questions:

1. A frame-dump comparison of R, B and D, outside timed windows, to decide correctness.
2. A run with `PS3_SAMPLE_TOP` to attribute `other_ms`.
3. Repeat B and D arms with the same warm cache, to measure noise.

## 12. Evidence

Tools: `tools/runtime_ab_t182.py`, `tools/runtime_extra_t182.py`. Private and untracked: `generated/runs/*-t182-{Rr1,Bb1,Dd1}`, `generated/analysis/t182/ab/runtime-*`, `generated/analysis/t182/ab/shader_cache`.
