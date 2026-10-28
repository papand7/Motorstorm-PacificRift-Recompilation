# Next render diagnostic run (PREPARED, NOT RUN; needs separate authorization)

**Questions:**
1. When presents stop after the loading-screen thread ends, did the guest stop flipping, or did the runtime swallow the flips?
2. What drives the loading-screen gain?

Background:
- `PRESENTATION_STALL_ANALYSIS.md`: the boundary is about 45.8 s, at `AsyncRenderThread` exit.
- `LOADING_SCREEN_FRAME_ACCUMULATION.md`: the brightening is a pre-store gain, not accumulation.
- A first-cube-shader stop alone is not enough: in the last run presentation stopped, and no shader was built, 164 s before the cap.

## Inputs

| | |
|---|---|
| Exe | `build/motorstorm-int-present-be870473/MotorStormPacificRiftRecomp.exe` (+ map; ps3recomp-int `c874771` + private port; log `generated/introskip/build_present.log`) |
| SHA256 | `be870473cc6070510838e0c6bfe11ad4fa1405555c33137c7a4fd2cbbe2749d9` |
| Previous exes kept | `motorstorm-int-render-8baed049/`, `motorstorm-int-garage-8bc4932e/`, `motorstorm-int-skip-2c1809c6/`, `motorstorm-int-fcw-f25903bc/` |
| Config | `generated/profile/motorstorm_milestones.render.proposed.json` (`--config`; the live config is unchanged) |
| Audio / thermal | native / off |
| FIOS cache | the live cache is at 672 MB after the last run. **Decision for the user:** run on it as it is (the runner snapshots it first), or restore `generated/cache-snapshots/20261023-150148` (29 MB, the last run's starting state) beforehand, for a like-for-like repeat. |

## Command (from the motorstorm root, one line)

```
py -3 tools/fast_startup.py --exe build\motorstorm-int-present-be870473\MotorStormPacificRiftRecomp.exe --name present-stall --config generated/profile/motorstorm_milestones.render.proposed.json --target first_cubemap_shader_compile --allow-extended --stop-on-fatal --stop-on-line "\[present-progress\] no present for ([6-9]\d{3}|\d{5,}) ms" --stop-on-line "\[shader\] fp=0x[0-9A-F]{8} ucode=0x[0-9A-F]{8} cube=0x[1-9A-Fa-f][0-9A-Fa-f]* rtfmt=\d+ nrt=\d+ stage=(pso_ready|pso_fail|compile_fail|translate_fail)\b" --stop-on-line "\[shader\] trace limit reached" --snapshot-cache --capture-rsx --capture-at garage_world_read_complete --capture-frames 3 --capture-stride 10 --capture-snap targets --env PS3_DEV_SKIP_INTRO=1 --env FS_CALLER=1 --env PS3_FSLOG_READS=5 --env RSX_SHADER_TRACE=1 --env RSX_SHADER_TRACE_MAX=4000 --env RSX_REPORT_TRACE=1 --env RSXI_MAX_MB=384 --env RSXI_VP_CONSTS=64 --env BLENDDBG=1 --env PS3_PRESENT_PROGRESS_MS=3000 --env PS3_PRESENT_PROGRESS_MAX=8 --env PS3_FC_WATCHDOG_MS=3000 --env RSX_HEARTBEAT_MS=1000 --env PS3_VIDEO_STATS=1
```

The wrapper adds the 210 s cap, the 225 s hard deadline, the GPU-watchdog stop line, the tree kill and image sweep, and no retries. It also records the exe SHA256 and snapshots the cache. Checked offline:
- without `--allow-extended` the argv is refused;
- with it, the timeout is 210;
- the stop regex matches 6000 and 12000 ms reports, and does not match a 3000 ms report or a "presents resumed" line.

## Stops (first wins)

1. **A presentation stall of at least 6 s**: the second `[present-progress]` report of a stall. The 3 s report before it is kept as the first window.
   - Expected near 52 s if the stall repeats at about 46 s.
   - A transient load pause of under 6 s does not stop the run.
2. **The first cube-map program build outcome** (`pso_ready`, `pso_fail`, `compile_fail`, `translate_fail`): reached only if replays continue.
3. `[shader] trace limit reached`.
4. A fatal line, the GPU watchdog, 210 s, or a process exit.

## Bounds

| Output | Limit |
|---|---|
| `[present-progress]` | ≤ 8 lines |
| `[BLEND]` | ≤ 64 lines |
| `[gcm-report]` | ≤ 64 lines |
| `[shader]` | ≤ 4,000 lines |
| RSXI | 3 frames, ≤ 384 MB, ≤ 64 VP constants per draw, one HLSL file per vertex and fragment program |
| `[fsread]` | one fd |

## What each result means

| Observation | Conclusion |
|---|---|
| First report: `flips=0`, `drain_moves>0` | the guest stopped flipping (case A or D); next, trace the thread that joined `AsyncRenderThread` |
| `flips>0`, `gate.clear_mode>0`, `replays=0` | the runtime swallowed guest flips (case C); `gate.no_display_draw` and `batch` (`FULL`) say why; the fix candidate is the frame-boundary policy |
| `flips>0`, `replays>0`, `presents=0` | replays without display content |
| Presents continue and a cube program builds | the stall was transient or cache-dependent; record the build outcome |
| RSXI `vp_consts` on ops 0–2 differ between frames 10 apart | the guest drives the gain (a fade parameter) |
| Constants identical, but the gain still grows | look at the vertex data and the vertex-program HLSL (`shaders/vp_*.hlsl`) |

**Not answered by this run:**
- whether the GPU waits on a fence: nothing is submitted while replays are absent;
- the vertex attribute values.
