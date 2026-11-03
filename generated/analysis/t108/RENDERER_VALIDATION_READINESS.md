# T108: Renderer validation readiness (2026-10-27, offline; no build, no launch)

- **Worktree:** `ps3recomp-t108`, branch `agent/t108-renderer-validation`, head **`6b1a7e4`**. Not merged or pushed.
- **Peer worktrees:** T100, T102, T103, T104, T105 and T107 are clean and at their recorded heads.
- **Not included:** T104's SPU code is absent (`PS3_SPURS_GUEST_MAXCONT` appears nowhere in the tree).

## 1. Integrated commits

| Commit | Content | Origin |
|---|---|---|
| `36d0fb7` | T105 base: T100 `5288949` + T99 `db2aa90` + T102 `1e5d534` + T103 `c2e9eec`/`26f262e` + `RACE_PRESENT_PROBE` | T105 |
| `df00fa9` | `SET_SHADER_PACKER` tracking, `rsx_color_xfer.h`, `RSX_XFER_LOG`, RSXI colour-transfer fields | cherry-pick `-x` of T107 `ec5cdb3` |
| `71a97b1` | T101 tests brought in-tree; early-replay pin rewritten (§3) | T108 |
| `6b1a7e4` | Probe: RGBA32F targets classified; format-coverage pin | T108 |

**Ancestry (VERIFIED):** T107's parent is T103 `26f262e`, which is already in T105. `ec5cdb3` is therefore the only new commit.

**Conflicts:** none. `git range-diff` shows `ec5cdb3` unchanged apart from the trailer. Checked areas:
- **Include list:** T107 adds `rsx_color_xfer.h`, near the top of the file and away from the T100/T99/T105 includes.
- **Draw record:** T107 adds `g_shader_packer`. No code depends on the record's size or layout.
- **`rsx_state`:** T107 adds `shader_packer`. The only size use is `memset(sizeof)`, and nothing uses `offsetof`.
- **`rsx_commands.c`:** before T107, `0x1FEC` hit the unknown-method path. That path printed a debug-only line (at most 50) and returned −1, and the only caller (`cellGcmSys.c:2751`) ignores the return value. T107 only stores the value.
- **Shader/PSO lookup:** untouched. `rsx_fp_apply_srgb_output` is never called, which T107's own test pins.

**Rendering with flags unset (VERIFIED by code and pins):**
- No colour correction is enabled.
- T107 costs one copied word per draw. `dr_color_xfer` is not evaluated, because `RSX_XFER_LOG` short-circuits and RSXI is off.
- The probe costs one branch per replay and one per Present.

## 2. Regression-test change (T101 pin)

- **Old pin:** a regex required `s_present_this_frame = 0;` to be immediately followed by `render_frame();`. T99's timing line sits between them, so the pin failed although behaviour was unchanged.
- **New check (`tools/test_t101_pins.py`), structural:**
  - inside `vp_flush` there is exactly one `render_frame();`;
  - `const int keep = …` comes before `… = 0;`, which comes before `render_frame();`, which comes before `… = keep;`;
  - between the clear and the replay, nothing touches the flag;
  - the flag is written exactly twice;
  - `vp_flush` contains no Present.
- **New pin:** the only `->Present(` is inside `if (s_present_this_frame) {`.
- **Negative fixtures**, each a mutated copy of the real source, all of which must fail:
  - the flag is left set;
  - the flag is restored before the replay;
  - the flag is set inside the timing gap;
  - the early replay calls Present;
  - the replay happens before the clear;
  - the Present guard is replaced by `if (1)`.
- **Positive fixture:** extra timing between the clear and the replay must be accepted.
- **Result:** 15/15 on T108, and 15/15 on T96I `95a906d` (where the original lines are adjacent).

## 3. Offline results (`logs/suite_t108.txt`): **23 PASS / 0 SKIP / 0 FAIL**

| Origin | Tests |
|---|---|
| T88 | `test_d3d12_blend_state`, `depth_state`, `rsxi_hooks`, `shader_trace`, `texture_source_order`, `zeta_pool` |
| T92 | `test_rf_phase` |
| T95 | `test_geom_expand` |
| T96 | `test_vp_flush`, `test_prim_stream` (primitive restart and winding), `test_draw_rejection`, `test_present_gate` |
| T99 | `test_rsx_frame_perf` |
| T100 | `test_race_display_diag.py` (10 pins), `test_race_display_diag.c` (16 checks) |
| T101 | `test_t101_offscreen_replay.c` (34 checks), `test_t101_pins.py` (15) |
| T102 | `test_vp_expand` (byte-identical expansion) |
| T103 | `test_win_dpi.c` |
| T105 | `test_race_present_probe` (12 pins + 32 C checks) |
| T107 | `test_d3d12_color_xfer` (pins + `test_color_xfer.c`) |
| other | `test_rsxi_frame_gain`, `test_rsxi_geom` |

**Other checks:**
- **TU compiles:** `rsx_d3d12_backend.c`, `cellGcmSys.c` and `rsx_commands.c`, with the exact T96I flags (`tools/tu_t108.cmd`): all rc=0, with no new warning kinds against T105.
- **Root signature, samplers, PSO keys:** unchanged since `95a906d`, with no hunk touching them. Static samplers still ignore guest filter/wrap, a known pre-existing gap that is not fixed.
- **Audit:** `audit_public.py --tree` gives 26 BLOCKs, identical to the T105 tree. None are in T105, T107 or T108 files.

**Missing tests:**
- T103's RSXI sampler-word record has no unit test.
- Draw drops and shader-binding failures can only be checked at runtime.

## 4. Diagnostic correctness

**Operating together (VERIFIED by code):**
- The four tools use separate state: T105 `s_rpp*`, T100 `s_rtpool`, `g_pdg`, T107 `seen[64]`/`shown`.
- All logging is bounded:
  - probe: ≤ 32 Presents plus 1 line;
  - `RTPOOL_LOG`: ≤ 4096;
  - present_diag: ≤ 1024;
  - `RSX_XFER_LOG`: n lines, deduplicated over 64 keys, so keep n ≤ 64.
- GPU readbacks happen only on probed frames (3 copies plus one wait) and on dump frames (existing).

**Frame identity:**
- The probe reports the host replay (`frame_count`), the probe's own count of **real Present calls** (incremented only inside the `if (s_present_this_frame)` block), and the guest flip count.
- Guest-frame accounting resets only when `!keep_targets`, so it accumulates across early replays.
- An early replay never Presents (pinned, §2).

**Probe interpretation (VERIFIED by code and tests):**
- **Readback point:** after `guest_fb_present` and `composite_present`, and before both the dump and the `→PRESENT` barrier. This is the image Present shows.
- **Swap-chain image:** `render_targets[fi]`, the replay's own buffer, read in the swap chain's format (`R8G8B8A8_UNORM`, pinned). `sc_idx` is read immediately before Present and compared with `fi`.
- **Barriers:** backbuffer `RENDER_TARGET → COPY_SOURCE → RENDER_TARGET`. Offscreen targets go to `COPY_SOURCE` and back to their tracked state. Copies only read the source.
- **Synchronisation:** one `wait_for_gpu` after `ExecuteCommandLists`, before mapping. This is the same pattern as the existing dump path.
- **Formats:** all four surface formats the backend creates are classified (RGBA8, RGBA16F, RGBA32F, R32F; BGRA8 too), with NaN counted separately. A pin now fails if a new format is added without probe support.
- **Fixed here:** RGBA32F was previously `unclassified`.

**Limit:** `scene` and `comp` are slot indices recorded during the frame. If a slot was reassigned after an early replay, the line shows the `off` actually read, so compare it with the expected surface (for example `0x01DD0000`).

**What the verdicts prove:**

| Verdict | What it proves |
|---|---|
| **A** | **Proven:** the surface with the most draws was black at Present time. Whether it is the scene is then a check on `off` |
| **B** | **Proven:** content upstream and a black backbuffer, so the loss is in composition. *Which* composition step (bloom alpha, exposure) remains a **hypothesis** |
| **C** | **Proven:** a host Present failure or a wrong swap-chain buffer |
| **D?** | **Proven:** the backbuffer had content and Present succeeded. That earlier screenshots were wrong-stage is a **hypothesis**, confirmed only if a presenting dump (`dumped=1`) of the same replay is lit |

## 5. Build and launch (needs explicit authorization; nothing run)

1. **Configure and build** (identical to T96I except the source tree and output directory):
   - `generated\analysis\t108\configure_t108.cmd` runs `cmake -S port -B build\motorstorm-t108 -G Ninja -DCMAKE_BUILD_TYPE=Release` with clang-cl 23.1.3 and `-DPS3RECOMP_DIR=…\ps3recomp-t108`. The other options are the same as T96I.
   - `generated\analysis\t108\build_t108.cmd` runs `cmake --build build\motorstorm-t108 --parallel 6`.
2. **Pin and prepare:**
   - `py -3 generated\analysis\t108\run_t108.py prepare` copies the exe into `t108\exe\` and prints its SHA256.
   - Set `EXE_SHA` in `run_t108.py` to that value and run `prepare` again. It makes fresh, hash-verified private `hdd0`/`hdd1` copies and writes `snapshot_manifest.json`.
   - `preflight` refuses to launch with an unpinned or mismatched hash.
3. **Dry run, then launch:** `py -3 generated\analysis\t108\run_t108.py dryrun`, then `py -3 generated\analysis\t108\run_t108.py launch`.

**Runner behaviour:** `run_t108.py` is generated from T98's runner by `tools/make_runner.py`.
- **Race entry:** the original CROSS-press route, at most 9 presses.
- **Intro:** `PS3_DEV_SKIP_INTRO=1`. `GCM_STALL_INTRO=5000:40` aborts only if the skip fails.
- **No early stop:** no `--target`. LoadRace, race intro and `[race-probe]` events are only logged.
- **Caps:** 300 s session, 310 s host.
- **Inputs:** the PT config is byte-identical to T98's. The env scrub covers `RACE_*`, `RTPOOL*`, `RSX*` and `PS3_*`, so T104's `PS3_SPURS_GUEST_MAXCONT` cannot leak in.
- **Timeline:** the controller timestamps `[XFER]`, `[rtpool]`, `[present_diag]` and `[race-probe]` lines.

**Diagnostic flags (on top of T98's set):**

| Question | Flag |
|---|---|
| 1. Real Presents in the race? | `PS3_PRESENT_DIAG_MS=5000 PS3_PRESENT_DIAG_MAX=64`; also `present=` in the probe lines |
| 2–4. Scene / composition / backbuffer non-black? | `RACE_PRESENT_PROBE=12 RACE_PRESENT_PROBE_MINDRAWS=200 RACE_PRESENT_PROBE_EVERY=20` |
| 5. Were earlier screenshots misleading? | `CELLMARK_DUMP=12 CELLMARK_DUMP_EVERY=8 CELLMARK_DUMP_MINDRAWS=200 CELLMARK_DUMP_PRESENT_ONLY=1`; compare with `dumped=1` probe lines |
| 6. Does the loading screen ask for SHADER_PACKER or texture gamma? | `RSX_XFER_LOG=48`; timestamped against the LOAD RACE START page (~110 s) |
| 7. Render targets evicted across early replays? | `RTPOOL_LOG=64` (`live=1`), plus `rtpool_live` in the probe lines |

RSXI capture is left off (about 2 s per frame); `RSX_XFER_LOG` answers question 6 without it.

## 6. Success and failure criteria

| Check | Pass | Fail |
|---|---|---|
| **Validity** | intro skip OK; `[race-probe] on:` printed; `0x8C2A0` marker (race entry, ~200 s); no crash or `[fc-watchdog]`; no new `REFUSED`/`dropped_draw` against T98 | — |
| **Q1: real Presents** | the `[present_diag]` ok count rises after race entry | flat: the failure is in the present gate |
| **Q2–4: probe verdicts** | `D?` with presenting dumps lit: **race visible**, confirm by eye; T98 was a capture artifact | `A`: scene black. `B`: composition black (then check exposure and bloom alpha). `C`: swap chain |
| **Q6: loading-screen colour transfer** | `[XFER]` lines with `packer≠0` or `gamma≠0` in the loading window: a transfer is requested and not applied | none in that window: T107's colour hypothesis does not apply to the loading screen |
| **Q7: evictions** | `rtpool_live=0` | `[rtpool] … live=1` on a composite input: the T101 eviction hazard is real |

## 7. Remaining uncertainties

- **`RSX_XFER_LOG` may run out early.** It logs the first 48 *distinct* requesting draws from boot, so splash, Bink and menu draws could use them up before the loading screen. Order in the timeline shows whether that happened; if so, a later run needs a time-gated variant.
- **Probe slot reuse** after early replays (§4, read `off`).
- **What happens after the verdict:** exposure (`RSX_RT_READBACK` off) and bloom alpha are the leading B-case hypotheses, and are untested.
- **Static samplers** still ignore guest filter/wrap state (pre-existing; affects fidelity, not black).
- **Runtime-only:** probe overhead (one GPU wait on 12 frames) and the actual race frame rate.

## Readiness

**Ready for one explicit build-and-launch authorization.** Nothing here claims a visible race or a fix.

Files under `generated/analysis/t108/`:
- `configure_t108.cmd`, `build_t108.cmd`;
- `run_t108.py`, `pb_stall_t108.cfg`;
- `tools/`: `make_runner.py`, `run_suite_t108.py/.cmd`, `make_tu.py`, `tu_t108.cmd`;
- `logs/`: `suite_t108.txt`, `tu/`, `audit_tree.log`.
