# T181: integration and performance recovery

Status: **PARTIAL. Integrated, built and tested offline. No game launch, so no FPS or load gain is claimed.** Targets remain goals.

## 1. Revisions

| Item | Value |
|---|---|
| Branch | `agent/t181-integration-performance`, in `ps3recomp-t181` and `root-t181` |
| Code head | `00f76bccf1790e84ec1eaf0f01e170f3bb3ec96f` |
| Base | T180 `b55bf15f`, compared with its recorded suite result |
| Order after base | T171 `7930dcd8`, T176 `7a7edf61` `3724e883`, T179 `e60c6492`, T178 diag `be44d8ec`, T174 `695e000a`, T181 `00f76bcc` |
| Build | `build/motorstorm-t181`, lifted `generated/ppu-t173-staging`, `port-t161`, rc=0. No relift |
| Exe SHA-256 | `a45dee0064d3fdadd62e46b8f71c79699a382786443fb0ff698dad0e52d0e381`, built from that head's source just before the commit |

Inventory and decisions: `INTEGRATION_MATRIX.md`.

## 2. Correction to the T179 report

I reported that T179 arm A never reached the race, probably because of GPU contention. **That was wrong.** Race entry was 125.4 s and the stop 167.7 s, which is race + 42 s. `Present() Timeout` followed `rsxi_trigger` (+25.1 s) and `vel_capture_trigger` (+38.1 s). The same timeout appears in other RSXI capture runs (T165, T169), so a capture stall is the likely cause (HYPOTHESIS).

## 3. Baseline

**About 5 FPS is not representative. It comes from validation runs with the debug layer on** (VERIFIED from logs: `VALID = {'D3D12_DBG': '1'}` in the T179 runner, `d3d12_messages.json` in the T169, T171, T176 and T179 runtimes, absent from T170's). Records cost 8.5-12 us with it and 1.5-1.6 us without.

| Run | Race mean FPS | p50 ms | Setup |
|---|---:|---:|---|
| T170 AA1 | 13.1 | 71 | No debug layer, `RSX_PERF_DEEP` |
| T169 AB1 | 12.9 | 67 | No debug layer |
| T169 DD2 | 10.6 | 94 | Debug layer |
| T171 ATA | 8.5 | 100 | Debug layer |
| T179 a1 | 8.1 | 64 | Debug layer, RSXI; heavy frames about 6 FPS |
| T176 APA, BPB | 6.8, 5.4 | 132, 97 | Debug layer |

T170 by phase: light 14.2, mid 13.7, heavy 11.2 FPS. These logs still carry deep profiling and per-frame diagnostics, so a clean figure is unmeasured. Nearly every optimization is opt-in (`RSX_VS_MEMO` is the exception among those checked): **an unflagged launch runs slow paths**, so the matrix pins flags.

Loading is separate: load screen to race entry takes 85-90.8 s polling and 20-22 s with wake (T161, older build). The gate has never run.

## 4. Frame costs and optimizations

T170 heavy race, p50 77 ms, no debug layer, one run. Figures overlap: `pso`, `tex` and `cmd` sit inside `record`.

| Rank | Cost | ms | Evidence-backed action | Status |
|---|---|---:|---|---|
| 1 | Vertex expand and upload | 30.9 | Fast fetch, then indexed. UPLOAD writes 5.3 GB/s on RTX | Bench only |
| 2 | Record | 30.7 | | |
| 2a | `pso` | 15.5 | FP scan memo | Bench only |
| 2b | `cmd` | 9.9 | T159 state dedup, not integrated | Unmeasured |
| 2c | `tex` | 5.3 | None | |
| 3 | Other, guest side | 13.9 | None yet | Unattributed |
| | GPU fence wait | 0.1 | The GPU is not the limit | |

No new optimization was written: existing flags cover the ranked costs and lack only a game run. Physics and gameplay logic are untouched.

Bench on T181 (`bench_draw_path`, heavy, 6,900 draws, default 2.93x reuse, median wall of 3). **Synthetic, not game numbers.** The RTX shared the machine with another GPU load (91 % utilization, 7.5 GiB in use at the end), so its timings are noisy; both + indexed peaked at 109 ms.

| Arm | RTX ms | AMD ms | Pixels vs T174 binary, RTX | AMD |
|---|---:|---:|---|---|
| Off | 83.2 | 58.8 | 6/6 | 6/6 |
| Fast fetch | 70.2 | 47.7 | 6/6 | 6/6 |
| Memo | 72.5 | 46.5 | 6/6 | 6/6 |
| Both | 57.2 | 34.9 | Not run | Not run |
| Both + indexed | 37.4 | 23.1 | 6/6 | **0/6** |
| Indexed alone | Not timed | Not timed | 6/6 | **0/6** |
| Poly offset; depth volume | Not timed | Not timed | 6/6 each | 6/6 each |

The polygon-offset and depth-volume matches only show no change on this workload. Indexed gain depends on vertex reuse: T174 measured 18 % at 1.5x, and the game's real reuse is unknown, so expect less than this table.

## 5. Candidates

Same exe; flags decide. Both exclude the debug layer, RSXI, visual diagnostics and frame dumps.

| | A Conservative | B Performance |
|---|---|---|
| Base | T170 lean flags without deep profiling or stats | Same |
| `PS3_LWCOND_WAKE=1:poll_ms=100:stats_ms=1000:heavy_draws=200` | On | On |
| `RSX_VP_FAST_FETCH`, `RSX_FP_SCAN_MEMO` | Off | On |
| `RSX_VP_INDEXED` | Off | On, RTX only until the AMD difference is explained |
| `RSX_SHADER_CACHE` | 1 | 3 |
| `RSX_POLY_OFFSET`, `RSX_DEPTH_VOLUME` | Off | Off |

## 6. Offline validation

| Check | Result | Label |
|---|---|---|
| Full suite through `env_t169.cmd` | **157 pass, 0 fail, 43 skip**, private `suite.txt` | VERIFIED |
| Base T180, recorded | 126 pass, 2 fail, 43 skip | VERIFIED |
| Base failures | `test_rt_pool_srv_layout`, `test_vpc_watch`; both pass here after T176's pin repair | VERIFIED |
| `test_t119_pins`, `test_vp_fetch_plan`, `test_vp_indexed`, `test_lwcond_wake`, `test_dev_guest_str` | Pass | VERIFIED |
| WARP fixtures | All 7 in the suite pass | VERIFIED |
| RTX, AMD pixels | Table above, private `ev/validate.txt` | VERIFIED |
| Runner | `prepare` and `envcheck` pass; arm differences are exactly the flags listed. `dryrun` stops at preflight | PARTIAL |
| Public audit | Code `--tree` on copies of the changed files: passed. Report: `--staged --private-reports` | VERIFIED |

## 7. Proposed runtime comparison (not authorized, nothing launched)

`generated/analysis/t181/ab/run_t181.py`, generated by `tools/make_runner_t181.py`; exe pinned. Fresh HDD copy, no retries, stop at race + 75 s or the 200 s cap. A polling run reaches the cap near race + 75 s, past the T170 crash at race + 54 s.

| Order | Arm | Flags beyond R | Decides |
|---|---|---|---|
| 1 | R | None, polling | Clean baseline; T173 fix |
| 2 | A | Wake gate | Load time, gate, FPS cost |
| 3 | B | A + all B flags, fills cache | Combined gain |
| 4 | W | Same as B | Warm shader cache |
| 5 | F | A + fast fetch | Individual effect |
| 6 | M | A + memo | Individual effect |
| 7 | X | A + fast fetch + indexed | Indexed effect |
| 8 | V | A + poly offset + depth volume, frame dumps | Visuals, not FPS |
| 9, 10 | S, T | A + config boot | `DIRECT_RACE_STARTUP.md` |

Minimum: R, A, B, W (4 launches). Record load time, average FPS, 1 % low, CPU and GPU frame time, peak RAM and VRAM, frame dumps and crashes. Primary `f373398c` has no isolated build and lacks these flags, so it is left out; T169 AB1 and T170 AA1 are the historic reference.

## 8. Blockers and risks

- **Preflight fails now:** `llama-server` and `eabackgroundservice` running, 562 MiB VRAM free against 6,000 required. The runner refuses until cleared. LeOffice and Godot are allowed, as the user decided; the runner logs them.
- The T173 fix, gate, fast fetch, memo and indexed have no game evidence.
- `Other` 13.9 ms and the load-side event-flag, usleep and main-CPU time remain unattributed.
- 60 FPS and under 10 s load have no supporting path. 15-30 FPS and under 20 s are plausible, unproven.

## 9. Next steps

1. Authorize launches and free the GPU.
2. Run R, A, B, W, then individual arms for whatever B changes.
3. Explain the AMD indexed difference before any default change.
