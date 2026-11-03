# T64: LoadRace stall diagnosis

2026-10-26. One bounded private session: 205 s, under the 210 s cap. Nothing merged or pushed. No shared worktree or HDD touched. No code changes.

## Result: **BLOCKED** (instrumentation never reached LoadRace)

The run reached Kanaloa Bay ticket select. My navigation controller then stopped on a wrong expectation, and the game sat on the ticket screen from 50 s to 205 s. LoadRace was never entered, so this run says nothing new about the stall.

## 1. Runtime baseline

- **Exe:** `t64/exe/MotorStormPacificRiftRecomp.exe`, sha256 `162afb4a…6b7`. This is the same binary as T62B and T63, and includes the T61 font fix. No rebuild.
- **HDD:** fresh private copies `t64/hdd0` (0 files) and `t64/hdd1` (4 files); see `snapshot_manifest.json`.
- **Env:** T63's env, unchanged. TEX_SAVE, TEX_NOCACHE and WWS AOT are not set; CELLMARK_DUMP is 160/60.
  - Added: `PS3_TRACE_FILE=t64_trace.cfg`, `SPURS_LFQ_TRACE=1`, `PS3_FSTRACE=100`.
- **Trace config `t64_trace.cfg`:** checked with `pt_cfg_check` (`pt_cfg_check_t64.log`): `fn=18 ret=59 hle=6 sc=all stall_ms=4000`.
  - `fn=`: the menu path, race request and state, `8EA00`, `89230`, the loading screen, `536A30` (LoadInternal), the IO pump `222368`, `21BB38` and `7284A0`.
  - `ret=`: all 59 T30 LoadRace marker sites.
  - `hle=`: the savedata imports and PushBody.
  - `sc=all`: only syscalls lasting 250 ms or more.
  - `stall=4000`: guest stack of any thread whose innermost frame is older than 4 s.
  - `report=5000`: fnstat every 5 s.
- **Run directories:** `generated/runs/20261026-131914-t64-loadrace-stall` and `t64/runtime-20261026-131914/`. Frames are in `t64/screens/`.

## 2. What happened (VERIFIED)

| host s | event |
|---|---|
| 37.9 | `mainmenu.gui` loaded |
| 45.1 | CROSS 1 → `76AF40`, then `festivalguide`. The Festival menu opened **directly**: the rank tutorial seen in T63 did not appear, and `buttons_select_back` loaded at the same moment. |
| 50.4 | CROSS 2 (the controller believed it was the tutorial) → `SetSelectedZone` → `ticket-select-earthzone`. Kanaloa Bay "Light Fantastic" is on screen (`screens/022`, `102`). |
| 56.4 | The controller expected `ProfileSave` (the T63 tutorial path), did not see it, and switched to manual mode as designed. |
| 56–205 | No operator input: my live monitor pipe buffered its output (`grep \| cut`), so I never got the manual-mode event. The game idled on the ticket screen until the cap. |

- **Health:** no crash, no NOSYS, no Present timeout.
- **Off the race path:** 29 `ev=stall` reports, all from menu and idle threads.
- **FIOS HDD cache:** `cache.dat` grew to 820 MB with menus only (T63: 495 MB after loading). It is still being filled in the background; this is an observation, not yet a finding.

## 3–7. LoadRace stages, last completed, first incomplete, outstanding work, blocked or slow

**Not measured: LoadRace was not entered in this run.** The only evidence is still T63's (offline re-read):
- The world `.rpk` LoadInternal (`536A30`, lr `0x3944FC`) took **19.2 s** (121.7 → 140.8 s), and the environment load 0.5 s.
- LoadInternal kept completing slowly afterwards: 64 calls by 150 s, 71 at 170 s and 77 at 180 s. **There were none from 180 to 205 s**, and PushBody (FIOS decompression) dropped to 0 over the same window.
- So in T63, loading was **progressing slowly until about 180 s and then went quiet**. Whether that is a stall or a pause can't be decided, because T63 had no stage markers (HYPOTHESIS).

## 8. Narrowest root cause

None established. Only candidates exist, unchanged from T63: (a) a race-only stage after the world load; (b) slow FIOS/SPU decompression; (c) a resource wait.

## 9. Correction made, offline only

`run_t64.py` navigation is now **transition-driven** rather than a fixed seven-step list:
- Every screen on the route takes CROSS with default focus.
- The controller presses CROSS after 6.5 s without screen activity.
- It requires a route transition within 6 s, and stops pressing when `0x8EA00` is entered (at most 9 presses).
- This handles both the tutorial and no-tutorial variants.
- The tracing is unchanged and already parse-checked.
- For future runs, the live monitor must not pipe through an unflushed `cut`.

## 10. Another run needed?

**Yes.** One more bounded session of 210 s or less with the same exe, env and trace, and the corrected navigator. LoadRace should start at about 85 s, leaving about 115 s of fully instrumented loading. That needs your approval; I have not launched it.
