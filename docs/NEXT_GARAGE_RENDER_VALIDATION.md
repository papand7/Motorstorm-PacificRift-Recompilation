# Next garage render validation run (RUN 2026-10-23: inconclusive, 210 s timeout)

**Question:** after the garage world is read, does the first cube-sampling fragment program translate, compile and get a pipeline? What does the loading screen's post-FX chain look like (baseline for the white-to-black capture)?

**This run will not capture the white-to-black transition.** In the 2026-10-21 run the first cube program was built right after the garage files, and the stop comes there. The relation of the ramp to that point is UNKNOWN: the old frames carry no log position. The transition needs the separate experiment B in `RSX_FRAME_CAPTURE_PLAN.md`.

## Inputs

| | |
|---|---|
| Exe | `build/motorstorm-int-render-8baed049/MotorStormPacificRiftRecomp.exe` (ps3recomp-int `dadfcaa` + private port; build log `generated/introskip/build_render.log`) |
| SHA256 | `8baed0493510ded2a04988dacb9df3a59b577d4d609d2e118ca1963f66dde9e4` |
| Previous exes kept | `motorstorm-int-garage-8bc4932e/`, `motorstorm-int-skip-2c1809c6/`, `motorstorm-int-fcw-f25903bc/` |
| Config | `generated/profile/motorstorm_milestones.render.proposed.json` (with `--config`; the live config is unchanged) |
| Audio | native (config env) |
| Thermal | off (optional) |

## Command (from the motorstorm root, one line)

```
py -3 tools/fast_startup.py --exe build\motorstorm-int-render-8baed049\MotorStormPacificRiftRecomp.exe --name garage-render --config generated/profile/motorstorm_milestones.render.proposed.json --target first_cubemap_shader_compile --allow-extended --stop-on-fatal --stop-on-line "\[shader\] fp=0x[0-9A-F]{8} ucode=0x[0-9A-F]{8} cube=0x[1-9A-Fa-f][0-9A-Fa-f]* rtfmt=\d+ nrt=\d+ stage=(pso_ready|pso_fail|compile_fail|translate_fail)\b" --stop-on-line "\[shader\] trace limit reached" --snapshot-cache --capture-rsx --capture-at garage_world_read_complete --capture-frames 3 --capture-stride 10 --capture-snap targets --env PS3_DEV_SKIP_INTRO=1 --env FS_CALLER=1 --env PS3_FSLOG_READS=5 --env RSX_SHADER_TRACE=1 --env RSX_SHADER_TRACE_MAX=4000 --env RSX_REPORT_TRACE=1 --env RSXI_MAX_MB=384 --env PS3_FC_WATCHDOG_MS=3000 --env RSX_HEARTBEAT_MS=1000 --env PS3_VIDEO_STATS=1
```

The wrapper adds:
- the 210 s cap and the 225 s hard deadline;
- the GPU-watchdog stop line;
- the process-tree kill and the image-name sweep;
- no retries.

It verifies the exe SHA256 into the manifest. `--snapshot-cache` copies and hash-verifies the FIOS cache before launch.

## Stops (first wins)

1. **The first cube program build outcome:** the first `[shader]` line with a non-zero cube mask and stage `pso_ready`, `pso_fail`, `compile_fail` or `translate_fail`.
   - It is a stop line, so it ends the run even if the RSXI capture is unfinished. The target alone would wait for the capture.
   - The `[CUBE]` patch line comes just before it and is recorded, not a stop.
2. `[shader] trace limit reached`, so a run that exhausts the 4,000-line budget does not go on untraced.
3. A fatal line (`--stop-on-fatal`, including `GcKernel::Present() Timeout` and `[D3D12] Present failed`) or the GPU watchdog.
4. 210 s, or a process exit or crash.

## Bounds

- Shader trace ≤ 4,000 lines (~400 KB).
- Report trace ≤ 64 lines.
- `[fsread]` one fd.
- RSXI: 3 frames, ≤ 32 snapshots per frame, ≤ 384 MB in total.
- One GPU wait per captured frame.

## Evidence to collect

- Milestone times: `garage_world_read_complete`, `garage_sky_read_complete`, `first_cubemap_shader_translated`, `first_cubemap_shader_compile` (stage), `first_shader_failure` (if any).
- Every `[shader]` stage line after the intro close, with counts of `fallback`, `compile_fail` and `pso_fail`.
- `[gcm-report] new` lines: which queries run after the intro (relevant to `WHITE_TO_BLACK_INVESTIGATION.md`).
- RSXI capture (if it completed): the post-FX programs and their constants on the loading screen, the luminance targets, the backbuffer.
- `[fs] open FAIL` lines after the world read, and the last archive member read.

## Pass / fail

- **Pass:** `first_cubemap_shader_compile` with stage `pso_ready`. The first garage-scene program translates, compiles and has a pipeline. Drawing is not shown.
- **Defect found:** stage `translate_fail`, `compile_fail` or `pso_fail`. The line names the program, its code hash and the first compiler error.
- **Inconclusive:** 210 s without a cube program; record the last stage reached (sky read, probes, reports).
- **Fail:** a fatal line, the watchdog or a crash. Record the last milestone. No retry.

## Ready?

Offline:
- exe built and hashed;
- config validated, and replayed against the garage-read run;
- the argv passes the wrapper's checks (without `--allow-extended` it is refused);
- suites as in the report.

**Run once** (authorized): `generated/runs/20261023-150148-garage-render/`.

## Result

Run `generated/runs/20261023-150148-garage-render/` (exe `8baed049…`, ps3recomp-int `dadfcaa`, intro skip, native audio, `--allow-extended`). Cache snapshot `generated/cache-snapshots/20261023-150148`.

- **VERIFIED termination:** wall-clock timeout, 210.1 s. No fatal line, no `[fc-watchdog]` report, no `Present failed`, no `GcKernel::Present() Timeout`; no leftover process.
- **VERIFIED:** `garage_sky_read_complete` at 95.98 s (all 205 blocks). It was read inside a sequential 64 KiB sweep of the PSARC (pos 0 → 671 MB at the stop) while FIOS `cache.dat` grew 29 MB → 672 MB (FIOS caching the archive to `dev_hdd1`). Whether the game requested the sky or the sweep covered it is UNKNOWN.
- **VERIFIED:** no cube program within 210 s: 0 `[CUBE]`, 0 `cube≠0` `[shader]` lines. 13 programs translated, compiled and got a pipeline; 11 bound by draws; 0 failures, 0 fallbacks. The last new program (`0x02538941`) came during the intro.
- **VERIFIED:** guest presents stop at frame 1733 (~45.8 s); no `[rsx-hb]` after that, while the frame-clock thread kept making progress (no watchdog report). SPU tasksets (images `406081863`, `341580667`, `308733018`, `491898574`) and FIOS reads continue to the end. Loading did not reach shader creation for the garage; whether the frontend is blocked or merely slow (HDD cache fill at ~4–6 MB/s) is UNKNOWN.
- **VERIFIED queries:** 4 distinct ZPASS reports, all during boot: offsets `0x14110`, `0x14120`, `0x14130`, `0x14100`, `dma=0xFEED0001`, value `0xFFFF` (not measured). None new after the intro.
- **VERIFIED capture (frames 1361/1371/1381, garage loading artwork):** 3 draws each, straight to the backbuffer (`fp 0x02537E81` ×2, `0x02538941`), blend enabled (`0x0122418B`), 0 clears, no post-FX chain. Program, constants and texture checksums are identical across the three frames, yet the backbuffer brightens: R/G/B mean 150.4/122.9/61.8 → 156.0/128.2/66.9 → 160.5/132.6/71.4, white pixels 3.9 → 5.7 %.
- **HYPOTHESIS (new lead for white-to-black):** the brightening depends on the destination, not the inputs: blending onto a backbuffer that is never cleared accumulates. This weakens the exposure/luminance hypothesis for the loading screen (no luminance pass runs there). Next: decode `blend_key 0x0122418B` and compare what the guest display buffer at RT offset 0 holds against the D3D12 backbuffer (offline first).
