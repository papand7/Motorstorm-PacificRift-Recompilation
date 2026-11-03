# T168: duplicate execution root cause

**There is no root cause to report: duplicate execution wasn't found, so no fix was made.** No draw, pass or walker behaviour changed.

## Findings

| Observation | Explanation | Status |
|---|---|---|
| Four RSX passes in heavy frames | `ceil(records / 2048)`: the record limit forces early replays of **different** records | VERIFIED from logs and source |
| About 6,900 draws | Counts libgcm batches, not guest commands. In light-scene captures 2.2 records make one packet | VERIFIED for light; heavy ratio unknown |
| Repeated FIFO offsets in the raw data | One packet with many (first, count) words. My first analysis counted 219-566 "repeats" per pass; all were this | VERIFIED |
| Same mesh, many targets | Multipass | Consistent, targets differ |
| Same mesh, one target, different constants | Instances | Consistent |
| `[rsx-hb] frames` above guest frames | It counts replays | VERIFIED (T101, T161 logs) |

## Not explained by T168

- **Poor heavy-scene performance.** T162 attributes it to the texture table overflow (190-216 ms) and vertex expansion (47-49 ms), not duplicates. T168 adds nothing against that.
- **Overexposed terrain and artifacts.** Nothing ties them to repeated draws. Blended candidates: 0. Opaque, depth-writing repeats at the same state would not brighten an image. That points away from duplicates (HYPOTHESIS); T166 owns colour.
- **The 1,427 candidates.** Open until vertex addresses are captured.

## If the candidates turn out to be real

Same target, program, state, constants **and** vertex addresses would still have separate FIFO addresses, so the runtime's walker would not be the cause. The next suspects would be, in order:

1. The game's own scene list (legitimate, must be kept).
2. SPU renderablejob translation emitting an entry twice. Identical-sequence detection found 0 repeated jobs, but one repeated entry inside a job wouldn't show.

Neither would justify deduplicating by signature.

## Latent hazards, left unchanged

| Hazard | Why unchanged |
|---|---|
| Stray RET goes to IO 0 and re-walks the ring | Never observed. The RSX has one return slot too, so a legal stream doesn't do this. Now counted (`stray_rets`, `nested_calls`) |
| Resync landing on an SPU block's start can re-walk it | 0 resyncs in the runs checked; other titles depend on it |

The brief allows fixes for verified defects only.

## Added

Ps3recomp `800287c`, branch `agent/t168-duplicate-draw-analysis`, from `69489f2`:

- `RSX_DRAW_DUP_DIAG=1`, `include/ps3emu/draw_dup.h`: per-draw signature, read-only and bounded.
- Walker CALL/RET counters: four additions in rare branches, always on, no behaviour change.
- `test_draw_dup.c`, `test_gcm_fifo_replay.c`.

## Handoffs

- **T166:** duplicates are unlikely to explain overexposure, on light-scene evidence only.
- **T167:** the 2,048-record early replays are the "passes" in its counters; each is a real submission.
- **T165:** no finding about vehicles. Rider and vehicle draws above c[63] can't be compared in these captures.
