# T171: game capture request

**Requested, not authorized. No launch has been made.**

| Item | Request |
|---|---|
| Exe | `build/motorstorm-t171/MotorStormPacificRiftRecomp.exe` |
| SHA-256 | `4450EA1FA8D31BCFD6F24CA9B6018459331DAD96D6E4D14989B9511D6D12A8BE` |
| Source | ps3recomp `b282e26` (tracked sources as built), port-t161 |
| Launches | **2**, the same exe; no retries |
| Venue and location | the beach route used by T169's VA/VB/VC arms, on that same route's start stretch |
| Tyre-track event | tracks visible near the camera on the ground, race clock about 02-07 s, the same window as VB `frame_006` (00:06.66) |
| Runtime cap | 205 s game cap each (runner hard kill at 203 s) |
| Capture duration | until race entry + 45 s, then stop |
| Watchdog | 4 s `GcKernel::Present()` unchanged |
| Session | local and visible, not minimized and not over remote desktop (these distort timing and SPURS) |

## Environment

Both arms use T169 arm B from `t169/tools/make_runner_t169.py` (`ENV_LEAN`, `TEXRES`, `D3D12_DBG=1`, `RSX_COLOR_XFER=7`, `RSX_GUEST_SAMPLERS=15`, `RSX_TEX_MIPS=1`, `RSX_ZETA_EXACT=1`, `RSX_RT_WINDOW=1`, `RSX_RT_FEEDBACK=1`, `RSX_DEPTH_STATE=0`, `RSX_MRT_STATE=1`, `RSX_RT_REINTERP=0`) with its lean RSXI (`RSXI=1`, `RSXI_COUNT=1`, `RSXI_STRIDE=1`, `RSXI_MINDRAWS=200`, `RSXI_SNAP=passes`, `RSXI_MAX_EVENTS=0`, `RSXI_MAX_SNAPS=64`, `RSXI_VP_CONSTS=0`, `RSXI_UNITS=0`, `RSXI_GEOM=0`, `RSXI_RTS=01650000,01DD0000,00750000,022D0000`), plus `CELLMARK_DUMP_EVERY=64`.

- **Arm 1 (fix):** `RSX_SHADER_WINDOW` unset.
- **Arm 2 (control):** `RSX_SHADER_WINDOW=0`.

A time-triggered RSXI frame can differ between runs, so matched comparison relies on CELLMARK frames at matching clock; RSXI is supporting evidence only.

## Stop conditions

Stop and report, without retrying, on: the watchdog firing; a crash; `[visual] effective` not showing the expected `shader_window` value and arm B's other values; `[WPOS]` remap lines absent in arm 1; a pipeline failure on any WPOS program; a SPURS collapse flagged by the run guard; or race entry + 45 s reached.

## Expected evidence

1. `[visual] effective ... shader_window=1` (arm 1) and `=0` (arm 2).
2. `[WPOS]` remaps for `0x022CD841` in arm 1, no new debug-layer messages against arm 2.
3. Arm 1: no sky, trees or vehicle pieces in the ground at the tracks; arm 2 still shows them.
4. Blocky bottom patches gone, or isolated to a named draw if they remain.
5. Shoreline and vehicles no worse than arm 2; no speckle.
6. No material frame-time difference (`RSX_PRESENT_INTERVAL`, local session).

Captures stay private.
