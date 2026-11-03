# T90: intro-skip reliability (offline, 2026-10-27)

- **Worktree:** `ps3recomp-t90`, branch `agent/t90-intro-skip`, from `d04a614` (the T87 base).
- **Changes:** no source changes, no build, no launch, nothing merged or pushed. T87B (`ps3recomp-t87b`, motorstorm01-3c) was not touched.
- **Inputs:** the 59 runs under `generated/runs` that log `[pad-trigger] press`, and the retail ELF (read-only disassembly).

## 1. Verdict

- **VERIFIED:** the press is delivered identically in all 59 runs: 1500 ms after the `gui_intro_eu.bik` open, held 156–157 ms, 15 reads (14–16), one release.
- **VERIFIED:** 58 of 59 runs skipped the intro: the next frontend file opened 1.0–2.0 s after the press. The one failure is T87: +109.8 s, the full intro (`t90/logs/skip_outcome.txt`).
- **VERIFIED (code and timing):** the input was **blocked by frame scheduling and then overwritten in the guest's own pad ring**.
  - It was not consumed too early, not held or released incorrectly, and not delivered during a non-skippable phase.
- **The pause is a necessary condition, not the cause by itself.**
  - A 3.1 s frame-thread stall loses the press only if it starts at least about 20 pad polls (≈ 200 ms) **before** the press and ends **after** the release.
  - In T87 it started 279 ms before.
  - The same stall starting 150 ms before the press, or during the press, keeps it (tests §5–6).

## 2. Original behaviour (retail code, VERIFIED unless marked)

1. **Pad thread `0x72ADF0`:**
   - Every poll it takes the pad lock, calls `cellPadGetInfo`, then `cellPadGetData` for ports 0..6, and writes **one snapshot entry** (0x644 B) into a **20-entry ring**.
   - The slot is `(head + count) % 20`, then `count = min(count + 1, 20)` (`0x72AE40..0x72AE7C`, `0x72AFC8..0x72AFE0`).
   - It then sleeps `[ctx+0x7D80]` µs (`sc 0x8D`, `sys_timer_usleep`). That is about 10.4 ms: 15 reads in 156 ms.
   - **Once the ring is full, slot = head: every new snapshot overwrites the same slot, and all but the last are lost.**
2. **Consumer `0x72B3A8`** (`0x72B6D4..0x72B744`):
   - When `count == 20` it reads from `head + 1` (`0x15 + head`, mod 20); otherwise from `head`.
   - The drain loop's end and the head/count reset are modelled, not fully decoded (PARTIAL).
   - It runs once per game frame on the frame thread. That is **HYPOTHESIS**, consistent with T87: the press was polled 15 times while the frame thread was blocked, and it was never acted on.
3. **GUI:** the intro page's Accept slot (+0x4C) leads to `TransitionPage(black)`, from the earlier `ORIGINAL_INTRO_SKIP_ANALYSIS.md`. It acts on a press.
4. **Readiness:** 58/58 skips at 1500 ms show the page accepts input by then. There is no evidence of a non-skippable phase.

## 3. Host implementation (VERIFIED)

- `port/main.cpp` `dev_skip_intro()` calls `pad_trigger_configure("gui_intro_", 0x4000, 1500, 150)`.
- `ppu_fs.cpp:312` arms the trigger on the first matching open.
- `cellPad.c:667` ORs CROSS into port 0's DIGITAL2 while `PT_PRESSING` (`include/ps3emu/pad_trigger.h`).
- The release is based on **wall clock**: ≥ 150 ms **and** ≥ 3 reads. It is one-shot, and nothing in it observes the guest's frame loop.
- `cellPad.c` hands out one change packet per 4 ms host report, so each guest poll gets a full `len > 0` packet. No polls are dropped on the host side.

## 4. Evidence: T87 versus the successful runs

| | T86I (skipped) | T87 (not skipped) |
|---|---|---|
| Frame thread at the press | `0x72E1E0` (ref throttle) exits in 6 µs–10 ms | entered at 37.067 s, exited at 40.210 s (`dur_us=3143139`) |
| Press / release (PT time) | 36.906 / 37.064 s | 37.346 / 37.503 s, 279 ms **after** the stall began |
| Ring at the first pressed poll | nearly empty, drained each frame | full: 27 polls since the last drain, more than 20 |
| Polls after the release before the next drain | 0–1 | about 260 |
| Heartbeat gap at the press | 1093 ms (normal 1 s) | 3235 ms, 3 frames |
| Result | `last_draws` 21 → 42; `gui_c.bik` +1.x s | `last_draws` stays 23; intro plays 124 s |

- The worst heartbeat gap at the press in the 58 successful runs is 1188 ms. Only T87 has a multi-second frame-thread stall there.
- **The 3.2 s pause:** the frame thread spins in `0x72E1E0` on `ctrl->ref`, while the present thread, which runs the FIFO walker, is blocked outside the walker. Its cause is not captured, and it is T87B's question.
- This report claims nothing about why the stall happens, only how it loses the input.

## 5. Offline tests (PASS, 27 checks)

`t90/tests/test_intro_skip_lifecycle.c` uses the **real** `pad_trigger.h` from `ps3recomp-t90` with explicit times, plus a model of the guest ring above. Build: `t90/tools/run_t90_tests.cmd` (clang `-Wall -Wextra -Werror`). Log: `t90/logs/test_intro_skip_lifecycle.txt`.

| § | Covers | Result |
|---|---|---|
| 1 | Lifecycle: no arm on `attract_*`, press at open + 1500 ms, held 150–170 ms, 15–16 pressed polls, one rise and one fall, no re-arm | PASS |
| 2 | Normal 16 ms frames: one Accept within 2 frames | PASS |
| 3 | Delayed presentation: frames of 16–190 ms keep the press | PASS |
| 4 | **T87 timeline** (stall −279 → +2864 ms around the press): delivered, Accept **lost** | PASS (reproduces) |
| 5 | The same stall from +40 ms, from −150 ms, or ending mid-press: kept | PASS |
| 6 | Sweep of the stall start from 0 to 600 ms before the press: lost **exactly** when the ring is full before the first pressed poll | PASS |
| 7 | Repeated polling (3 extra port-0 readers): the hold stays ≥ 150 ms; kept | PASS |
| 8 | Readiness: a page ready at 1400 ms keeps the press; one ready only after the release loses it | PASS |
| 9 | Proposed gate: normal timing unchanged (< 170 ms); T87 timeline kept, with one press held through the stall; every sweep start kept; frames up to 400 ms kept | PASS |

Run-level confirmation tools: `t90/tools/skip_outcome.py` (next frontend open within 30 s of the press) and `classify_runs.py`.

## 6. Smallest proposed correction (not implemented)

- **In `pad_trigger_apply_at`:** release only when ≥ 150 ms **and** ≥ 3 reads **and** ≥ 2 guest flip requests have passed since the press.
  - Use `cellGcm_flip_request_count()`, which `cellPad.c` already uses for `PAD_CLOCK=flips`.
  - Add one field `flip_at_press`, and add the gate to `tests/test_pad_trigger.c` and `test_pad_trigger_getdata.c`.
- **Why this is not a timing hack:** a press is then defined as lasting at least two frames of the title's own loop, which is what a human press is to a frame-polled game. It does not delay, repeat or retry the press, and nothing in the guest changes. It fixes the wall-clock assumption that broke here.
- **Open (PARTIAL):** this needs flip requests not to advance while the frame thread is blocked. T87's heartbeat counted 3 backend frames in the gap; the guest flip-request count over the gap was not logged. Check `cellGcm_flip_request_count` around a stall before relying on it.
- **Not proposed:** re-pressing, longer fixed holds, or a later delay. Each only moves the window.

## 7. For T87B

- When T87B launches, any frame-thread stall that already covers open + 1.3 s and lasts past open + 1.66 s will cost the skip again: the ring is full before the press, and no drain happens until after the release.
- The T87 hypothesis 1 ("the pause caused the missed skip") is refined: the pause starting about 280 ms before the press, combined with the guest ring overwriting a single slot when full, lost it.

## 8. T87B run follow-up (read-only)

- Run: `generated/runs/20261027-084130-t87b-race-stall` (motorstorm01-3c's launch).
- **VERIFIED:** the skip worked.
  - `[intro-skip] OK`: a 42-draw frame 1937 ms after the press.
  - The next frontend file opened 1.0 s after the press.
  - The heartbeat gap at the press was 1015 ms, normal, with no frame-thread stall.
- This matches §1: skips succeed whenever no stall starts ≥ 200 ms before the press.
