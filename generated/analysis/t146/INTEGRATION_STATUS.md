# T146 — integration status (concise)

Branch `integration/t146-unified-runtime`, worktree `ps3recomp-t146-integration`, base `07b453f` (T141 tip).
Full detail: `UNIFIED_INTEGRATION_REPORT.md`.
Head `80fe5de` (73 commits over base). Exe `build/motorstorm-t146/MotorStormPacificRiftRecomp.exe`, SHA-256 `ef0d32c8…4682`, built, **not launched**.
Offline: suite 126 PASS / 43 SKIP, 0 new failures (2 pre-existing); real-backend harnesses T137/T141/T142/T144/T145 identical to recorded; T143 on/off identity holds. Switches: `RUNTIME_SWITCHES.md`. Presets: `presets/`.

"Runtime-unverified" = no game run of the *integrated* exe (none was authorised). Several features were
VERIFIED in game on their own branch; that is noted.

| Task | Feature | Status | Integrated as |
|---|---|---|---|
| T102 | VP convert-once, RSX_FRAME_PERF | **Integrated and tested** (already in base as `4d7e84c`/`470785e`) | base |
| T104/T106 | five-lane WWS safety, race fixes, guest maxContention (default on) | Integrated, runtime-unverified (VERIFIED +57% on T109 line) | merge `752a3c5` |
| T109 | WWS AOT runtime, READY_LEVEL, SC_WAIT | Integrated and tested offline; AOT exe variant **not built** (needs `port-t106aot`) | merge `752a3c5` |
| T110 | guest samplers, colour transfer, attr0, rtpool | Integrated and tested (in base) | base |
| T113 | RT write-back, FP span (default on) | Integrated and tested (in base; runtime VERIFIED) | base |
| T115 | mip chains | Integrated and tested (in base, `4a74174`) | base |
| T115B | exact texture cache | Integrated and tested | `4c4ee7d` |
| T116 | shader/PSO cache | Integrated and tested (T146 key fix) | `2f8f121`, `cf70862` |
| T117 | FP refuse-without-END | Integrated and tested; 16 KiB window **superseded** by T113 FP span | `92b5745` |
| T118 | audio initial port gain, SPU exit diag | Integrated and tested (discovered; not in brief list) | `1aeb09e`, `80fe5de` |
| T119 | compact VP, VS memo, getenv once, draw split | Integrated and tested | `9796324`…`1ba4e71` |
| T120 | RT window, depth/stencil state | Integrated and tested (in base) | base |
| T121 | PS3_USLEEP_SPIN=2 | Integrated and tested | merge `1cb4b5e` |
| T122 | D3D12 submission/sync, tex-snapshot epoch | Integrated and tested (runtime VERIFIED on own branch) | merge `b06e733` |
| T123 | SPU FP cache (default on), kick wake | Integrated and tested | merge `752a3c5` |
| T123B | event-driven SPURS coordinator | Integrated and tested | merge `752a3c5` |
| T131 | VMX alias test, SPU overlay evidence tool | Integrated and tested | `82c1480`, `d5edebc` |
| T132 | atomic flip-pending | Integrated and tested | `482aa13` |
| T132B | PS3_SIM_PACE (opt-in, off) | Integrated and tested (keep off: physics pacing) | `63750dd` |
| T133 | FP precision, RSXI aa_ctl | Integrated and tested (in base) | base |
| T134 | critical-path trace, RSX_RECORD span | Integrated and tested | merge `1cb4b5e` |
| T136 | SSE4.1 SPU float/fi/cwd | Integrated and tested | `0af0496`…`28691bf` |
| T137 | RSX MSAA | Integrated and tested (in base) | base |
| T140 | PPU store fast path (default on), RESV_STORE, RAW_STORE_COH | Integrated and tested; RAW_STORE_COH needs a re-lift (not in exe) | merge `1cb4b5e` |
| T141 | blend/MRT/feedback | Integrated and tested (base) | base |
| T142 | fetched-unit RT windows | Integrated and tested | `deb9deb`, `8864547` |
| T143 | SRV reuse, bind dedup, GPU profile | Integrated and tested (wrappers merged with T122) | `a0ed1c5`, `618981c` |
| T144 (RSX) | RSX_STENCIL_EXACT | Integrated and tested | `345c083`, `e42e2c0` |
| T144 (SPURS) | PS3_SPURS_LANE_HANDOFF | **Pending** — uncommitted in `ps3recomp-t144s` (files modified 18:03–18:09 today; possibly active); synthetic net regression in default-like arms | — |
| T145 | SET_SHADER_WINDOW WPOS | Integrated and tested (T146 key fix) | `dd04a88`…`bde0dd4` |
| T107 | colour-transfer report | Integrated (in base) | base |
| T111 | offline mod framework (tools only) | **Excluded** — offline tooling, not runtime; no dependency | — |
| misc-hle-features | cellFs real delete, savedata autosave, cellFont NIDs | **Pending** — host file deletion semantics need their own review | — |
| T147 | parallel RSX-visuals integration (`integration/t147-unified-rsx-visuals` @ `d76e08e`, appeared during T146, build dir active) | **Not merged** (another agent's active work). Its commits are a subset of T146's RSX stage (T142, T145, T115B, T144 RSX, T117 decoder half) and it resolved T113×T117 the same way (`test_fp_span` expects refusal) — independent cross-check | — |
