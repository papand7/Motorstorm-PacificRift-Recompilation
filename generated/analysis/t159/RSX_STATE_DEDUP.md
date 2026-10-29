# T159 — RSX live-draw D3D12 state deduplication

Code worktree `ps3recomp-t159-state-dedup`, branch `agent/t159-rsx-state-dedup`, base `c535cc0`
(T157 integration: T155/T156 included), code commit `12b1d78`. Report worktree `root-t159`, branch
`agent/t159-rsx-state-dedup`, base `5836fd3`. No game launch: every number below is from the
Windows host D3D12 device driven by the synthetic live-draw harness. Nothing was pushed or merged;
the runtime library and the harness executables were built in `build/ps3recomp-t159/` (Release,
clang-cl 23.1.3, no `YZ_PERF_PROFILE`).

The change is off by default. `RSX_STATE_DEDUP=1` turns it on; without the variable the renderer
records exactly the same calls as `c535cc0` (each wrapper has a `!enabled` fast path that calls the
original method).

## 1. What the cache covers

VERIFIED (source: `libs/video/rsx_live_draw.c`, all call sites of the game path):

| slot | D3D12 call | deduped | invalidation |
|---|---|---|---|
| `LD_ST_PSO` | `SetPipelineState` | yes | value change only |
| `LD_ST_ROOTSIG` | `SetGraphicsRootSignature` | yes | value change; also clears `LD_ST_SAMPLER` |
| `LD_ST_HEAPS` | `SetDescriptorHeaps` | yes | heap pointer/count change; also clears `LD_ST_SAMPLER` |
| `LD_ST_VIEWPORT` | `RSSetViewports` | yes | value change |
| `LD_ST_SCISSOR` | `RSSetScissorRects` | yes | value change |
| `LD_ST_TOPO` | `IASetPrimitiveTopology` | yes | value change |
| `LD_ST_SREF` | `OMSetStencilRef` | yes | value change |
| `LD_ST_SAMPLER` | `SetGraphicsRootDescriptorTable(2, …)` | yes, by GPU handle | value change; rootsig or heap change |

Deliberately **not** deduped, and why:

- `SetGraphicsRootDescriptorTable(1, …)` (SRVs) and `(3, …)` (vertex textures): a new ring slot is
  allocated per draw and its source descriptors can be rewritten in place, so "same handle" does not
  imply "same state". These stay on the unconditional path (`rsx_live_draw.c:3499`, `:3638`,
  `:7957`, `:7960` in the committed tree).
- Root arguments 0 and 4 (constant-buffer views, including the per-draw frame and pixel-shadow
  constants) and the downsample/blit root constants: their value changes per draw by construction.
- `OMSetRenderTargets`, `IASetVertexBuffers`, `IASetIndexBuffer`: not part of this task; render
  targets still change every draw, and the vertex/index bindings are already built per draw. Listed
  as follow-up work in §6.
- `SetComputeRootSignature` / compute descriptor tables of the depth-snapshot pass: outside the
  graphics root signature. The pass drops the cache instead of modelling compute state.

The cache is command-list-local state. `ld_flush()` drops it immediately after
`ID3D12GraphicsCommandList::Reset` (every binding is undefined after a reset), and `zdepth_snapshot`
drops it before it changes the pipeline/heaps outside the wrappers. Both paths are in the same
commit.

Sampler dedup relies on two properties of the existing code: `sampler_table()` returns a cached
handle only for an identical slot set, and sampler descriptors are append-only, so equal GPU
handles are equal state. If that function ever starts reusing slots for different sampler
descriptions, this slot must be revisited.

## 2. Calls recorded per draw

VERIFIED (`[rsx-state-dedup]` counters printed at `rsx_live_draw_shutdown`, same run):

| run | state calls wanted | recorded | skipped |
|---|---|---|---|
| `test_live_draw_state_dedup` (10 draws) | 80 | 23 | 57 |
| bench, identical state, 7 000 draws | 56 000 | 16 | 55 984 (99.97 %) |
| bench, PSO changes every draw, 7 000 draws | 56 000 | 7 014 | 48 986 (87.5 %) |
| bench, identical state, 70 000 draws | 560 000 | 144 | 559 856 (99.97 %) |

Steady state is eight wrapped calls per draw. The non-zero baseline at 7 000/70 000 identical
draws is the command-list ring: `ld_flush` runs about every 3 900 draws, and each reset makes the
next draw record all eight slots again (16 = 2 × 8 at 7 000; 144 = 18 × 8 at 70 000). The
PSO-alternating case records the unavoidable `SetPipelineState` (plus the same two resets) and
skips the other seven.

## 3. Correctness

VERIFIED — `libs/video/tests/test_live_draw_state_dedup.c`, built against the committed runtime
library, run twice in separate working directories with `RSX_STATE_DEDUP=0` and `=1`:

- four identical draws (same PSO, rootsig, heaps, viewport, scissor, topology, stencil, samplers);
- scissor change to the other half, colour change, another identical draw;
- render-target switch 64×64 → 32×32 with a viewport/scissor change and a different pipeline;
- switch back to 64×64, then `rsx_live_draw_flush()` (command-list reset), then a scissor/colour
  change and one more draw;
- read back both targets through `rsx_live_draw_debug_dump_surface` and check pixels.

Result both arms: `5 passed, 0 failed`. PPM dumps are byte-identical:

```
state_dedup_a.ppm  12 301 B  sha256 DAAD4DAB8C046C7C3D7F0D704E4109BC1B8583DFD363A4694C8407103AF125B4
state_dedup_b.ppm   3 085 B  sha256 C308E6DA46B19B0F92C4AB53E35CDB8DEB7D00995DEBB237843FB28C5F6CF916
```

VERIFIED — the pre-existing live-draw suites, run in both arms from separate directories; every
test prints `0 failed` and all 12 dumps it writes are byte-identical between the arms:

| test | result (both arms) | dumps compared |
|---|---|---|
| `test_live_draw_alias_subrect` | 2 passed | `alias_subrect_e.ppm` |
| `test_live_draw_depth_export` | 5 passed | `depth_export_e.ppm`, `depth_export_f.ppm` |
| `test_live_draw_z16_clear` | 4 passed | 4 × `z16_clear_*.ppm` |
| `test_live_draw_depth_textures` | 2 passed | `depth_textures_e.ppm` |
| `test_live_draw_aa_surface` | 8 passed | `aa_surface_{0,3,4,5}.ppm` |

`test_live_draw_depth_export` is the important one here: it runs the depth-snapshot compute pass,
i.e. the path that changes the compute root signature and the heaps outside the wrappers, so it
exercises the cache-drop before the next graphics draw.

PARTIAL: this proves pointer/state equivalence on the host path and identical output for the
covered transitions. It does not prove the game's frame is unchanged; that needs a bounded,
draw-gated capture run, which was out of scope for this task.

## 4. Benchmark

SYNTHETIC, `libs/video/tests/bench_live_draw_state.c`: 64×64 colour target with Z24S8, the same
one-quad draw repeated through `rsx_live_draw_method`, timed with `QueryPerformanceCounter` around
the draw loop only (the final GPU drain is outside the timer; the intermittent ring flushes inside
it are identical in both arms). Five process runs per arm, warm-up run discarded, medians shown.
The two arms were run alternately to spread machine drift.

Identical state every draw (`change_every=0`):

| draws | dedup off (ms) | dedup on (ms) | delta |
|---|---|---|---|
| 7 000 | 18.448 (17.718–20.458) | 18.194 (17.816–18.875) | −1.4 % median |
| 70 000 | 166.172 (165.367–168.129) | 162.978 (162.154–163.998) | −1.9 % median, all 5 pairs lower |

Pipeline state changing every draw (`change_every=1`, 7 000 draws): 22.021 ms off vs 21.996 ms on
(−0.1 %), i.e. within run-to-run noise. Recording costs ≈ 2.6 µs per draw, and the wrapped state
calls are a small part of that: guest method processing, vertex expansion, constant upload and SRV
ring allocation dominate. At the 7 000-draw size the effect is at the edge of noise; at 70 000 draws
it is consistently ≈ 2 %. The deterministic result is the call count: 99.97 % of the wrapped setters
are elided in the steady state.

## 5. Integration

```
RSX_STATE_DEDUP=1 <runtime>
```

On startup the renderer prints `[rsx-state-dedup] on`, at shutdown
`[rsx-state-dedup] calls_recorded=<n> calls_skipped=<n>` (stderr). Unset or any value other than
exactly `1` keeps the old behaviour and prints nothing. No build flags, assets, shaders or
generated code change; the patch is 228 added / 21 removed lines in
`libs/video/rsx_live_draw.c` plus the two test files. To drop the feature, revert commit
`12b1d78`.

## 6. Limitations / follow-up

- `OMSetRenderTargets` is still recorded on every draw (the live path switches targets often). A
  render-target slot is the obvious next candidate, but it must invalidate nothing else and needs
  its own test with overlapping RTVs.
- Root signature: only the graphics signature is cached. The compute signature of the
  depth-snapshot pass is not, deliberately.
- Descriptor-heap changes are internal to `rsx_live_draw.c` (heaps are created once), so the heap
  slot is defensive rather than load-bearing; the heap-change invalidation is therefore not
  reachable from the test harness.
- Sampler-handle dedup depends on the sampler table's append-only, slot-set-keyed behaviour (§1).
- No in-game A/B was run; the game-level CPU effect is unmeasured.
