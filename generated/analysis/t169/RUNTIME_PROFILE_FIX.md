# T169: runtime profile fix

**`RSX_VISUAL_PROFILE` now takes effect on the game's D3D12 path, and a behavioural test proves it.** Commit: ps3recomp `774c81d` on `agent/t169-visual-fidelity-recovery`. Defaults are unchanged.

**Change:**
- `visual_profile_apply()` is the first call in `rsx_d3d12_backend_init`, before `fpf_init` and `init_d3d12`. It's gone from `d3d12_init`.
- Parsed once. An invalid value prints `[visual] RSX_VISUAL_PROFILE=<v> rejected: no switch changed`.
- An explicit switch beats the profile, because the profile only sets unset variables.
- `[visual] effective ...` prints right after `init_d3d12`.
- `RSX_VISUAL_ACTIVE=1` adds `[visual-active]` counters every 64 presents. It needs `RSX_FRAME_PERF` set, because the report sits in the frame-perf path.

**Tests:** `tools/test_t169_profile.py` builds `test_t169_profile_backend.c` against the real backend and calls the real init. 13 environment cases check pixels (depth red/green, sRGB 0x40 to about 0x88), the effective line and the rejection text. 0 failures.
- **Negative control VERIFIED:** with `visual_profile_apply()` commented out, the pixel and effective-line checks failed; the line was then restored.
- **Offline counters at F2 settings:** `depth_differs` 64, `xfer_srgb` 64, `srgb_rewrites` 1, `samp_binds` 1152; all 0 at default.
- **Scene gap:** it doesn't exercise window, feedback, mip, MRT or zeta. Their game evidence is the F2 counters.

## Switch audit (all read in `rsx_d3d12_backend.c`, once, into a static)

Each process has one configuration, since values are cached at first read. "Applied" is the F2 game counter, or the depth count in both arms.

| Switch | Read at | Behaviour changed | Reached in game | Dependency | PSO, shader or cache effect | Conflict |
|---|---|---|---|---|---|---|
| `RSX_DEPTH_STATE` | `ds_state_on` | Guest depth state per draw; `ds_bind_exact` keeps zeta bound | Yes, 1.33 M differing draws | None | `dr_depth_key` in PSO key | Exposes vehicle speckle and possibly `0xBF` |
| `RSX_COLOR_XFER` | `xfer_mode`, `dr_xfer_req` | Texture gamma; sRGB output | Yes, 724,864 sRGB draws | Bypassed for 32-bit exports and float surfaces; may refuse per program (0 refused) | PSO key and FP compile | None seen |
| `RSX_GUEST_SAMPLERS` | `gs_mode_from_env`, at `gs_init` | Guest sampler descriptors | Yes, 447,034 binds | Base bit needed; init failure turns it off | Root signature, sampler cache; no new shader | Mips rely on it for LOD |
| `RSX_TEX_MIPS` | `texmip_mode` | Uploads guest levels | Yes, 297 uploads | Samplers select LOD | Texture cache entry size | None seen |
| `RSX_ZETA_EXACT` | `zeta_exact_on` | Exact depth-to-colour shader | Yes, 7,220 draws | Zeta sampled as colour | Conversion pipeline only | None seen |
| `RSX_RT_WINDOW` | `rtwin_on` | Windowed RT sampling (`tex_win`, `rtwin_refresh`) | Yes, 13,099 draws | RT-sampling draw | Per-draw copy state | None seen |
| `RSX_RT_FEEDBACK` | `rt_feedback_on` | Copy when sampling the bound RT (`tex_fb`, `fb_refresh`) | Yes, 5,152 copies | RT-sampling draw | Extra copies | None seen |
| `RSX_MRT_STATE` | `mrt_state_on` | Guest per-MRT colour mask | Switch on; effect not counted | None | `dr_mrt_key` in colour-mask argument of `vp_get_fp_pso` | None seen |

**Note:** `RSX_DEPTH_STATE=1`, `RSX_COLOR_XFER=7` and the rest passed unmodified in D2/F2, without relying on the profile.
