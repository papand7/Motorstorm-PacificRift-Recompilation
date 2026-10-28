# Sequential PSARC reads during the garage load (offline, 2026-10-23)

Run `generated/runs/20261023-150148-garage-render/` (`PS3_FSLOG_READS=5`, so every read of fd 5 is logged). The archive is `ms2.psarc` (4,811,608,561 B; fd 5); FIOS keeps `cache.idx` (fd 3) and `cache.dat` (fd 4) on `dev_hdd1`. Times are seconds after launch. MotorStorm was not launched for this analysis.

## What the log shows (VERIFIED)

- **One monotonic walk over the archive**:
  - starts at offset 0 at 20.1 s (during boot, before the intro);
  - reaches 27 MB at 45.8 s and **671 MB at 210.4 s** (3.9 MB/s from 45.8 s);
  - made of 9,600 reads of 64 KiB (8,959 directly after the previous one) and variable-size reads at the same front, which are PSARC blocks: stored blocks are 64 KiB, compressed ones smaller;
  - it pauses for more than 1 s at times (57.8, 59.9, 63.6 s, and every 1.6 s between 132.9 and 142.7 s).
- **FIOS cache growth matches the walk:** `cache.dat` grew from 29,360,640 B to 672,137,728 B over the run (runner cache diff). That is the walk's final offset to within 1 MB. `cache.idx` stayed 1,043,456 B.
- **Caller:** the `lseek`s on fd 3, 4 and 5 come from `func_00667558+0x103B1`, the FIOS media code (`FS_CALLER=1`). Read lines carry no caller.
- **The game's own reads go on in parallel:** between 37 and 94 s, reads touch offsets from 27 MB to 3,363 MB, well ahead of the walk.
- **Garage sky package** (`/env/Track0a_Garage_Sky1_driver.rpk`, [244,169,081, +8,650,343)):
  - The game's reads covered **6.41 MB, starting at 34.4 s**. That is like the garage-read run's 5.9 MB, which was cut by its stop.
  - The remaining 2.24 MB were read only when the walk passed that offset, at **95.1–96.6 s**.
  - So **`garage_sky_read_complete` (95.98 s) was completed by the walk**, not by the game asking for the rest. It is not evidence of loading progress. The game may need only part of that package.

## What it is

| Candidate | Status |
|---|---|
| Expected FIOS cache population (copying the archive into `cache.dat`) | **most likely (INFERRED)**: sequential, in archive order, rate-limited, and `cache.dat` grows by the same amount |
| Sequential archive prefetch for a specific load | unlikely: it starts at offset 0 during boot and runs across unrelated members |
| Background scan | possible as part of the cache fill; no per-member pattern |
| Repeated reads | no: monotonic, no re-reads except where game reads overlap |
| A guest thread waiting on the cache fill | **UNKNOWN**. No wait is attributed to it. Presentation stopped at 45.8 s, while the walk had covered only 27 MB. |
| A slow I/O path | **UNKNOWN**. 3.9 MB/s is far below the host disk. It may be FIOS's own throttle (the 1.6 s spaced pauses suggest pacing) or the emulated media rate. Not traced. |

**No caching behaviour was changed:** no correctness or performance defect is identified.

**Side effect on runs:** the live cache now holds 672 MB of the archive. The next run starts from a different FIOS state than this one, unless `generated/cache-snapshots/20261023-150148` (29 MB, taken before this run) is restored first. Restoring it is a separate decision (`NEXT_RENDER_DIAGNOSTIC_RUN.md`).

## To attribute it (not done; needs a run)

- A caller on reads, not only seeks, for fd 4 and 5. The `[fsread]` line has no caller field.
- FIOS op lifecycle around the walk: which FIOS op issues the 64 KiB reads, and whether any game op waits on it (`func_0065B460` waits, see `STATUS.md` 2026-10-21).
- `PS3_PRESENT_PROGRESS_MS` now reports `fs_reads` and `spu_dispatches` during a presentation stall.
