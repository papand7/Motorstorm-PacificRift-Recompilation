# T167: GPU-fetch shader compile stall

Source: ps3recomp `8a12a61`. No game launched. Programs are the 34 private `vp_*.hlsl` of T145 A1; only hashes and metrics are stored.

## Cause

**VERIFIED:** fxc inlines and unrolls T162's fetch prologue, once per input and component, so each program compiled about 16 times slower than its CPU-path form, on the render thread. T162 B1's stack was inside `D3DCompile` on the frame-clock thread.

**HYPOTHESIS, strongly supported:** this caused the `GcKernel::Present() Timeout`. Estimated VS compile at race entry: 25 programs × 466–565 ms = 12–14 s. B stalled about 4.5 s when the game gave up; A survives 3.17 s at its worst frame. The exact threshold is unmeasured.

Other compile paths were checked: all HLSL goes through `rsc_compile` (`guest_vp2` at two call sites, `guest_fp`). No DXC is in use. Variant lookup and cache insertion were not timed separately; the compile and PSO figures below account for the stalls measured.

## Compile profile, real programs

`vs_compile_bench_t167.py`, fxc `vs_5_0`, flags 0, 34 unique, 0 failures. Per-program median of 3 repeats, `ev/vs_bench_r3.txt`:

| Variant | Mean ms | Median | Max | Total ms |
|---|---:|---:|---:|---:|
| CPU path | 27.6 | 22.1 | 115.3 | 939 |
| T162 fetch | 466.4 | 390.0 | 989.0 | 15,858 |
| Skip unused inputs only | 223.9 | 154.2 | 711.2 | 7,613 |
| Loop only | 89.5 | 89.8 | 165.6 | 3,042 |
| **Loop and skip (T167)** | **65.3** | **62.6** | **128.0** | **2,220** |

An earlier single-repeat run (`ev/vs_bench_3.txt`) gave 72.1 against 564.9, and the source header quotes those figures. Treat this as about 7–8 times faster. The machine was shared with other agents.

Caveat: the benchmark splices the prologue into captured text and picks inputs from the text, because captures hold no VP ucode. The shipped code uses `rsx_vp_analyze_inputs` on ucode. The two were not compared on game programs.

## Existing game frames, CPU path (T162 A1)

| Frame | VS | PSOs | Total |
|---|---|---|---:|
| Race entry | 25, 798 ms | 51, 1.31 s | 2.24 s |
| Transition | 18, 788 ms | 47, 2.1 s | 3.17 s |

Loop-and-skip alone would add roughly 25 × 65 ms = 1.6 s of VS time at race entry, near the survivable edge. So fetch programs also compile on a worker now.

## Offline runs with `RSX_SHADER_COMPILE_DIAG=1` (synthetic, 3 repeats)

`compile_summary_t167.py`, `ev/compile_summary.txt`. Ranges across repeats:

| Case, fetch | Calls | Unique | Duplicates | Failed | Total ms | Worst ms | On render thread ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| bench, off | 2 | 2 | 0 | 0 | 21–26 | 11–16 | 21–26 |
| bench, sync | 3 | 3 | 0 | 0 | 60–62 | 41–42 | 60–62 |
| bench, async | 3 | 3 | 0 | 0 | 62–64 | 41–43 | 20–21 |
| mixed, off | 5 | 5 | 0 | 0 | 42–44 | 9–10 | 42–44 |
| mixed, sync | 9 | 9 | 0 | 0 | 192–197 | 38–42 | 192–195 |
| mixed, async | 9 | 9 | 0 | 0 | 223–230 | 50–52 | 43–45 |

These workloads have few programs, so they prove the mechanism, not a game-scale gain. **Hit rate was not measured**: `rsc_stats` keeps requests but no run printed them. Zero duplicates means no variant compiled twice. PSO time per variant in these runs was not separated out.

Unchanged and unresolved: with `RSX_SHADER_CACHE=1` the cache is in memory only, so every launch pays again. PSO creation (up to 2.1 s in one frame) stays on the render thread and is the largest remaining stall on either path.
