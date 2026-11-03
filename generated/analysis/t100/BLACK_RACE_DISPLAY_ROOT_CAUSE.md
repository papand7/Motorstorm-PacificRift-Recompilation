# T100: black race display, root-cause investigation (2026-10-27)

**Result:** T98's 35 black images **do not show that the race display is black**.
- The dump samples every render pass. A non-presenting pass dumps exact black by construction, and T98's dump spacing locks onto a fixed pass parity.
- No backend defect producing a black presented image is proven offline.
- **The earliest failing stage is the T98 measurement itself** (VERIFIED mechanism; how many of the 35 it affected is PARTIAL).
- I added two opt-in diagnostics (`729caed`) and a launch configuration that separates "black display" from "black sample".

**The race is not declared visible.**

## Ownership
- **Sessions:** `ListAgents` shows one peer, motorstorm01-21 (T99, finished, idle). No T100 worktree, branch or report existed.
- **Worktree:** `ps3recomp-t100`, branch `agent/t100-black-race-display`, from T96I `95a906d` (the T98 exe's source).
- No shared worktree or earlier artifact was modified.

## 1. Present path (VERIFIED by code reading, `rsx_d3d12_backend.c` at `95a906d`)

| Entry | Runs `render_frame` when | Calls `Present` when |
|---|---|---|
| `d3d12_clear`, display colour clear (`:7970`–`8044`) | `ps3_pg_display_clear` says boundary | always for that replay (`s_present_this_frame` = 1) |
| `d3d12_present`, guest flip (`:7853`) | the batch has a display record, is empty, or `flushed_display` | same |
| `rsx_d3d12_backend_present`, ticker (`:9805`) | `has_display` or draws > 0 | only with `has_display` (`:9906`) |
| `vp_flush`, early replay (`:8451`) | the VP buffer or the records are full | **never** (`s_present_this_frame = 0`) |

- **Display draw:** a record with `rt_off == 0`. `current_rt_off` returns 0 when the colour offset is a registered display buffer: `0x10000` or `0x394000` in T98 (`SetDisplayBuffer` ids 0/1).
- **Race frames contain one (VERIFIED, T94 flip 2112):** a display draw, `count=4`, to `0x00394000`.
- **The host clear colour is the guest's last display clear colour** (`memcpy(s_d3d.clear_color, cc)`, `:7970`). In T98 it is `0x00000000`. Every replay that does not keep targets clears the backbuffer to exact (0,0,0) at entry (`:6693`).
- **The frame dump (`:7472`–`7520`) runs on every `render_frame`** and copies `render_targets[fi]` after `composite_present`, before `Present`. A pass with no display record therefore dumps exact black, whatever the screen shows.
- **Stage distinction:**
  - **Guest frame:** a `0x72E1E0` return (368 in T98).
  - **Render pass:** a `render_frame` call (`[rsx-hb] frames`: 849 from 200.9 s to 298.5 s, 2.3 per guest frame).
  - **Early replay:** 256–511 in T98.
  - **Host Present:** not counted in T98; `PS3_PRESENT_DIAG_MS` was off.
  - **Captured image:** the backbuffer of *any* pass with ≥ 200 draws.

### Why T98's dumps cannot show a black display
- **Re-arm period (VERIFIED by code):** `CELLMARK_DUMP_EVERY=N` re-arms the skip counter to N−1, and the counter is decremented and tested in the same pass. The dump period is therefore **N−1 = 24 qualifying passes**.
- **Consistency with T98 (VERIFIED):**
  - 849 passes / 24 ≈ 35, which equals the 35 dumps;
  - 24 passes / 8.6 passes per second ≈ 2.8 s, which equals the dump spacing.
- **Parity lock (VERIFIED by test):** `frame_000` (202.5 s) is the first race pass, an early replay (`frame=2132`, 966 records, no Present). With a strict early-replay-then-present pattern, an even period stays on early replays. The model in `test_race_display_diag.c` gives 31 of 31 dumps on early replays.
- **PARTIAL:** T98 averaged 2.3 passes per guest frame, so the pattern is not strictly alternating. How many of the 35 were presenting passes is unknown. A black presented image is therefore **not excluded**, only unproven.

## 2. Producer → display chain
- **Source:** RSXI events of the garage (2026-10-24/25, VERIFIED there).
- **Same chain in the race (VERIFIED):** T87B's first race frame, `f004062`, has the same pool addresses: `0x02195900`…`0x022C1600` luminance, `0x01DD0000`, `0x022D0000`, `0x022B5D80`, `0x00750000`, `0x01650000`.

| Stage | Guest surface | Host | Risk for exact black |
|---|---|---|---|
| shadow / depth-only passes | zeta `0x0B030000` 1024×2048, `0x00ED0000` 1280×720 | zeta pool, plus RGBA8 colour aliases (slots 17/18, T87B) | T101: depth-only draws dropped. They cannot zero the HUD (HYPOTHESIS) |
| scene | `0x00750000`, MRT1 `0x01650000` (2× AA, pitch 10240) | RGBA8 1280×720 (AA layout ignored, known) | dark in the garage, not black |
| scene copy / half-res | `0x01DD0000` (op 602), `0x022D0000` (op 604) | RGBA8 | — |
| luminance → exposure | `0x02195900` → … → `0x022C1600` 10×5 → `0x06A1E400` 16×16 FP16 | read by the PPU (`func_004C3778`) only through `RSX_RT_READBACK` | **off in T98**. The PPU then reads 0, so `c33` sits at its maximum (35.3): dark in the garage, not black (PARTIAL by analogy) |
| bloom / vignette | `0x02206100` … `0x022B5D80` 80×45 FP16 | FP16 | the composite multiplies by its alpha (garage op 613). If the alpha is 0, the image is black (HYPOTHESIS, unmeasured in the race) |
| final composite | fp `0x02193941` → display `0x10000`/`0x394000` | `rt_off = 0`: swap-chain `render_targets[fi]` | — |
| Present | `Present(1,0)` (`:7704`) | only in a presenting replay | count unknown in T98 |

## 3. T101 pool hazard
- **Pressure:** T87B's first race frame had **25 of 32** slots allocated by op 316 of 974 (VERIFIED, RSXI `rt_pool` + `rt_life`).
- **No overflow within a replay:** T98 has no `render-target pool full` line (VERIFIED).
- **Evictions:** silent outside RSXI, so whether a live surface was evicted across an early replay is **unknown**.
- **GPU lifetime:** eviction calls `wait_for_gpu()` before `Release` (`:3833`), so GPU lifetime is safe.
- **The T101 one-line change is NOT applied.** No runtime eviction is proven. Keeping `used` across a replay also brings forward "pool full: draws skipped", a different loss. `RTPOOL_LOG` now measures this.

## 4. Depth surfaces
- **`0x00ED0000` is read as a texture** (`read as A8R8G8B8: converted`, 4 lines in T98).
- **No consumer recorded:** the garage composite inputs (op 613) include neither `0x00ED0000` nor `0x0B030000`, and no race consumer is recorded. A depth-fed post pass (fog/DOF) cannot zero the HUD and every pixel on its own. Not proven to feed the final image.

## 5. Source changes: `729caed` (on `95a906d`; not merged or pushed)
- **New header** `include/ps3emu/race_display_diag.h`, plus 33 lines in `rsx_d3d12_backend.c`. Both diagnostics default off; rendering is unchanged.
- **`CELLMARK_DUMP_PRESENT_ONLY=1`:** the dump and its `EVERY` counter consider only replays that will call Present.
- **`RTPOOL_LOG=<n>`:** at most n `[rtpool] evict|resize` lines (capped at 4096) with cumulative counts. `live=1` means the surface was used earlier in the same guest frame (tracked by `gf_used`, reset only when `keep_targets == 0`).

## Offline results
- **New test** `test_race_display_diag.c`: 16 checks, 0 failed. Pins `tools/test_race_display_diag.py`: 10/10.
- **Renderer suite on `ps3recomp-t100`:** 31 PASS / 9 SKIP / 0 FAIL, identical to T96I (`logs/suite.txt`).
- **T101 pins on this tree:** 7/7 after `5288949` (the `used = 0` reset line is restored verbatim; `gf_used` is reset in a separate `keep_targets`-guarded loop). Before that fix: 6/7.
- **T103 note (peer, HYPOTHESIS for the race):** the guest-FP root signature uses static samplers and ignores the guest's TEXTURE_FILTER/ADDRESS/CONTROL0 settings. This can change the image but cannot by itself make it exact black.
- **TU compile** of `rsx_d3d12_backend.c` with the exact build flags: rc=0 (`logs/tu/`). 11 new warnings, all in categories already present (2,657 at baseline).
- **Public audit** (`--tree` of the changed files): passed.
- **Logs:** `t100/logs/`. **Runners:** `t100/tools/run_t100_tests.cmd`, `run_suite_t100.cmd`, `tu_t100.cmd`.

## 6. Runtime check (needs authorization)

**Option A, no build (T96I exe `3fd97ab6…`):** the T98 runner and environment, with these changes:
- `CELLMARK_DUMP=12 CELLMARK_DUMP_EVERY=24 CELLMARK_DUMP_MINDRAWS=200`: a period of 23 passes, which alternates the pass parity;
- `PS3_PRESENT_DIAG_MS=5000 PS3_PRESENT_DIAG_MAX=64`;
- a 300 s cap.

**Option B (preferred; one diagnostic build of `729caed`, then one launch):** the T98 runner and environment plus:
- `CELLMARK_DUMP=12 CELLMARK_DUMP_EVERY=8 CELLMARK_DUMP_MINDRAWS=200 CELLMARK_DUMP_PRESENT_ONLY=1`;
- `PS3_PRESENT_DIAG_MS=5000 PS3_PRESENT_DIAG_MAX=64`;
- `RTPOOL_LOG=64`;
- optionally one RSXI presenting-frame capture: `RSXI_EVENT=present RSXI_PRESENTED=1 RSXI_MINDRAWS=200 RSXI_AFTER_MS=205000 RSXI_COUNT=2 RSXI_STRIDE=20 RSXI_SNAP=end RSXI_RTS=01DD0000,00750000,022D0000,022B5D80,06A1E400,022C1600,00ED0000,01650000` (plus the runner's RSXI dir). It adds about 2 s per captured frame.

**Unchanged in both options:** no `RSX_RT_READBACK`, no `TEX_SAVE`, no continuous RSXI.

### Pass/fail criteria

| Observation | Meaning |
|---|---|
| `[present_diag]` `ok` count rises after 201 s | real Presents happen (Q1) |
| `ok` flat while `replays` rise | no race Present: the stage-1 failure is in the present gate |
| presenting dumps after race entry show non-black race content | **race visible** (then confirm by eye); T98 was a sampling artifact |
| presenting dumps exactly 0 | real black display. The RSXI `end` snapshots then place the failure: `0x01DD0000` non-black means composition/bloom-alpha/exposure; `0x01DD0000` black means scene |
| `[rtpool] … live=1` on a composite input (table above) | the T101 eviction hazard is real: apply its fix with a regression test |
| Option A: dumps alternate black / non-black | same conclusion as presenting dumps non-black, without a build |

## Remaining uncertainties
- How many T98 dumps were presenting passes.
- Bloom alpha and exposure in the race.
- Whether live evictions occur.
- Whether depth-only drops matter visually (T101 class B).
