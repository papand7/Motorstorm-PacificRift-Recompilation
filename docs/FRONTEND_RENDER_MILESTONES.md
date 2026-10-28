# Frontend and render milestones (proposed, 2026-10-23)

Config: `generated/profile/motorstorm_milestones.render.proposed.json` (v3). It is **not live**; pass it with `--config`. The live `tools/motorstorm_milestones.json` is unchanged.

Test: `generated/profile/test_render_milestones.py`, 14/14 PASS. It covers:
- a replay of the real garage-read run (the same milestones fire; the partly read sky does **not** complete);
- synthetic `[shader]`/`[CUBE]` lines: order, no false positives from cube programs before the intro close, from `cube=0x0` programs or from `[CUBE] unit=` texture lines;
- the compile-failure path;
- the run's stop regex;
- `requires_env`.

| # | Milestone | Detection | Evidence quality | Status |
|---|---|---|---|---|
| 1 | `garage_sky_read_complete` | `span_read complete` over `/env/Track0a_Garage_Sky1_driver.rpk` [244,169,081, +8,650,343) | bytes read, not parsed | implemented |
| 2 | `garage_resource_init_started` | — | no traced guest function marks rpk parsing | **unresolved** (`supported: false`) |
| 3a | `first_cubemap_shader_translated` | `[CUBE] fp=` (replaces `garage_rendering_started`) | the HLSL was patched, **before** the compile | implemented |
| 3b | `first_cubemap_shader_compile` | `[shader] … cube≠0 … stage=pso_ready\|pso_fail\|compile_fail\|translate_fail` | the build outcome | implemented (needs `RSX_SHADER_TRACE=1`) |
| 3c | `first_cubemap_pipeline_ready` | `… stage=pso_ready` | a pipeline exists | implemented |
| 4 | `first_cubemap_draw` (in place of `first_garage_draw`) | `… cube≠0 … stage=bound` | a replayed draw set the pipeline. "Garage" is INFERRED (no cube program before the garage load); it does not show the draw reached a present. | implemented |
| — | `first_shader_failure` | any `translate_fail\|compile_fail\|pso_fail\|fallback` | informational, not a stop | implemented |
| 5 | `first_garage_present` | — | a present cannot be tied to a garage draw from the log | **unresolved**; use RSXI |
| 6 | `main_menu_rendered` | — | `mainmenu.gui` is read in the boot prefetch (garage-read run stderr 2441, before the intro), so a read proves nothing | **unresolved** |
| 7 | `main_menu_accepts_input` | — | needs the menu; pad polling alone is not consumption | **unresolved** |

**Fatal patterns:** the v2 patterns plus `\[D3D12\] Present failed`.

**Not used:**
- the heartbeat as "garage present": it counts draw frames, not content;
- `mainmenu.gui` reads as a menu signal.

**Evidence needed for the unresolved milestones:**
- **Parsing / initialisation:** trace the guest code that consumes a completed FIOS read of `track_garage.rpk`. Find it from the FIOS completion callback with a bounded `PS3_FTRACE` in a separately authorised run, then hook it.
- **Menu rendered:** an RSXI capture identifying the menu's own fragment programs or textures. That becomes an `RSXI_AFTER_FP`-style milestone.
- **Input accepted:** a guest state change after a pad press in the menu, observed in a capture.
