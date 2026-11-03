# T64 / T64B: LoadRace stall diagnosis

2026-10-26. T64B: one private session (`generated/runs/20261026-134822-t64b-loadrace-stall`, `t64/runtime-20261026-134821/`).
- Same exe as T63 (sha256 `162afb4a…6b7`, includes the T61 font fix). WWS AOT, TEX_SAVE and TEX_NOCACHE are off.
- Fresh private HDD copies `t64/hdd0b` and `t64/hdd1b`.
- Navigation is transition-driven. All 59 LoadRace markers are traced, plus `stall=4000`, slow syscalls (250 ms or more), fnstat every 5 s, `SPURS_LFQ_TRACE` and `PS3_FSTRACE`.
- Nothing merged or pushed. No shared state touched. No loading or SPURS logic changed.
- The T64 run 1 report (BLOCKED at ticket select) is kept as `RACE_LOADING_STALL.run1.md`.

## Result: **PARTIAL**

LoadRace was **progressing normally through 7 stages** when the session was cut at 138.3 s. No stall was observed.

The cut came from my controller, not the game:
- The tracer emitted `ev=exit … how=unwound site=FFFFFFFF` for `0x89230` and `0x8EA00` at 127.19 s. This is a shadow-stack unwind during the world LoadInternal, not a real return; markers kept firing afterwards.
- `run_t64.py` treated it as "LoadRace returned" and stopped 10 s later.
- So LoadRace was observed for **29.6 s**, while T63 went quiet about **58 s** in. The T63 quiet window was not reached.

## 1. Navigation (VERIFIED, 4 CROSS, no manual input)

| host s | event |
|---|---|
| 81.2 | main menu loaded (38 s in run 1; slower startup this time) |
| 87.8 | Festival screen; no tutorial, as in run 1 |
| 94.5 | ticket select, Kanaloa Bay "Light Fantastic" |
| 101.1 | vehicle select; ATV is the default |
| 108.4 | Select pressed; no ATV-info tutorial (T63 had one, because that run's save state differed) |
| 108.67 | `LoadRace 0x89230` entered (from `0x8EA00`) |

## 2. LoadRace stage timeline (VERIFIED; PT timestamps; all on tid 1)

| PT s | site | marker | stage duration |
|---|---|---|---|
| 108.109 | `0x892C4` | LOAD RACE START | |
| 108.109 | `0x8CA60`, `0x8CB28` | IO tasks / ghost filenames (early pass) | ~0 |
| 108.112 | `0x89760`, `0x8979C`, `0x897DC` | SPU push buffer, job-manager buffer, AudioMemMalloc | 4 ms |
| 108.115 → 108.256 | `0x89828` → `0x898D8` | apply config | 0.14 s |
| 108.256 → **128.189** | `0x898E4` → `0x89E04` | **load WORLD** | **19.93 s** (T63: 19.16 s) |
| 128.189 → 128.242 | `0x89E48` → `0x89F08` | viewports | 0.05 s |
| 128.242 → 128.364 | `0x89F4C` → `0x89F84` | AI binary block | 0.12 s |
| 128.364 | `0x89F90`, `0x89FC0`, `0x89FCC`, `0x8A004` | scene tracking, splines | ~0 |
| 128.364 → **134.657** | `0x8A010` → `0x8A060` | **visibility load level** | **6.29 s** |
| 134.657 → 135.300 | `0x8A060` → `0x8A0D8` | Gag system | 0.64 s |
| 135.300 → 137.603 | `0x8A0E4` → `0x8A11C` | audio systems | 2.30 s |
| 137.603 → (cut at 138.3) | `0x8A25C` | **vehicles pre-load**: LoadInternal `split_vehiclestv03_LV0` (lr `0x3944FC`, 137.67) | open |

- **Last completed stage:** audio systems (`0x8A11C`).
- **First incomplete stage:** vehicle pre-load (`0x8A25C`), active for only 0.7 s when the session was cut.
- **Not reached:**
  - the vehicle and character stages;
  - PostLevelLoad (`0x8C2A0`/`0x8C2E0`);
  - `0x8C848`;
  - the final IO loop (`0x8C994`…`0x8CA34`: pump `0x222368`, pending `0x21BB38`);
  - IO done (`0x8CA60`, second pass).

## 3. Outstanding requests and waits during LoadRace

- **Main thread (tid 1):** no `ev=stall` report at any point, so no frame stayed innermost for 4 s or more. No syscall of 250 ms or more after 105 s (3 slow syscalls in the whole run, all before the menu).
  - The world LoadInternal (`0x536A30`, n=50, lr `0x3944FC`) is a single 18.92 s call, but its callees kept changing.
- **Visibility stage (6.3 s):** no LoadInternal and no main-thread stall. PushBody dropped to 19 per 5 s (130–135 s). It looks like CPU-bound main-thread work, but which function is spending the time was not traced (HYPOTHESIS).
- **SPURS:** the one long `EventFlagWait BLOCKED` (tid 8124, flag `0x0140F000`) ran from 70 s to 94 s, before LoadRace; there were none during LoadRace.
  - PushBody (`0x8A85674D`) rc=0 throughout; no NOSYS.
  - Rate per 5 s: about 1000 in the menus, then 416/500/80/248 during the world load, 19 during visibility, 142 during Gag/audio.
- **Files:** only the known missing-loose-file `open FAIL` (`data/events/light_fantastic.race`, `atvsmall_player.vsb`, `dspsettings`). FIOS `cache.dat` is 460 MB (fresh copy).
- **Health:** no crash, no Present timeout; heartbeat 1389 frames at 132 s.

## 4. Slow progress or deadlock?

**Slow progress, up to 137.6 s (VERIFIED):**
- 19 markers fired in order;
- every stage completed;
- no blocked main-thread frame;
- SPURS decompression kept accepting work.

Stage durations match T63 (world 19.9 s vs 19.2 s), so T63's first 30 s of LoadRace were the same normal slow load.

T63's silence from 58 s into LoadRace onwards (180 s host) lies **beyond this run's window**. Whether a later stage deadlocks is still **undetermined**. Candidate stages: vehicle or character pre-load, PostLevelLoad, or the final IO wait loop `0x8C994`–`0x8CA34` on `0x21BB38`.

## 5. Function addresses

- **Race path:** race enter `0x8EA00` → LoadRace `0x89230`. Marker function `0x295EF8`; return sites are in `t30/loader/loadrace_markers.tsv`.
- **Loaders:** LoadInternal `0x536A30`:
  - world and vehicle callers: lr `0x3944FC`;
  - later callers: lr `0x3B98FC`, `0x3B9E50`, `0x9087EC`.
- **IO:** IO pump `0x222368`, pending check `0x21BB38`. LFQueue wrapper `0x7284A0` → PushBody HLE `0x8A85674D`.

## 6. Recommended next step

No code correction is justified: nothing in the observed window is broken.

**Next diagnostic:** one more bounded session (210 s or less), identical except that `run_t64.py` **ignores `how=unwound` exits** and stops only on a real `how=ret` exit of `0x89230`, or at the cap.
- LoadRace starts at about 108 s, so this gives about 95 s of loading, enough to pass T63's 58 s point.
- Optional, to save time: shorten the menu path (the main menu at 81 s vs 38 s in run 1 is unexplained).
- This needs your authorisation; I have not launched it.

---

# T64C: complete race-loading trace

2026-10-26. One private session that ran to the 205 s controller cap (under the 210 s limit).
- **Run dirs:** `generated/runs/20261026-140153-t64c-loadrace-stall`, `t64/runtime-20261026-140153/`.
- **Exe, trace and env:** same exe as T64B (sha256 `162afb4a…6b7`, T61 font fix), same `t64_trace.cfg` and env. TEX_SAVE and WWS AOT are off.
- **HDD:** fresh private copies `t64/hdd0c` and `t64/hdd1c`.
- Game code was not changed, there was no driving input, and nothing was merged or pushed.

## Result: **PASS**: LoadRace completes and the race initialises

**No deadlock.** The T63 "stall" was a slow load (about 89 s) that outlasted T63's session.

## 0. Controller preparation (verified offline: `test_ctl_c.py`, 9/9 PASS, `test_ctl_c.log`)

- `how=unwound` exits are logged as `race_loader_exit_ignored` and can never count as a return. The T64B stderr replay confirms this.
- A return is accepted only on `how=ret` from `0x89230` **plus** the PostLevelLoad marker `0x8C2A0`. Stop is 15 s after that.
- Marker pauses cannot stop the session. The only stop paths are corroborated return, the 205 s cap, operator STOP, and a controller error.
- Auto-input stops when `0x8EA00` is entered.
- **In the run:** the tracer again emitted `how=unwound` for `0x89230`/`0x8EA00` at 84.1 s, and the controller ignored it. The genuine return was never seen as a `how=ret` event, because the unwind had already dropped the frame from the tracer's shadow stack. The session therefore ran to the cap; that cost nothing.

## 1. Navigation (4 CROSS, transition-driven, no manual input)

| host s | event |
|---|---|
| 37.8 | main menu |
| 44.5 | Festival |
| 51.2 | ticket select, Kanaloa Bay "Light Fantastic" |
| 57.9 | vehicle select (ATV) |
| 65.1 | Select → race enter `0x8EA00` |

## 2. LoadRace entry

`0x89230` entered at PT **64.92 s**.

## 3. Stage timeline (VERIFIED; PT s; tid 1)

| PT s | marker site → site | stage | duration |
|---|---|---|---|
| 64.921 → 65.069 | `0x892C4` → `0x898E4` | start, buffers, apply config | 0.15 s |
| 65.069 → 84.924 | `0x898E4` → `0x89E04` | load world | **19.86 s** |
| 84.924 → 85.024 | `0x89E48` … `0x8A010` | viewports, AI, scene tracking, splines | 0.10 s |
| 85.024 → 91.238 | `0x8A010` → `0x8A060` | visibility | **6.21 s** |
| 91.238 → 91.841 | `0x8A060` → `0x8A0D8` | Gag system | 0.60 s |
| 91.841 → 94.195 | `0x8A0E4` → `0x8A11C` | audio systems | 2.35 s |
| 94.195 → 110.534 | `0x8A25C` → `0x8A858` | **vehicles pre-load** | **16.34 s** |
| 110.534 → 137.610 | `0x8A858` → `0x8AF98`/`0x8AFD0` → `0x8B00C` | competitor 1, including character load (0.96 s) | **27.08 s** |
| 137.610 → 144.571 | `0x8A858` → `0x8B00C` (loop, ×15) | competitors 2–16 | 0.3–0.7 s each, 6.96 s total |
| 144.572 → 144.793 | `0x8B1EC`, `0x8B210`, `0x8B21C`, `0x8B494` ×16 | Gag add drivers, grid positions | 0.22 s |
| 144.79 → 148.067 | `0x8B57C` … `0x8BF28`, `0x8C1F0` | helper nodes, game scene, clients, callbacks, particles | 3.27 s |
| 148.067 | `0x8C2A0`, `0x8C2E0` ×16 | **PostLevelLoad**, InitialiseEffects | 0.06 s |
| 148.122 → 152.057 | `0x8C400`, `0x8C498` → `0x8C6A0` | audio samples, deformation, ApplyConfigLoadGUI | 3.93 s |
| 152.057 → 153.169 | `0x8C6B4`, `0x8C6D8`, `0x8C754`, `0x8C848` | resource update, tags | 1.11 s |
| **153.800** | `0x329D90` entered from **lr `0x8EE8C`** (inside `0x8EA00`) | loading-screen teardown, **after LoadRace returned** | |

- **LoadRace total:** about **88.8 s** (64.92 → ≤153.80). The slowest stages are competitor 1 (27.1 s), world (19.9 s), vehicle pre-load (16.3 s) and visibility (6.2 s).
- **Final IO wait loop `0x8C994`–`0x8CA34` / `0x21BB38`:** not a blocker. `0x21BB38` was entered once in the whole run, and LoadRace returned 0.6 s after `0x8C848`.
- **The `0x8CA60` marker** fires only at LoadRace start: its code sits early in the function's layout, and there is no second pass.

## 4. Last completed stage

All stages completed: `0x8C848`, then the return to `0x8EA00`.

**Corroboration:**
- `0x329D90` was entered from `0x8EE8C` at 153.80 s.
- Race GUI pages loaded at 152.1–153.1 s, all via `0x536A30`:
  - `gui/pausemenu.gui`, `gui/race-summary.gui`, `gui/race-results.gui`;
  - `gui/textureresources`, `gui/osd.gui`, `gui/osd-main.gui`, `gui/invitation-popup`.
- On screen (`screens/t64c_079_race_intro.png`; frames 075–079, 168–203 s): the race-intro overlay "Press ⊗ to Skip".
- Per the brief, no input was sent: no skip, no driving.

## 5. First incomplete stage

None inside LoadRace. The race is in its pre-race intro (skippable) state.

## 6. Outstanding work at termination (205 s)

- **Main loop alive:** the IO pump `0x222368` runs about 5 times per second (one per frame). No new `0x536A30` loads after 153.1 s; 127 loads in all, 123 completed.
- **FIOS/SPURS streaming active:** PushBody `0x8A85674D` ran about 175–250 per second at 155–205 s, rc=0 every time; there were no NOSYS errors and no non-zero HLE returns.
- **Stall reports after LoadRace:** only non-race threads (tid 28 `0xCC021C`, tid 7 `0x649E10` recursion, tid 13 `0x94CD58`); tid 1 never stalled.
- **Frame rate in race state:** about **5 fps** (heartbeat 4733 → 4981 frames over 153–203 s), compared with about 32 fps in the menus and while loading.
- **Final frame RSXI capture (frame 4985, `rsxi/reports/summary.json`):** 256 draws, 22 render targets, 54 textures, one high-severity `rt_feedback` (t2 samples bound colour target `0x00750000`).
  - The backbuffer is **black except for the HUD text**: the scene region has max pixel value 0.
  - So the race scene is drawn but does not reach the image. This is a new, separate rendering issue (PARTIAL; cause not investigated).

## 7. Progress versus deadlock

**Progress, VERIFIED:**
- Every LoadRace stage fired in order, and the function returned.
- At most 27 s passed between consecutive markers (competitor 1), and assets kept loading during that gap.
- T63's apparent stall at 180 s host is explained: T63 entered LoadRace at 121.5 s, so it would have needed until about 210 s host, beyond its 205 s cap.

## 8. Narrowest justified next action

**No loading fix is warranted.** For the next bounded session, either:
- **(a)** raise the time budget, or start nearer the race (LoadRace ends about 154 s after launch, leaving about 50 s inside the cap); or
- **(b)** move on to the black race scene and the 5 fps race state. Start with the RSXI capture already taken (frame 4985: `rt_feedback` on surface `0x00750000`, and the final composite/exposure pass), offline, before any new run.

**Two notes for future runs:**
- Allow the intro skip (CROSS) only if a driving test is authorised.
- The tracer's unwind on `0x89230` means the controller must treat `0x329D90` entered from `0x8EE8C` as the LoadRace-return signal.
