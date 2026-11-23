# NEXT_RACE_PLAN: minimum authorised race tests (Task 9). NOT EXECUTED

Nothing here has run. Each race needs explicit authorisation. All runs go through `generated/analysis/vksync/ab2/run_vk.py` unchanged in behaviour:
- strict tag order (`ORDER`, next tags after `Kksr46`);
- preflight: quiet PC, an active `>console`/`>rdp-tcp#` session, free RAM/VRAM;
- no FORBIDDEN variables.

This plan only adds `K_BY_TAG` arms in the existing style.

## Preflight additions (operator checklist)
1. Quiet host: the brief's "±5 %" does not hold when other work runs. Same exe/env gave 35.0 fps (Kksr43) and 11.6/15.5/24.7 fps (Kksr44-46). Before each run, `Get-Counter '\Processor(_Total)\% Processor Time'` must be < 10 % for 30 s with MotorStorm not running. Abort the pair if bf1943/SSX/Nightfire/other agents' builds are running (Kk71-Kk77 history).
2. Exe: baseline `68cdc70d0f25a3c12a64cfdd5d26ce6a30279275bcbaad1c2a2f793e0222c8d5` in `spuopt/exe_v` (the Kksr24-46 pin). Verify the sha256 before each run.
3. Disk: ≥ 8 GB free on C:; trace files go to D: (`D:\cp60_runs\`).
4. After the run: race fps from `[rsx-hb]` over race_entry+25 s..stop (`criticalpath60/tools/run_fps.py`). Reject the run if fps is < 30 or the `[frame-hist]` p50 median is > 36 ms (disturbed host).

## R1: one combined "frame map" race (baseline exe, existing switches only, no code change)
Purpose: per-site waits without PT logging in **driving** frames; renderable interpreter miss sites (C2); handler latency in driving (C1); production-like main thread (C3).

Environment = the Kksr43 environment plus:

| Variable | Value | Why | Expected overhead |
|---|---|---|---|
| `PS3_TRACE_OFF_FILE` | as today, **and the controller writes it at `race_entry` + 2 s** (the runner already watches the timeline; only a file write is added) | removes the 1.11 ms/frame of route hooks once navigation is done (C3); stderr must then show `[PT] off:` | negative (removes overhead) |
| `PS3_SAMPLE=2`, `PS3_SAMPLE_MAIN=2`, `PS3_SAMPLE_M2_TOP=150` | as Kksr23 | main-thread split by function; per-caller inclusive gives per-site waits | ~1 % (hold 17-27 us per 2 ms sample) |
| `PS3_CRITICAL_PATH_TRACE` | `120:70:D:\cp60_runs\r1_cpath.txt` | SPU job/task spans, main syscall/usleep spans, lane picks, flips over race entry (~100-125 s) through driving. Kksr36 wrote 315k spans per 10 s; 70 s ≈ 2.2 M < the 4 M default cap | small: in-memory spans; hooks only on syscalls, job/task begin/end and picks (Kksr36's intro frames stayed ~31 ms despite heavy PT, so ftrace alone is light; PARTIAL) |
| `PS3_FTRACE_SPUJOB` | `3214:1320` | job spans and interpreted steps (kind 27) | small |
| `PS3_SPU_AOT_PROF` | `5` | image/pc/reason/steps/ns of every AOT miss, every 5 s (`spu_channels.c:2844-2935`) | only on misses (hash table + 2 clock reads) |
| `PS3_SPU_TASK_STATS` | `1000` (already set) | Havok per-run MFC/atomics/on-CPU | small |
| `PS3_SC_WAIT_MS` / `PS3_HLE_WAIT_MS` | `1000` (already set) | per-thread syscall/HLE waits, handler poll rate | small |

**Do NOT set** `PS3_TRACE_FILE=waits_sites.cfg`: the per-call PT logging is what made Kksr36 race at 14 fps.

Optional, only if per-call wait sites are needed later: a lean PT config with `limit=0`, `sample=none`, `report=1000` on 0x4AACA0, 0x94CC80, 0xA4C590, 0x50C818, 0x413390, 0x5F74B0, 0x5F5E98, 0x3AD890, 0x63E698, 0x187108. Per-site `fnstat` totals come out with no per-event lines. But mask ≠ 0 brings back the per-call hook cost (~1.1 ms/frame, C3), so use it in a separate run, not R1. PARTIAL: `limit=0` printing nothing is read from `ppu_trace.cpp:249-254`, not run.

Analysis after R1 (offline, existing tools):
- `run_fps.py`, `maincyc.py`;
- `waits/tools/m2_agg200.py <log> <start_ms>` for main-thread categories in driving windows;
- `criticalpath60/tools/{decomp,batch_hops,lanes,phases,rj_model}.py`. These need a PT file for main-thread intervals. Without PT, use ftrace kind 2 (usleep, lr 0x94CCA8 = cv waits) and kind 1 a=0x82 (semaphore) for main waits, as `waits/tools/crit.py` does;
- `[spu-aot-prof]` lines: group by image 1296695296 and reason (miss/rejoin/resume/restart/irq-restart).

Success criteria:
- fps within the 33-35 band of the pinned exe;
- `[PT] off:` logged;
- ≥ 300 driving frames in the ftrace;
- the AOT profile names the pcs behind ≥ 80 % of renderable interpreted steps.

## R2/R3 (and R4/R5): A/B of C1 (needs one small runtime change, built and unit-tested offline first)
- Change (to be made on an isolated copy, not a shared tree): let `PS3_USLEEP_SPIN_MAIN_ONLY` accept extra guest thread ids (or the call site lr 0x4AF6D0) so tid 12 gets the exact spin tail. Unit test: usleep(200) never early, p99 < 260 us; CPU of the spinning thread recorded.
- Arms: A = baseline env (with trace-off at race entry, as R1, but without sampler/ftrace); B = A + handler tid in the spin set. Order A, B, A, B (4 races) on a quiet PC.
- Metrics:
  - race fps (primary);
  - `[sc-wait]` tid 12 calls/s (expect ~4,000/s instead of ~1,780/s);
  - tid 1 usleep ms/s (expect lower);
  - frame-hist p50.
- Decision: keep only if both B runs beat both A runs and the mean gain is > 3 %. Modelled 1-3 ms ≈ 3-10 %.

## R6 (after R1 identifies C2's miss sites and an offline-validated fix exists)
- A/B the C2 build vs baseline, 2+2 races. Metrics: kind-27 steps per renderable job (expect ~0), Present spin share in m2 (if sampled), fps.

## What is deliberately not proposed
- No race for C5/C6 alone: modelled < 0.7 ms, below the noise of 2+2 races.
- No reordering experiments (BLOCKED, see PPU_DEPENDENCIES).
