# T162 — final validation

2026-10-30. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED.

**Status: offline correctness VERIFIED, exe pinned, game A/B BLOCKED on the texture A/B gate. No game launched; no in-game number exists.** GPU fetch stays off by default.

## Commits

- ps3recomp `agent/t162-gpu-vertex-pipeline`: `d1bec5b`, `a89cf5f`, `8c68a76`, `ee8b13c` (nopso fix), `69489f2` (final; moves the spill release after the pinned entry-drain lines and repairs a `test_gvf` pin).
- The texture work (`a049b1e`) is not in this tree. No texture change was cherry-picked.

## Suite

| Tree | Pass | Skip | Fail |
|---|---|---|---|
| `8c68a76` (§3A) | 143 | 43 | 2 known: `test_rt_pool_srv_layout`, `test_vpc_watch` |
| `ee8b13c` | 140 | 43 | 5: the 2 known, plus `test_gpu_sync` and `test_gvf` (my fix) and `test_d3d12_shader_cache` (below) |
| `69489f2` (final) | 143 | 43 | 2 known |

**Intermittent crash, not caused by T162, cause unproven (PARTIAL).** The harness of `test_d3d12_shader_cache` crashes with 0xC0000374 or 0xC0000005 and no stdout: 6 of 40 runs on `59fcab5` (T157), 5 of 40 on `8c68a76`, 3 of 25 on the working tree of `ee8b13c`. It predates T162 and passed in the `8c68a76` and `69489f2` suite runs by chance. Source review found no fault in `rsx_shader_cache.h` or the test's threads; unlocked concurrent `D3DCompile` at `rsx_shader_cache.h:555` is an untested suspect. The crash site was not captured. Whether the game can reach it is not established.

## Forced failure (`tools/nopso_regress_t162.py`, final commit): VERIFIED

45 checks pass, 0 fail, debug layer silent. Cases none, all (`FP_OFF=1`), mix (`RSX_TEST_FP_FAIL_EPOCH=3`) × arms cpu, gvf, gvf4 (early replays), spill (own buffer per fallback).

- Every arm's presented frames are byte-identical to the CPU arm of the same case, so fallback output, draw order and resource state match the CPU path on this harness.
- Counters: `nopso` = `cpu_drawn`, `lost` = 0. Full `all` and `mix` counts were recorded on `ee8b13c`: all 7,249 draws / 4,858,614 corners, mix 2,418 / 1,618,851.
- The frames are not blank; all differs from none, and mix from both, so the forcing really reached the fallback.

## Differentials

- Renderer snapshots (`harness/correct_draw.sh`, `tools/cmp_draw_t162.py`), final commit: heavy, light, seam × fat, gvf, gvf4, gvf rerun: 12 of 12 arms byte-identical to cpu, 0 debug-layer messages in 15 runs. VERIFIED.
- Vertex fetch, seeds 1–5 on WARP, AMD and RTX, 15 runs, 400 draws each: 0 words differ, on `ee8b13c`. Not repeated on `69489f2`, which changes no fetch code; the suite's `test_gvf` passes there.
- These are synthetic streams. Game streams are unproven until the A/B compares them.

## Exe

| Item | Value |
|---|---|
| SHA-256 | `5098e7e31f8dd17f2c05d56e0263faeeec93ac2b5cdd8807f7b9a9fdd24c8573` (`ab/exe_g/`) |
| ps3recomp | `69489f2c311297b347ae6f65f811dd85123786d0`, detached `ps3recomp-t162-exe` |
| Root | `5407ee4`, port `port-t161` |
| Compiler | clang-cl LLVM 23.1.3, `/O2 /Ob2 /DNDEBUG`, Release, Ninja |
| Inputs | `generated/ppu-hooked-staging`, Wws AOT `generated/spu_raw/wws_reloc_t81c`, Havok `--chain-chunks` (`tools/build_t162.cmd`) |
| Env | `ab/run_t162.py`: A = T161 arm C + `RSX_GPU_PROF=60`; B = A + `RSX_GPU_VERTEX_FETCH=1`; D = T161 arm C + `RSX_VTX_STATS=1000` |
| Caps | 195 s game, 210 s hard, `PS3_FC_WATCHDOG_MS=2000`, fresh HDD copy per run, hash check per launch (`ab/seq_t162.sh`) |

## Launch gate: BLOCKED

The launches require that the texture A/B has completed or that its owner has confirmed it will not overlap. It has not started: there is no `performance_next/ab/seq_et.log` and no runs. No live session claims it. One peer session disclaimed it and said its notes name this session; a second left without answering. Neither counts as the owner's confirmation.

## Still to deliver after the launches

`GAME_AB_RESULTS.md`, individual and frame-matched runs, rendering comparisons, real fetch coverage, remaining bottlenecks and the integration recommendation. **Current recommendation: do not merge or enable; there is no game evidence.**
