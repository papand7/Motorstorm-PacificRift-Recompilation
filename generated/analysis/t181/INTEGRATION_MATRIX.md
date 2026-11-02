# T181: integration matrix

Base of `ps3recomp-t181`: T180 `b55bf15f`. Primary: `motorstorm/v0.15-local` `f373398c`, an ancestor of that base, 400+ commits behind. Nothing was merged into primary. "In game" means a real game run of that feature, not a build containing it.

| Work | Commit, branch | Depends on | Flag, default | Offline | In game | Benefit evidence | Regressions, risks | Class | T181 |
|---|---|---|---|---|---|---|---|---|---|
| T170 write-combined fix, fast fetch, FP scan memo | `fda8c9b`, in base | T169 | `RSX_VP_FAST_FETCH`, `RSX_FP_SCAN_MEMO`, off | Pass | Fix yes; the two flags never | Bench only, table in report §4 | Flags untested in game | READY (fix), EXPERIMENTAL (flags) | Base; flags in B |
| T173 jump-table lifter fix | `b6f53f8`, in base | T170 | None, lifted tree `generated/ppu-t173-staging` | Pass | **Never** | Should stop the `0x00CB7FA8` crash | Unproven. The T179 exe did not use this tree | READY, needs a run | In |
| T177 adaptive wake gate | `b86a1073`, in base | T173 | `PS3_LWCOND_WAKE=...:heavy_draws=200`, off | Pass, about 4,700 to 19 us/op in a fixture | Gate never; plain wake in T161 | Load 85-90.8 s to 20-22 s, older build | Plain wake -2.8 % FPS, +0.88 cores | READY | In; A and B |
| T178-load probe | `b352450d`, in base | T177 | `PS3_LOAD_PROBE`, off | Pass | Never | None, diagnostic | Overhead unmeasured | READY | In, unused in matrix arms |
| T180 gate log | `b55bf15f`, base | T178-load | With the gate | Pass | Never | None, diagnostic | One print per transition | READY | Base |
| T171 shader window for WPOS | `b282e262` as `7930dcd8` | | `RSX_SHADER_WINDOW`, **on** | Pass | Yes, T171 | Correctness | The only default-on change added | READY | In |
| T176 polygon offset | `5ccbb116`, `0eb257f6` as `7a7edf61`, `3724e883` | | `RSX_POLY_OFFSET`, off | Pass | Yes, T176 | Visual, inconclusive for the squares | `0eb257f6` repairs two stale pins | EXPERIMENTAL | In, off; arm V |
| T179 depth volume | `0f68dd20` as `e60c6492` | T176 | `RSX_DEPTH_VOLUME`, off | Pass | One capture run, no verdict | Fixture only | Squares not fixed | EXPERIMENTAL | In, off; arm V |
| T178 dark-squares diagnostics | `b2240f2c` as `be44d8ec` | | RSXI only | Pass | Yes | Diagnostic | | READY | In |
| T174 indexed compact | `e528406f` as `695e000a`, one conflict resolved | T170 | `RSX_VP_INDEXED`, off | Pass; RTX pixels 6/6 | Never | Bench only | **AMD pixels 0/6 identical, unresolved.** Off under RSXI and `RSX_VP_PARALLEL` | EXPERIMENTAL | In, off; B |
| T175 direct indexed | Uncommitted in `ps3recomp-t175` | T174 | `RSX_VP_DIRECT` | Its suite 123 pass, 4 fail; pin test ended in a TypeError | Never | None usable | Test failures | BLOCKED | Out |
| T162 GPU vertex fetch | `agent/t162-gpu-vertex-pipeline` | | | | Yes | | Present timeouts, rejected | SUPERSEDED | Out |
| T167 shader stall | `8a12a61a`, `61d32fdc` on T162 | T162 | | | | | Carries T162 | BLOCKED | Out |
| T168 culling, duplicates | `800287cc`, `fc6f1dbe` | T162 | | | | | Rejected earlier | SUPERSEDED | Out |
| T159 state dedup | `12b1d78b` | | `RSX_STATE_DEDUP`, off | Not rebased | Not assessed | `cmd` is about 10 ms of 77 | Touches the record path | EXPERIMENTAL | Out, next candidate |
| T152 inline guest stores | `dcd62dc5`, `9e393ce2` | | Opt-in | Not rebased | Not assessed | Unknown | Touches guest memory paths; may need a relift | EXPERIMENTAL | Out |
| T149, T144 lane handoff | `ce326294`, `b00e9996` | | Opt-in | Not rebased | Not assessed | Unknown | Scheduling | EXPERIMENTAL | Out |
| T148 lwcond queue | `e69bafe9` | | `PS3_LWCOND_QUEUE`, off | Not rebased | Not assessed | Overlaps wake | | SUPERSEDED by T177, HYPOTHESIS | Out |
| T169 visual | `d2d9ef91`, `66b5478a` | | | Not rebased | | Visual | | EXPERIMENTAL | Out |
| T143 | `e2f9435b` | | | | | | Probably a patch-id false positive; its flags are in use | SUPERSEDED, HYPOTHESIS | Out |
| T144 stencil, T145, T162 vehicle, T163 character, T163/T164 Vulkan, T97, T99, T18 | `git cherry` residue | | | Not rebased | | Not assessed in this task | | Not assessed | Out |
| Upstream | `origin/master` `4e8f3ca8`, `origin/integration/v0.18.0` `669d6138` | | | | | v0.18 indexed draws `d682e9c4` are on another draw path (T174 report) | | Not applicable | Out |
| T181 dev string redirect | `00f76bcc` | | `PS3_DEV_GUEST_STR`, off | Pass | Never | See `DIRECT_RACE_STARTUP.md` | Dev tool | EXPERIMENTAL | In, off |

Rollback: unset the flag, or `git revert` the single commit. The one merge conflict is in `libs/video/rsx_d3d12_backend.c` (`rsxi_snap_fp_after` before `vp_drawn:`); indexed mode is forced off under RSXI, so the snapshot is unaffected.
