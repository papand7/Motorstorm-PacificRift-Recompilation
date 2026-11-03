# T189: correctness results

Code commit `a26240c5` (`agent/t189-perf-architecture`, ps3recomp worktree `ps3recomp-t189`). All tests offline.

| Test | Command | Result |
|---|---|---|
| T152 page gates / inline stores | `py -3 ps3recomp-t189/tools/test_vm_page_gates.py` (under `generated/analysis/t169/tools/env_t169.cmd`) | **0 failures**. Gate rules, probe refusal, rwatch, reservations before and after the fill close their pages, inline store to a reserved line raises LR, first page / raw-SPU / ref-poll, unaligned and 64 KiB-crossing accesses, and **300,000 random loads/stores inline vs out of line** with twin reservations: the same memory, values and LR events. One text check was updated for the T189 slow-path forwarder (`vm_writeN_cold`, verified to call `vm_writeN`) |
| Store fast path vs full writers | `test_vm_store_fast.py` | 89 passed (400,000-store differential, LR events equal) |
| Promotion with the real T152 header | `py -3 tools/test_ppu_regpromo.py --seeds 12` | **0 failures**: 12 seeds × 4 variants (base, promo, promo_keep, promo_sync) identical. Seeds 3, 6, 9, 12 use inline stores, 1, 5, 9 the cold thunks, even seeds trace masks 0 and 7. 3/3 mutants detected |
| Default behaviour (negative control) | `generated/analysis/t189/tools/default_equiv.py` | **PASS**: without flags, the lifted C and the x64 of every lifted function (4 programs, 35 functions: kernels plus 3 random programs, one with trace hooks) are byte-identical between T189 and the unmodified `766d3575` lifter and header |
| Four-arm transcripts, synthetic | `tools/bench_ppu_fourarm.py` | 9/9 cases: A, B, C, C2, D identical |
| Four-arm transcripts, real game functions | private `real_fourarm.py 000` / `003` (pointer mode, 4 seeds each) | 48 functions, **0 mismatches**. 10 functions faulted (identically in every arm) or exceeded the time limit on the synthetic inputs and were not timed |
| Real runtime, real functions | private `bl4.cmd` + `run_bl4.py` | final state hash identical in A/B/C/D for `func_0096B648` and `func_002D0D94`. `func_000C9678` crashes the runtime in every arm on T152's inputs (input-dependent, not arm-dependent); excluded |
| Lifter suite | `test_ppu_lift` (1,533 conformance checks), branches, chunks, dedupe, header name, scaffold, trace, jump tables, cs-restore, fall-through | all pass (inside the full suite) |
| Full suite | `env_t169.cmd py -3 generated/analysis/t188/tools/run_all_t188.py ps3recomp-t189` (log `generated/analysis/t189/logs/suite_run.txt`) | **161 PASS, 43 SKIP, 3 FAIL**: T188's 160 plus the new `test_vm_page_gates`. The same 3 failures as T188: `test_spurs_kick_wake` (known flaky timing), and `test_t169_profile` / `test_t169_rt_reinterp`, which fail identically on the unmodified T183 base on this machine (D3D12/WARP environment) |

**Semantics notes:**
- Memory ordering: relaxed atomics for inline stores, the same as the existing inline loads; fences unchanged.
- Reservations: store pages that hold an SPU-reserved line are closed before the line is marked.
- Exceptions: unmapped or closed pages take the unchanged out-of-line path.

See `PPU_INLINE_STORES.md` §4.

**Not covered:**
- multi-threaded PPU/SPU interleavings with inline stores beyond T152's twin-reservation differential;
- the combination with T187's `PS3_SPU_MFC_FAST` (a different branch);
- VMX stores (they use the raw-store macros, unchanged).
