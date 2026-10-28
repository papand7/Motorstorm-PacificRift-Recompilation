# Next validation run: does the garage scene reach the backbuffer with the guest depth state honoured? (PREPARED, NOT RUN; needs separate authorization)

Previous run: `20261023-224835-garage-raster` (`STATUS.md`); its plan is in `generated/introskip/NEXT_PRESENTATION_VALIDATION.raster.md`.

**Questions:**
1. Is op 606's target `0x02206100` non-zero after the op (`nonzero_fraction` > 0; alpha ≈ 1 near the centre)?
2. Is `0x022B5D80`, at the end of the blur chain, non-zero?
3. Does op 613's backbuffer show the garage scene under the UI?
4. Are there new D3D12 errors, or new pipeline-cache misses beyond one extra pipeline per depth-off program?

| | |
|---|---|
| Revision | ps3recomp-int `f77ef52` |
| Exe | `build/motorstorm-int-depth-884f2629/MotorStormPacificRiftRecomp.exe` (+ map; log `generated/introskip/build_depth.log`) |
| SHA256 | `884f2629bce8cb97c4e7ef464684e51fbac6a4035fa071bf84294241ffd0d716` |
| Config | `generated/profile/motorstorm_milestones.zeta.proposed.json` (unchanged) |

## Command (motorstorm root; also `generated/introskip/depth_cmd.txt`)

Changes from `raster_cmd.txt`: only the exe path and `--name garage-depth`.

Wrapper limits are unchanged: 210 s cap, 225 s tree kill, GPU watchdog stop, no retries.
