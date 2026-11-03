# T192 correctness results

Tree `ps3recomp-t192`, code commit `cc386f42`. All offline, Windows 11, clang 23.1.3. No game launched. Logs (private, untracked): `generated/analysis/t192/logs/` (`test_spu_ib_fast.txt`, `sanitizers.txt`, `suite_off.txt`, `suite_on.txt`, `suite_recheck_*`).

## Differential harness

`py -3 ps3recomp-t192/tools/test_spu_ib_fast.py --seeds 4 --iters 20000` under `env_t169.cmd`: **50 checks reported PASS, 0 FAIL; `test_spu_ib_fast: 0 failure(s)`** (33 suite/environment checks + 17 negative controls).

Every case runs the same context state through the full resolver (context A, switch off) and the fast path (context B, switch on), and requires the same stub called the same number of times with the same `pc`, `resident_task`, `reloc_delta`, a restored register and `int_enable`, and the **whole `spu_context`** identical afterwards (local store by checksum).

| Suite | Checks | Covers |
|---|---:|---|
| `directed` | 4,148 | T191 scenarios (ordinary, invalid / misaligned / high-bit targets, overlays, images, slots, policy and service addresses, iret, task region, run-time registration, 2,000 re-created contexts) |
| `directed --tasks` | 4,156 | same with taskset entries registered |
| `reloc` (new) | 125 | intra-slot fill / hit; second target; module moved to another base; link base changed; same-address replacement by another owner and back; eviction; unrecognized owner; slot boundaries; misaligned and high-bit pc; overlay change under a slot; two-slot order; DMA outside / inside a slot; reinstall; knob off; policy, iret, tracing, task state, job return, image 23, negative overlay; registry change (epoch miss); shadowing by a later overlay registration; epoch wrap; **exact primary reason asserted at 32 call sites**, and the partition identities |
| `random` x 4 seeds x {plain, `--tasks`} | 8 x 80,003 | as T191, plus negative `resident_ovl` values, relocatable slots in a quarter of the slot draws |
| `random --reloc` x 4 seeds x {plain, `--tasks`} (new) | 8 x 80,004 | slot install / replace around the target (other owner, base or link base), eviction, unrecognized, DMA over or near a slot, run-time registration (owner, overlay, image, relocatable keys), tracing toggled, the reloc knob toggled |
| `threads` | 2 | 4 host threads, own contexts, shared registry; half the cases use a relocatable slot whose delta depends on the worker |
| `stackreset` | 7 | one-way stack-reset check with a live host frame |
| `envinit` | 13 | switch unset / 0 / yes / 1, the reloc knob, each diagnostic variable |

Random total: **16 runs, 1,280,056 checks** (T191: 8 runs, 640,008). Each run asserts that hits, fills and resolver fallbacks all occurred, that the primary reasons sum to the branches, and the probe classes sum to fills + unresolved; the reloc runs also that slots, unrecognized owners, tracing, the knob and epoch misses were exercised. Seeds are fixed; the first failing iteration and its RNG state are printed for replay.

Zero mismatches in any run. (Development found and fixed three harness mistakes, none in the runtime: wrong expected stub id, an uncounted extra branch, a mutant that turned out to be behaviourally equivalent.)

## Negative controls (17 textual mutants of `spu_channels.c`; each must fail the suite) — **17 of 17 detected**

1 key omits overlay; 2 key omits image; 3 policy mode ignored; 4 pending iret ignored; 5 `resident_task` clear skipped; 6 reloc hit does not publish the delta; 7 reloc fill does not publish the delta; 8 reloc key ignores the link base; 9 evicted slot still the owner (with the non-positive-owner refusal removed); 10 slot size ignored; 11 negative overlay accepted; 12 reloc knob ignored; 13 probe classification dropped; 14 slot owners ignored; 15 registry epoch not compared; 16 stack-reset check skipped; 17 task ownership not consulted.

Control 9 as first written (only the owner scan changed) was **not** detected, because the refusal of non-positive owners sent the branch to the resolver anyway: an equivalent mutant. It was strengthened (second edit) and then detected. Control 15 is now detected behaviourally (the shadowing test dispatches a stale function), not only by the refill counter as in T191.

## Sanitizers (`generated/analysis/t192/tools/run_sanitizers.py`)

AddressSanitizer and UndefinedBehaviorSanitizer, each over `directed`, `directed --tasks`, `reloc`, `random 3 --tasks`, `random 103 --reloc`, `random 203 --reloc --tasks`, `threads`, `stackreset`: 16 runs, **0 failures, no sanitizer report**. ThreadSanitizer does not exist for Windows targets; concurrency is covered by the 4-thread differential and by design (thread-local cache; the only shared datum is the release/acquire epoch).

## Existing suite

`generated/analysis/t192/tools/run_all_t192.py ps3recomp-t192` (a copy of `run_all_t188.py` whose only change is that `PS3_SPU_IB_FAST*` is not stripped from the environment, so the suite can run with the switch on):

| Run | PASS | SKIP | FAIL |
|---|---:|---:|---|
| switch **off** (default) | 164 | 43 | `test_spurs_kick_wake` (known flaky timing assertion) |
| switch **on** (`PS3_SPU_IB_FAST=1`, whole suite) | 161 | 43 | `test_t169_profile`, `test_t169_rt_reinterp`, `test_d3d12_shader_cache`, `test_spurs_kick_wake` |

The three extra failures with the switch on were examined and are **not** caused by it:
- `test_t169_profile` (6 failures: `[visual-active] printed` etc.) and `test_t169_rt_reinterp` (5) are renderer / WARP tests. They passed in the first, default run, but when re-run alone and serially they fail identically with `PS3_SPU_IB_FAST=1` and with `PS3_SPU_IB_FAST=0` (log `suite_recheck_*`). They failed in T191 as well (T191 `CORRECTNESS_RESULTS.md`). They depend on the machine state, not on the switch. HYPOTHESIS (not investigated): GPU / RDP session state.
- `test_d3d12_shader_cache` passes alone with the switch on (4.3 s) and off; in the full on-run it failed once, under the same parallel-batch load that made it fail in T191.

The SPU tests that drive the real dispatcher with the switch on all pass: `test_spu_jobspan`, `test_spu_reloc_job`, `test_spurs_wws_concurrency`, `test_spurs_wws_stress` (3 seeds), the `test_spurs_*` policy tests, `test_spu_ib_fast` itself. (Many of those tests run under policy mode, so they mostly exercise the refusal path; that is stated, not hidden.)

## Not covered

- No real lifted program or homebrew SPU program; the relocatable tests use manufactured modules registered under synthetic keys.
- Guest writes into a slot that bypass `spu_overlay_note_get` (SPU stores, GETLLAR, PPU writes to LS) cannot be modelled at this level and are outside both the resolver's and the cache's knowledge (`CACHE_INVALIDATION.md`).
- POSIX builds were not run.
- The `-DSPU_IB_FAST_STATS` code is exercised by the harness only; the report line printed at exit was checked by eye, not by a test.
