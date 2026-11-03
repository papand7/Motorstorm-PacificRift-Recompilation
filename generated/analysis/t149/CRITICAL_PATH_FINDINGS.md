# T149: critical-path findings (MotorStorm: Pacific Rift, race)

Labels: VERIFIED (measured), PARTIAL (measured in part, or on a sibling build), HYPOTHESIS (inferred), BLOCKED (needs a game run).
Full report: `PPU_SPU_CRITICAL_PATH_OPTIMIZATION.md`.

## Game A/B result (2026-10-28, 4 authorised race runs, one per arm; full table in report §15)

| Arm | FPS | Frame (PT) | Gate (trace) | Scheduler-attributable lane idle |
|---|---:|---:|---|---|
| P0 T146 defaults | 6.57 | 136.9 ms | **RSX** (drain 157 ms per frame, 79 ms of it the tex-snapshot hash) | 2.7 of about 115 ms |
| P1 performance preset | 7.29 | 121.3 ms | **PPU frame-thread compute (56 ms) + RSX** | 0.9 of about 91 ms |
| P2 P1 + `PS3_USLEEP_SPIN=2` | 7.21 | 121.4 ms | (trace window mostly pre-race: loading took about 76 s longer) | n/a |
| P3 P1, no trace | 7.07 | 123.8 ms | n/a | n/a |

- **SPURS dispatch:** off the critical path (VERIFIED). Lane idle is `no_work`: the guest has nothing ready.
- **No SPURS/PPU optimization:** none is justified, and none was implemented. No default was changed.
- **Next work:** renderer drain/record, then PPU frame-thread compute.
- **Sample size:** single runs (PARTIAL for the FPS deltas).

The sections below were written before the runs; their BLOCKED items are answered by this table.

## What the evidence covers

- **No race run of the unified runtime exists.** That is T146 (`integration/t146-unified-runtime`, `80fe5de`).
  - No race run anywhere has a `PS3_CRITICAL_PATH_TRACE` timeline.
  - The T134 profiler only ever ran in tests.
- Every number below comes from an older exe:
  - T106: five lanes (`motorstorm-t109`, `-aot`);
  - T122: one lane (23 runs);
  - T145: one lane (3 race runs today, with the debug layer on).
- These lineages differ from the unified runtime in exactly the switches that moved the critical path:
  - guest maxContention;
  - T119/T122 renderer changes;
  - the SPU job AOT.

So **the current critical path is not established** (BLOCKED). The chains below are the measured ones.

## Frame model (guest tid 1, `main`)

| Phase | Guest site | What it waits on |
|---|---|---|
| ref | `0x72E1E0` | the RSX reaching the previous frame's reference |
| PRE | ref exit → first `0x50D868` | Havok taskset `0x16209480` (about 25 SPU tasks in 4 waves); `JobBatch::Wait 0x4AACA0`; `PVS WaitForCompletion 0x5F74B0`; Havok `0x30B710` |
| emit | first → last `0x50D868` (ExecutePushBuffer) | push-buffer generation, interleaved with Wws jobs |
| spin | `0x50C818` | the frame-end Wws spin on jobs issued/done (`[r3+0x44C]` / `[r3+0x2560]`) |

- Every wait is the guest's own primitive (`0x4B63F0`): a spin, then `sys_timer_usleep(250)`.
- Each such usleep returns after about 520 µs, because the host timer tick is 0.5 ms (T121, VERIFIED).
- The frame ends when the last producer finishes. These are **genuine guest dependencies**: the guest decides what it waits for.

## Longest measured chains (ms per race frame, means)

| # | Build | Frame | Chain (critical producer per phase) | Gate | Evidence | Label |
|---|---|---:|---|---|---|---|
| 1 | One lane (T145 A1 today, debug layer on) | 294 | PRE 137 (SPU tasks + Wws on 1 lane) → emit 92 → spin 51 (Wws jobs) → ref 11.5 | SPURS Wws on one lane | `[PT]` phases, `t149/tools/phases_t145.txt` | VERIFIED |
| 2 | One lane (T122, 23 arms) | 193–243 | PRE 93–116 → emit 58–77 → spin 38–48 → ref 0–0.3 | same; RSX idle 114–168 ms | `t134/phases_all.txt` | VERIFIED |
| 3 | Five lanes (T106 B1/B2) | 136 | ref 45–47 (RSX drain host thread busy about 130 of 134 ms, `expand_ms` 107) + PRE 54 + emit 21 + spin 12.5 | RSX drain | T106 `AB_RESULTS.md`, T134 §2 | VERIFIED |
| 4 | Five lanes + Wws AOT (T106 D1/D2) | 129 | ref 80–82 + PRE 40 + emit 6 + spin 0.3 | RSX drain | same | VERIFIED |

Moving from 1 lane to 5 removes about 123 ms of PRE + emit + spin (chain 2 → 3). It was the T106 guest maxContention fix (`b84ed80`), which **is default-on in the unified runtime** (VERIFIED by ancestry, T146 ledger).

## Idle-time evidence available today

| Question | Answer from existing data | Label |
|---|---|---|
| Are the five lanes load-imbalanced? | No. T106 B1: each lane at 0.318–0.320 busy, max/mean 1.00 (T144) | VERIFIED |
| How idle are the lanes? | 68% (B) and 91% (D) of wall time | VERIFIED |
| Is that idle time scheduler overhead? | **Not separable.** No existing log records when work became ready, so idle time cannot be split into no work / waiting for a pass / waiting for a lane | BLOCKED |
| Kick → admission latency in game | Periodic coordinator: about 0.7 ms median per kick (T123) | PARTIAL (old build) |
| Host CPU oversubscribed? | No. The process uses 2.64 of 12 logical CPUs (T123, D1) | PARTIAL |
| PPU compute on the path? | tid1 is off-CPU 63–78% of the frame and runs at most about 28 of 129 ms (T121, T140) | PARTIAL |

## What follows (HYPOTHESIS until the trace run)

- **Default unified runtime:** five lanes, with the epoch/compaction opt-ins off.
  - The RSX drain is expected to gate, as in chain 3.
  - A host SPURS change cannot then move the frame.
- **Performance preset** (epoch, compaction, PSO cache, SRV reuse, event scheduler):
  - T122 cut the drain from 77 to 15.6 ms on one lane.
  - PRE (Havok task waves plus in-frame job waits, 40–54 ms) then becomes the gate.
  - Whether PRE is SPU-bound (task runtime), dispatch-bound (kick → pass → lane), or wake-bound (the frame thread's 520 µs polls) is what the T149 trace answers:
    - `guest sites`: each wait site's time while SPU work ran, while only the RSX ran, or while nothing ran;
    - `lane idle`: idle time split into `kick_wait`, `pick_to_run`, `ready_unadmitted`, `capped` and `no_work`.

## Host-introduced vs guest dependencies

| Delay | Origin | Status |
|---|---|---|
| Wws jobs on one lane | host (maxContention stored as 1) | fixed, default-on (T106) |
| Kick → coordinator pass (periodic 1 ms) | host | opt-in fixes exist (T123 kick wake, T123B event scheduler); not measured in game |
| Pass → lane thread running | host (condvar wake) | measurable now (`pick_to_run`) |
| Frame-thread usleep overshoot (520 µs vs 250 µs) | host timer tick | opt-in `PS3_USLEEP_SPIN=2` (costs about a core); share of the path BLOCKED |
| Havok waves, JobBatch, PVS, Wws done counters | guest | preserved; never shortened |
