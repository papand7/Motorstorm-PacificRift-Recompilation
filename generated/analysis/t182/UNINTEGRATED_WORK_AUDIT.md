# T182: unintegrated work audit

Status: **PARTIAL. Nine items recovered on an isolated branch and validated offline. No game launch, so no runtime benefit is established.** Nothing was merged into primary or T181, nothing pushed, no relift. Other worktrees were only read.

## 1. Revisions

| Item | Value |
|---|---|
| Base | T181 `00f76bccf1790e84ec1eaf0f01e170f3bb3ec96f`, verified as `ps3recomp-t181` HEAD |
| Head | `e9ba485f8f9cbb2556e19fdfb45acd7867cb5aa1`, `ps3recomp-t182`, branch `agent/t182-unintegrated-recovery` |
| Exe | `build/motorstorm-t182`, lifted `generated/ppu-t173-staging`, rc=0, SHA-256 `a1cd6f1f0080413edf9a4ae2b8b2e922aa48198a9fb8883e5b397e5445d53786` |

## 2. Recovered

Each is one commit or a pair, so `git revert` undoes it.

| Commit | Source | Change | Default | Tests | Class |
|---|---|---|---|---|---|
| `753ff8d9` | T175, uncommitted | `RSX_VP_DIRECT` | Off | `VERTEX_PIPELINE_RECOVERY.md` | EXPERIMENTAL |
| `d9046ca4` | New, test only | `BENCH_NO_DEPTH` in the bench, for the AMD experiment | Off | Used there | READY |
| `3c6f4e45` | T162 `684d8bd2` | FP decoder honours the SRC2 abs bit | **On, the only default-on change** | `test_t162_fp_src2_abs` 9 checks, 0 failures, by hand | READY; needs a game frame check |
| `bd0a34ae`, `cbbd4cb8` | T169 `d2d9ef91`, `66b5478a` | `RSX_RT_REINTERP` decodes both fetch spellings; real counters | Off | `test_t169_rt_reinterp`, `test_rsxi_geom` | EXPERIMENTAL |
| `cbf85a43` | T152 `9e393ce2` | `PS3_SAMPLE_TOP`, wider sampler report; can help attribute the 13.9 ms guest time | Off | Suite | READY |
| `fe2225f2` | T163 `6fbbc051` | `RSX_VTX_PARTIAL_0001`, RPCS3-style fill for arrays under 4 components | Off | Both T163 tests | EXPERIMENTAL |
| `e4abbe29`, `e9ba485f` | T168 `800287cc`; test glue | `RSX_DRAW_DUP_DIAG` | Off; 4 walker counters always count | `test_draw_dup` pass. `test_gcm_fifo_replay` **not run**: no Windows link recipe here | READY as a diagnostic, partly tested |
| `e7de5b6c` | T167 `8a12a61a`, interval hunk | `RSX_PRESENT_INTERVAL`; a new line prints the setting at start | Unset = as before | Three updated Present pins | EXPERIMENTAL |
| `93afa74e` | T167 `61d32fdc`, without `[vca]` | `PS3_KEEP_TIMER_RES`, `RSX_TIMER_DIAG` | Off | `test_host_timer_res` | EXPERIMENTAL |

Conflict fixes: both T169 conflicts were by hand in `rsx_d3d12_backend.c`. In the second, the indexed `vp_drawn:` label now sits before the decode counter, so indexed draws are counted too. The SRC2 change alters generated HLSL, and the shader cache keys on HLSL, so it can't reuse an old entry.

## 3. T162, T167, T168

| Commit | Function | Why excluded before | Decision |
|---|---|---|---|
| `a89cf5f7`, `ee8b13c8`, `69489f2c`, `8c68a768` | `RSX_GPU_VERTEX_FETCH` and its fallback, pins | Two launches, `Present() Timeout`, 0 race frames (`t162/GAME_AB_RESULTS.md`: "Do not integrate or enable it") | **REJECTED for now.** Heavy, 7-region conflict, failed in game, and its fixes only serve itself |
| `d1bec5b3` | `RSX_VTX_STATS` | Base of fetch | **REJECTED** as low value: `RSX_FRAME_PERF` covers it |
| `8a12a61a` async fetch compile | `RSX_GVF_ASYNC` | Exists only for fetch. Never run. T181's concurrent `D3DCompile` is an untested crash suspect | **BLOCKED** on fetch |
| `8a12a61a` wait and compile diagnostics | `RSX_WAIT_DIAG`, `RSX_SHADER_COMPILE_DIAG` | Timer and fence reads run even when off | **Not recovered**, needs gating work; can be done when needed |
| `8a12a61a` interval, `61d32fdc` timer | Above | Tied to the T162 base only | Recovered |
| `61d32fdc` `[vca]` | Async diagnostics | Needs async | **BLOCKED** |
| `800287cc` | Duplicate-draw diagnostics | No fix needed: 0 confirmed duplicates in 13,471 records | Recovered as a tool. **No performance gain is expected** |
| `fc6f1dbe` | `RSX_VIS_DIAG` | No results reported; T168 culling idea rejected | **Not recovered:** 3-region hand merge for an unused diagnostic |

The T162 base is not needed by the recovered items: `gvf` and `vtx_stats` don't appear in those hunks (VERIFIED).

## 4. Everything else

| Workstream | Commits or path | Finding | Class |
|---|---|---|---|
| T152 inline loads and stores | `dcd62dc5` | Lifter change, needs a relift (forbidden here) or a separate path | BLOCKED |
| T159 state dedup | `12b1d78b` | Only `rsx_live_draw.c`, which is off in the race arms' path (HYPOTHESIS). -1.4 to -1.9 % in its bench. **Corrects T181's "next candidate"** | EXPERIMENTAL, low value |
| T144 lane handoff | `b00e9996` | Net regression in its own report | REJECTED |
| T149 trace | `ce326294` | Diagnostic, 1 conflict | EXPERIMENTAL, not needed now |
| T163, T164 Vulkan | `cc343a02`, `f11ecd45`, `c631d2a0` | Doesn't help the D3D12 path; never run in race | EXPERIMENTAL |
| T25 snapshot share | `fab7b2c4` | 3 conflicts; `tex` is only 5.3 ms | EXPERIMENTAL |
| T74, T77 prepass, recycler | `600e3727`, `9497ad3c` | Memo may overlap; recycler offline only | BLOCKED |
| T83 redundant drain | Uncommitted, `Motorstorm01/t83-worktree` | Old base; fence wait is 0.1 ms, so little to gain; its legacy runners fail | EXPERIMENTAL |
| T89b MFC owner | Uncommitted, `Motorstorm01/t89b-worktree` | Old base, untested on T181, small | EXPERIMENTAL |
| T172 | Uncommitted, `ps3recomp-t172` | Same symbols as T179 in T181; not compared byte for byte. **Does not fix the dark squares; no branch does** | ALREADY INTEGRATED |
| t58 prop | Uncommitted, `scratch/t58/prop` | Flags already present | ALREADY INTEGRATED |
| T143, T144 stencil, T145, T99, T115, T115b, T116, T117, T147, T102, T104, T106, T109, T123, T123b, T136, T25 VP growth and strips, T89b spans | See `git cherry` | Flags and functions found in T181; several by symbol only | ALREADY INTEGRATED |
| T148 | 28 commits, incl. `e69bafe9` | Superseded by T177; the rest are NP, fs, tools, sampled by subject only | REJECTED for this goal |
| T97, T25 leftovers, T33-T61 and T70-T89 AOT lines, `recover/*`, `origin/*` | | Tests, tracing, older AOT and upstream branches. Not reviewed commit by commit: T59 onward AOT flags are in T181 | Not assessed, no race candidate found |
| Stashes | Root and `ps3recomp` | None | |

The older-branch rows come from a read-only survey by symbol and report; only the recovered items were built here.

## 5. Validation

| Check | Result | Label |
|---|---|---|
| Full suite, `env_t169.cmd` | **161 pass, 0 fail, 43 skip** | VERIFIED |
| T181 base | 157, 0, 43; the 4 extra passes are new tests | VERIFIED |
| Manual C tests, not in the suite | `test_draw_dup` pass; `test_t162_fp_src2_abs` pass | VERIFIED |
| Not run | `test_gcm_fifo_replay` no link recipe. `test_t162_vehicle_reflection` compiles, not linked | BLOCKED |
| Off-flag pixels vs T181 on RTX, AMD, WARP | Identical. The bench doesn't use SRC2 abs, so that default-on change isn't covered there | VERIFIED |
| Build | rc=0, exe above, later than the head commit | VERIFIED |
| Public audit | Code `--tree` on a copy of all changed files passed. Reports `--staged --private-reports` | VERIFIED |
| Suite rewrites of `scratch/ppu_conformance*` | Restored | VERIFIED |

One bug of mine was caught by the build and squashed into `e7de5b6c`: a literal newline in the interval log string.

## 6. Runtime A/B proposal (not authorized, nothing launched)

Requires the T181 preflight: GPU free, no `llama-server`. `tools/make_runner_t182.py` generates the runner with the exe pinned. One launch each, in order, no retries, RTX, stop at race + 75 s:

| Arm | Flags | Decides |
|---|---|---|
| R | Lean, polling | Baseline, T173 fix, SRC2 change |
| B | Wake gate, fast fetch, memo, indexed, cache 3 | Candidate B |
| D | B + `RSX_VP_DIRECT=1` | Direct's real gain |

If they disagree with the bench, the other recovered flags don't matter yet. `RSX_PRESENT_INTERVAL=0` and `RSX_RT_REINTERP` should each be a later single-flag arm. Pass: frames not visibly different, no crash, `[rsx-frame-perf]` `expand` lower in D than in B.

## 7. Blockers

- GPU held by `llama-server`; no launch possible yet.
- The T173 fix and every performance flag lack game evidence.
- The AMD indexed difference is unexplained.
- Dark terrain squares have no cause and no fix anywhere.

## 8. Next steps

1. Authorize R, B, D.
2. If D gains: decide whether T182 replaces T181 as the candidate.
3. Only then consider relift-dependent T152.
