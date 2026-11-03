# T168: performance impact

**Confirmed duplicate work: 0 draws, so measured saving: none.** Everything below is a theoretical ceiling, not a prediction.

| Measure | Confirmed duplicates |
|---|---|
| Duplicate draw count | 0 of 13,471 records in 18 light-scene passes |
| CPU recording, GPU execution, target traffic, frame time | Nothing to measure |

## Ceiling if every candidate were real (THEORETICAL)

Candidates are 2,744 of 13,471 records (20%), but very unevenly spread:

| Pass shape | Records | Candidate records | Share |
|---|---|---|---|
| Shadow and depth | 8,507 | 2,431 | 29% |
| Main colour and post | 4,964 | 313 | 6% |

| Item | Basis | Ceiling, light scene |
|---|---|---|
| CPU vertex expansion | T161: 13-13.5 ms per 2,004 draws, about 6.6 µs per record | About 2.6 ms per frame at 20% |
| Recording | T161: 5 ms per 2,004 draws | About 1 ms per frame |
| GPU | Not measured (GPU wait about 0 in T162) | Unknown |

**This wouldn't raise light-scene FPS by itself:** expansion runs on the RSX thread, which T162 found idle about 21 ms per frame while the PPU sets the pace (HYPOTHESIS, strong). Heavy-scene share is unknown. Removing 20% of draws would not mean 20% more FPS, and removing them isn't proposed.

## The real numbers behind "pass" cost

Four passes in a heavy frame cost real time, but not through duplicates: T162 measured 199-222 ms in early replays, driven by texture recording. Records are replayed once each.

## Diagnostic overhead

| Item | Value |
|---|---|
| Off | One flag test per draw |
| On | About 2 µs per draw in the unit test, mostly hashing 8 KiB of constants |
| Heavy frame, on | About 14 ms per 7,000 draws (estimate). **So timing from a diagnostic run isn't comparable** |
| Walker counters | Plain adds on CALL and RET, always on. Not separately timed |
