# T171: game capture request and results

**Authorized and completed: exactly two launches, no retries, no new build. Frames and captures stay private** under `generated/analysis/t171/ab/` and `generated/runs/`.

| Item | Value |
|---|---|
| Exe | `t171/ab/exe_t/MotorStormPacificRiftRecomp.exe`, a verified copy of `build/motorstorm-t171` |
| SHA-256 | `4450EA1FA8D31BCFD6F24CA9B6018459331DAD96D6E4D14989B9511D6D12A8BE` (checked in preflight and in both wrapper logs) |
| Source | ps3recomp `b282e26`, port-t161 |
| Route | same automatic route and default vehicle (blue quad), beach start; no manual driving, only the runner's Cross presses |
| Cap | 205 s game, 210 s host, runner hard kill at 203 s |
| Session | local console; the runner stops if the session turns remote, and it did not |
| Fresh HDD | one verified private copy per launch, removed afterwards |

## Launches

| Arm | `RSX_SHADER_WINDOW` | Run | Race entry | Stop |
|---|---|---|---|---|
| A | 0 | `20261030-204039-t171-ATA` | 127.5 s | race entry + 45 s, no serious errors |
| B | 1 | `20261030-204342-t171-BTB` | 132.3 s | race entry + 45 s, no serious errors |

The runner kills the game at the planned stop, so "exited_error" in the log is expected.

## Settings

The generated runner confirms `RSX_SHADER_WINDOW` is the only differing environment key. The `[visual] effective` line was checked in both arms, ending `depth_state=0 mrt_state=1 rt_reinterp=0 shader_window=0|1`.
The set is T169 arm B, as listed in the original request: `ENV_LEAN`, `TEXRES`, `D3D12_DBG=1`, `RSX_COLOR_XFER=7`, `RSX_GUEST_SAMPLERS=15`, `RSX_TEX_MIPS=1`, `RSX_ZETA_EXACT=1`, `RSX_RT_WINDOW=1`, `RSX_RT_FEEDBACK=1`, `RSX_DEPTH_STATE=0`, `RSX_MRT_STATE=1`, `RSX_RT_REINTERP=0`.

**Changes from the original request, the same in both arms:** `CELLMARK_DUMP=32` and `CELLMARK_DUMP_EVERY=32` (was every 64), `RSXI_MINDRAWS=700`, `RSXI_MAX_EVENTS=4096` (draw records without constants, units or geometry), `RSXI_RTS=00750000,01650000,0243AB00,0BA10000`.

## Preflight

| Check | Result |
|---|---|
| Exe hash | match |
| Correction present | exe contains `RSX_SHADER_WINDOW`, `shader_window=%d`, `[WPOS]`; arm B logged the remaps |
| `=0` disables | source check and `test_shader_window` pass; arm A logged 0 `[WPOS]` lines and `shader_window=0` |
| Other flags identical | yes |
| Scratch files | rewritten by `tools/test_ppu_lift.py` during the suite (paths and a `VM_COH_RAW` stub, timestamp inside the suite run). Left untouched and uncommitted |
| 25 audit BLOCKs | `--staged` audits the full index. All 25 paths exist at base `542420e` and none is in `b282e26`, so none is new or part of the commit |
| WARP | `test_t171_track` 19/0, `test_shader_window` 0 failures, T145 35/35, list failed 0 |

## Frames at matching race clocks

| Clock | Arm A frame | Arm B frame |
|---|---|---|
| 0.7 s | `frame_007` (00:00.66) | `frame_006` (00:00.73) |
| 1.7 s | `frame_008` (00:01.69) | `frame_007` (00:01.76) |
| 3.0 s | `frame_009` (00:02.99) | `frame_008` (00:03.06) |
| 4.1 s | `frame_010` (00:04.03) | `frame_009` (00:04.09) |

Arm A also has 5.06 s and 6.09 s; arm B stops at 4.09 s. RSXI: A captured `f005564`, a full track frame; B captured `f005404`, which has no WPOS draw.
Visual results are in `TERRAIN_TRANSPARENCY_ROOT_CAUSE.md`, performance in `PERFORMANCE_IMPACT.md`.
