# T162 — game validation plan (D, A1, B1, A2, B2; conditionally authorised, gate not met, no launch yet: `FINAL_VALIDATION.md`)

Both steps use one exe built from ps3recomp `agent/t162-gpu-vertex-pipeline`. The recipe is the T161 arm-x recipe, with this tree in place of `ps3recomp-t161`:
- same port (`port-t161`), PPU staging lift, Wws AOT, Havok `--chain-chunks`;
- every new switch defaults off.

The tree is independent of the texture-residency branch: it touches no texture-residency code, worktree, configuration or exe.
- Base: the T161 arm-C configuration, the current known-good integrated baseline.
- To combine with texture residency later, rebase onto `agent/perf-next-tex-residency` and repeat step 2. The heavy scene only becomes vertex-bound after the texture fix.

## Step 1: one diagnostic launch (counters only)

**Goal:** the measurements no existing log has.
- the compact/fat/GPU share per draw class;
- referenced index ranges and raw-span bytes per draw;
- in-game vertex-format signatures (are there dividers, MAIN arrays across IO pages, sparse draws?);
- the GPU-fetch fallback reasons.

**Settings:**
- arm C environment + `RSX_VTX_STATS=1000`;
- `RSX_GPU_VERTEX_FETCH` unset (counters describe the CPU path the game takes today);
- the same pinned route, fast pacing, race stop at entry + 150 s, 195 s game / 210 s host caps, fresh HDD copy.

**Read-only:** the counters read the RSX state and index arrays and change no draw. Their cost is one index pre-scan per indexed draw (min/max), which inflates `expand_ms`. So this run is for counts, not for timing.

**Pass criteria:** route and race reached; the `[vtx-stats]` lines cover the light and the heavy scene.

## Step 2: A/B, A → B → A → B (4 sequential launches, no retries)

**Arms:**
- **A:** the T162 exe, arm C environment, `RSX_GPU_VERTEX_FETCH` unset;
- **B:** the same exe and settings + `RSX_GPU_VERTEX_FETCH=1`.

Same race-frame ranges: light frames 40–499, heavy frames 600 to the last frame every run reached (T161 `bench_t161.py` / `cd_t161.py`).

**Collect:**
- FPS, 1 % low, frame time avg / p50 / p95 / p99 per scene;
- `expand_ms` (draw callbacks), `record_ms` (textures, PSO, commands), `flush_ms`, `wall_ms`;
- GPU time (`RSX_GPU_PROF=60` in both arms);
- upload bytes: the `[gvf]` ring bytes in B, the vertex-buffer units in A;
- Havok wait `0x30B710`, Wws spin `0x50C818`, RSX throttle `0x72E1E0` (`phase_sites_t154.py`);
- CPU cores per phase (`performance.json`);
- the `[gvf]` fallback reasons, `flushes` and `nopso`;
- the 12 CELLMARK dumps per run.

**Pass criteria:**
1. route identical and race reached in all 4 runs; no new error categories; 0 FIFO resyncs;
2. draw counts equal to A's;
3. **`lost` = 0, and `nopso` = `cpu_drawn`**; a nonzero `nopso` now means fallback draws, not missing ones;
4. the CELLMARK dumps visually equivalent to A's (dumps are not run-to-run deterministic; compare by eye and by the stable overlays);
5. light-scene FPS within the A–A spread (the light scene is PPU-bound, so no gain is expected);
6. heavy scene: `expand_ms` lower by at least 30 %, frame time not worse, GPU time per pass not higher than A + 1 ms.

**Expected (HYPOTHESIS):**
- `expand_ms` −30 to −40 % in both scenes. This is the synthetic race shape (§7 of the implementation report), if the in-game spans are as compact as the synthetic ones; step 1 settles that.
- On today's baseline the heavy frame is texture-bound, so FPS gains stay small (about 15–20 ms of a 270–300 ms frame).
- With texture residency in place, about 20–25 ms of about 130 ms: **+15–20 % heavy FPS**.

**Safety:**
- pinned exe hash checked before each launch;
- fresh HDD copy per launch;
- GPU watchdog;
- caps as T161;
- the sequence stops at the first rc ≠ 0.
