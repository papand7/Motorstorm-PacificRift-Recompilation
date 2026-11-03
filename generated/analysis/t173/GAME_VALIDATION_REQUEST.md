# T173 game validation request

**Not run. Needs your authorization: one build and one game launch.** Nothing below has been executed except the offline checks in `REGRESSION_VALIDATION.md`.

## What is being validated

The jump-table fix (ps3recomp `b6f53f8` on `fda8c9b`) removes the `unresolved indirect call -> 0x00CB7FA8` that ended T170 arm A at race + 54 s and the T169 baseline at race + 36 s. The executable differs from T170 arm A in exactly two lifted chunks (the switch in `func_00CB7D80`, and its duplicate `func_00CB7D7C`). Runtime code is identical to the T170 exe's.

## Preparation already done (private, offline)

| item | state |
|---|---|
| lifter fix | committed, `b6f53f8`, `agent/t173-ppu-jump-table` |
| lifted tree | `generated/ppu-t173-staging`: the 2026-10-21 staging with `ppu_recomp_006.cpp` and `ppu_recomp_026.cpp` replaced (77 hard links, a copy of `ppu_hle_nids.cpp`). SHA-256 manifest: `generated/t173/overlay_sha256.txt` |
| build script | `generated/analysis/t173/tools/build_t173.cmd` (copy of `build_t170.cmd`: `ps3recomp-t173`, `RECOMP_DIR=generated\ppu-t173-staging`, build dir `build\motorstorm-t173`) |
| runner generator | `generated/analysis/t173/tools/make_runner_t173.py <exe sha256>` -> `ab/run_t173.py` (T170 arm A, T173 exe, crash stop) |
| rebuild of the tree | `prepare_staging_t173.py` (needs a scratch lift with the T173 lifter, command in its header) |

## Request

1. **Build** `build/motorstorm-t173` with `build_t173.cmd` (clang-cl, Release, 6 jobs). A fresh build directory recompiles every lifted chunk; about 25-60 minutes (estimate from the 105 s and 19 s measured for the two changed chunks, not measured end to end). Record the exe SHA-256 and that no source is newer than it. **No other build.**
2. **One launch** with `ab/run_t173.py launch A V1`, then stop and report. No retry, no extra arms, no B or C, no merge or push.

## Settings (identical to T170 arm A)

`RSX_VP_FAST_FETCH=0 RSX_FP_SCAN_MEMO=0 RSX_VP_PARALLEL=0`, T165 `ENV_LEAN` and `TEXRES`, `RSX_PERF_DEEP=1`, same route and flyover skip, fresh private HDD, no `D3D12_DBG`, no manual driving. Maximum 205 s game, 210 s host. Dry run must show the same 53 `--env` entries as T170 arm A except paths. The only difference from arm A is the executable.

## Host conditions (a lesson from T170 and the baseline run)

Close Godot and confirm no GPU or CPU use; stop Ollama and release its VRAM; close or suspend other workloads; no other MotorStorm process, build, test or GPU job; session local; Present interval and window visible (a hidden window can collapse SPURS timing). The T170 baseline run found a clean host at 553 MiB GPU memory after Ollama and Godot were closed.

## Stop conditions (runner, as the baseline run)

Unresolved indirect call, null-page write, guest crash, watchdog timeout, FIFO resync, device removal, Present timeout, other serious failure. The runner stops 3 s after a guest crash so the dump reaches the log. Race entry is about 123-126 s, so the 205 s cap gives about 80 s of race.

## What passes

| outcome | reading |
|---|---|
| no `unresolved indirect call`, no null-page access, no new `[ppu]` error; frames keep presenting to the cap (at least race + 70 s); `[rsx-hb]` frame count rises to the end; no FIFO resync | **fix holds for this run**, not proven stable (the trigger time varies, risk 2) |
| same `0x00CB7FA8` | the fix did not take effect in the build: check that the exe contains the new chunks (hash of the staged files, symbol for `loc_00CB7FA8`) before any other conclusion |
| a different `unresolved indirect call` or null access in `func_00CB7D80` or a callee | the switch now runs and reached another gap: record target and call chain; classify with the same table-shape scan |
| a different crash outside the guest (renderer, GPU) | document separately; causality unresolved |

## Evidence to collect

- Guard before and after (`run_guard_t167.py`); the exe SHA-256 and the new chunk hashes; session and workload state.
- Race duration, last `[rsx-hb]` against the end of the session, and the full list of `[ppu]`, `[null-read]`, `[null-write]` lines (counts, first and last).
- Compare to the baseline run (`20261030-214922-t170base-AB1`) and arm A: p50/p95 per phase for 20-30 s after race entry, and frame dumps at matched race times (vehicle, terrain, HUD, shadows) for visual or synchronization regressions. Frame time should be the same as arm A, since the runtime is identical.
- Arm A's total race frames over 54 s is the yardstick for the fix running longer.
- If it fails, `PS3_TRACE` for `fn=00CB7D80` on a second authorized run only.

## Not requested

Arms B and C of the T170 benchmark. The fix only removes the early end of long runs; B and C stay blocked until one run reaches the cap.
