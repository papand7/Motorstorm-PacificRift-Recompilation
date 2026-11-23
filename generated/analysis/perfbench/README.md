# perfbench: offline SPU/PPU performance bench (private)

Times a baseline and a candidate without launching the game. Private: game-derived inputs and outputs stay
under `generated/`. Do not publish this folder.

## Commands (run from this folder, Windows Python 3)

```
py -3 perfbench.py run   --suite spu --baseline ..\spuopt\bin\gen5.exe,..\spuopt\bin\solv.exe ^
                         --candidate ..\spuopt\bin\hand5.exe,..\spuopt\bin\solvd.exe --recs ..\spuopt\rec\Kksr2
py -3 perfbench.py run   --suite ppu --baseline D:/motorstorm/ppucc/conf2#B --candidate D:/motorstorm/ppucc/conf2#F --ppu-max 8
py -3 perfbench.py run   --suite snap --baseline ..\spunat2\bin\e19_game.exe,..\spunat2\bin\gr_game.exe --candidate <same or new exes>
py -3 perfbench.py run   --suite all  ...            # spu + ppu + snap, one results file per suite
py -3 perfbench.py check --suite spu --baseline <exe> --candidate <exe> --recs ..\spuopt\rec\Kksr2
py -3 perfbench.py check --suite all --baseline ... --candidate ... --ppu-base D:/motorstorm/ppucc/conf2#B --ppu-cand D:/motorstorm/ppucc/conf2#F --natbench 007A4C48
py -3 perfbench.py race  --factors results\<stamp>_run-spu.json --lanes 6     # MODELLED race section only
```

Flags: `--rounds N` (alternating baseline/candidate rounds, min of N; default 3), `--reps` (in-exe repeats),
`--ppu-max` (first N functions of names.json), `--lanes` (SPU lanes for the race model; default 6).

- `spu`: `spu_task_replay` (`verify`, `bench`) over TASKREC recordings grouped by image id
  (`rec_<decimal id>_NNN.bin` = hex id in the race trace). Net = best run minus the exe's reported fixed overhead.
  Each image needs exactly one verifying exe per side; list several exes with commas.
- `ppu`: `wl2` arms in a wl3 build dir (`DIR#ARM`), floor-subtracted (empty function), transcripts compared first.
- `snap`: `<x>_game.exe snap 3 <files>` over FNREC groups in `D:/ms_fnrec3|5|6`, min of N rounds.
- `check`: bit-exact gates only. SPU: candidate must verify every image that some exe verifies on the baseline.
  PPU: transcripts of the two arms must match for every name. `--natbench ADDR` runs
  `ppuopt/nat/tools/natbench.py ADDR --nobench --nomut` (builds with clang, ~30 s; only natives in
  `ppuopt/nat/natives/` work). Exit 0 = PASS, 1 = REJECT, 2 = INCOMPLETE (some images had no verifying exe).
- Output: `results/<YYYYMMDD-HHMMSS>_<suite>.txt` and `.json` (the json holds the rows and the `factors` used by `race`).

## Labels

Every row carries MEASURED, INDICATIVE, or FLOOR-BOUND. The race section is always MODELLED.

## Race model (MODELLED, not measured)

`race_model.py` reads `generated/analysis/waits/cpath_waits.txt` (ftrace of a recorded race, 191 frames).
Per steady frame (index >= 98, frame < 50 ms, as `crit.py`) it takes the main-thread waits (cv 94CCA8 and
event-queue waits >= 60 us) and the SPU work overlapping each wait (hk tasks and SPURS jobs). The work is
packed onto L lanes (greedy), with jobs in flight at the window start occupying lanes. Each wait ends at its
measured end. Candidate durations are the observed durations times the candidate/baseline factor of the job's image.
Validation: the baseline model frame vs the measured trace frame. The saving is the mean of the modelled delta.
PPU functions use the share method (race `m2_race200.txt` "top exclusive" shares x (1 - 1/speedup)); the
main-thread spin `func_0050C818` is excluded.

## Known limits

- PPU has no recorded real inputs. PPU numbers come from synthetic window inputs and are INDICATIVE. Do not
  report them as game gains.
- SPU numbers use recorded real task states (replay), not a full game run.
- Race-only effects are not modelled: DMA waits, RSX, SPURS scheduling beyond the observed job timings,
  jobs that never block the main thread (ignored by the DAG model).
- The DAG model's validation error depends on the lane count (see the race output); the default 6 SPUs gives
  about -1.6% on the 85 steady frames of the trace.
- A modelled saving is not a race fps gain until a race is measured. Never report it as one.
- Snap rows: one exe per entry, floor-bound rows (< 0.05 ms) are not resolved.
- Mutant/unknown images without a verifying exe are NOT CHECKED (the check returns INCOMPLETE, not PASS).
