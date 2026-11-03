# T191 generalization

## What the fast path assumes

| Assumption | Where it comes from | Title-specific? |
|---|---|---|
| Local store is 256 KB; targets are masked with `SPU_LS_MASK` | architecture | no |
| The taskset task-code region starts at LS `0x3000` | existing resolver constant (`SPU_TASKSET_TASK_LO`, SPURS taskset ABI) | no (SPURS) |
| LS `0xA70`, `0x3FF00`, the two policy-module service addresses, image id 23 | existing constants the resolver already special-cases | SPURS ABI plus one legacy title hack, refused by the fast path |
| Lookup is `(pc, image, overlay)` over an append-only registry | `spu_lookup` | no |

No MotorStorm function addresses, Havok task layouts, Wws job behaviour, program sizes, overlay lifetimes or synchronization assumptions appear in the fast path or in the tests. The tests use manufactured stub functions registered under arbitrary image ids and addresses.

## Independent workloads used

- **Manufactured SPU programs** (no game bytes): 4 base images, 3 overlay images, 2 code-owner images, a wildcard image, ~96 addresses each, registered with deliberately overlapping addresses so shadowing and wildcards are exercised; 8 x 20,000-branch seeded random sequences; 4 host threads.
- **Existing runtime tests** that drive the real dispatcher with synthetic programs (`test_spu_reloc_job` assembles synthetic Wws-layout job modules; `test_spurs_*` run manufactured policy modules): the same tree, the same suite run, switch off. They do not run with the switch on in this task.

Not done: running the T191 switch **on** under the existing runtime tests, and a legally usable homebrew SPU program (none is available offline in this workspace). Both are listed in `NEXT_STEPS.md`.

## Where it does and does not help

| Workload shape | Fast path | Measured offline |
|---|---|---|
| A guest loop dispatching `bi` to a few stable targets in one image | hit | ~25 % less per branch |
| Streamed code overlays swapped often (target repeatedly changes owner) | hit after the first use of each key | ~30 % less |
| Many distinct targets (a large jump table) | hit while the working set fits 512 entries per thread; direct-mapped, so conflicts refill | ~7 % less at 200 targets; the saving is smaller because target diversity costs the same in both arms (indirect-call misprediction) |
| Code running from relocatable slots (Wws-style) | **refused**: resolver, plus ~2 ns of eligibility work | **slower** with the switch on |
| SPURS policy-module code | **refused**: resolver, plus a few % | slightly slower |
| Taskset tasks above LS `0x3000` where the title registered task entries / ELFs | **refused** | no change beyond the eligibility cost |
| Titles that never dispatch through the resolver (all calls statically linked) | never reached | none |

Fallback conditions are exactly the list in `FAST_DISPATCH_DESIGN.md`. A title that spends its time in policy modules, relocatable job slots or the registered task region will see no benefit and a small cost until those are cached (`NEXT_STEPS.md`). Whether MotorStorm is such a title is **unmeasured**: how many of its branches are eligible needs the in-game hit-rate counters (`-DSPU_IB_FAST_STATS`).

## Limitations

- Direct-mapped 512 entries per host thread; no adaptive sizing.
- A miss that resolves costs a lookup plus a fill; a branch that never resolves (unregistered target) always runs the full resolver.
- The registry is assumed append-only (`CACHE_COHERENCE.md`).
- Memory: 12 KB of TLS per host thread.
- Windows (MSVC-model TLS and `musttail` in the clang-built lifted TUs) was measured; POSIX builds compile the same code but were not run here.
