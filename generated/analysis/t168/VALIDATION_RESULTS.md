# T168: validation results

Source: ps3recomp `800287cc9a9577a8ad76473b9c0f7b79ddfc4893`, from `69489f2`. Commands: `tools/build_tests_t168.cmd` (private). clang LLVM 23.1.3. No game launch, no game data.

| Check | Result |
|---|---|
| `test_draw_dup` | 12 of 12 pass |
| `test_gcm_fifo_replay` | 12 of 12 pass |
| `ps3recomp_runtime`, default configuration, includes the D3D12 backend | Builds, exit 0 |
| Public-source audit of the five changed files | Passed |
| Offline trace analysis | 21 passes, 0 unparsed events |

## FIFO walker cases (`test_gcm_fifo_replay`)

Counted at `rsx_process_method`.

| Case | Expected | Result |
|---|---|---|
| Packet of 3 words | Each once | Pass |
| CALL/RET | Chunk in place, once, with return site recorded | Pass |
| Overflow chain: CALL, JUMP, RET | Both chunks once | Pass |
| One chunk from two CALL sites | Twice, as asked, different return sites | Pass |
| Repeated drains while put moves | Nothing re-walked | Pass |
| Reused chunk slot | New content only | Pass |
| Chunk still holding the pre-filled RET | Adds nothing | Pass |
| Flip inside the stream | Splits the drain, nothing twice | Pass |
| Identical draws in a row | **Both execute**: nothing dedups | Pass |
| Nested CALL | Hazard pinned: nested and stray counters move | Pass |

## Classifier cases (`test_draw_dup`)

Next word of one packet isn't a replay. Same position with same content is a replay, with other content is a rewrite. A new guest frame starts clean. Identical draws elsewhere, including a second CALL site, are candidates and never replays. Blended draws are counted apart. Other transform counts as instancing, another target as multipass, another texture as neither. Overload is counted, with no false replay.

## Brief's experiments: coverage

| Experiment | Coverage |
|---|---|
| CALL/RET nesting, reused buffers, frame boundaries | Tests above |
| Multiple RSX passes | T101 and T97 models (early replay), T161 pass arithmetic |
| Shadow passes | Trace only: distinct targets. No replay of a shadow pass was built |
| Repeated meshes with different transforms | Classifier test, traces |
| Identical transparent draws, intentional overdraw | Walker runs both; classifier keeps blended apart |
| Removing a repeat and comparing output | **Not done**: no confirmed repeat to remove |

## Not validated

- **`RSX_DRAW_DUP_DIAG` has not run inside the real backend.** The hook compiles and its logic is unit-tested, but the D3D12 call site was never executed. The test covers the header, not the signature fields the backend fills.
- Frame hashes: nothing changed in rendering, and no D3D12 run was made to confirm it.
- Linux and macOS builds of the new tests. On Windows the FIFO test links with a private stub file, `tools/fifo_stubs_win.c`, in place of CI's `--gc-sections`.
- The new tests are not added to the CI workflows.
- The heavy scene: see `GAME_CAPTURE_PLAN.md`.
