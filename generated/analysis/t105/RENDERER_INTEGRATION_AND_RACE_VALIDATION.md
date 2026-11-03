# T105: Renderer integration and visible-race validation preparation (2026-10-27, offline, no build, no launch)

- **Worktree:** `ps3recomp-t105`, branch `agent/t105-renderer-integration`, head `36d0fb7`. Not merged or pushed.
- **Peer trees:** T100 (`5288949`), T102 (`1e5d534`), T103 (`26f262e`) and T104 (`d7fc0a9`) are unchanged and clean.
- **Not integrated:** T104 (SPU work, out of scope) and T101 (tests only; run against this tree, not committed).

## 1. Source ancestry (VERIFIED, git)

| Work | Commits | Parent |
|---|---|---|
| T96I | `95a906d` | — |
| T96 | `bd09877` | **tree-identical** to `95a906d` (`3c1ad49b…`); a parallel copy of the same 4 commits |
| T100 | `729caed` → `5288949` | `95a906d` |
| T99 | `db2aa90` | `bd09877` |
| T102 | `1e5d534` | `db2aa90`, so **T102 includes T99** |
| T103 | `c2e9eec` → `26f262e` | `95a906d`, the same renderer base as T100. Not a different branch |
| T101 | `5cb0181` (tests only) | `95a906d` |

**Foundation:** T100 `5288949`. All four inputs share the tree of `95a906d`, so the only differences are their own patches.

## 2. Integration (cherry-pick `-x`, in order)

| T105 commit | From | Conflict | Resolution |
|---|---|---|---|
| `470785e` | T99 `db2aa90` | 1 hunk: the include list in `rsx_d3d12_backend.c` (T100 `race_display_diag.h` against T99 `rsx_frame_perf.h`) | kept both lines |
| `4d7e84c` | T102 `1e5d534` | none | — |
| `83507ef` | T103 `c2e9eec` | none | — |
| `cb844ed` | T103 `26f262e` | none | — |
| `36d0fb7` | new, T105 | — | `RACE_PRESENT_PROBE` (§4) |

**Nothing dropped (VERIFIED):** `git range-diff` shows every source patch identical apart from its context lines and the `cherry picked` trailer.

**Overlap analysis (VERIFIED by diff):**
- **Include changes:** the only conflict, resolved above.
- **PSO cache keys:** no integrated commit touches a PSO key. T102's memo reuses the prepass result inside one pass with the same `vp_gen`. Its epoch is bumped on every prepass and on FP-cache eviction.
- **Root signature, descriptor tables, static/dynamic samplers:** no hunk in `95a906d..HEAD` touches them.
- **T103's scope:** contrary to the brief, T103 does **not** change sampler/filter/wrap behaviour. It adds DPI awareness, and the RSXI JSON now records the guest's `filter`/`address`/`control0` words next to the host sampler.
- **Render-target lifetime:** T100 only adds `gf_used` and log calls (`RTPOOL_LOG`). Eviction and the per-replay `used` reset are unchanged (pinned).
- **Early replay:** unchanged. T99 only wraps the early-replay `render_frame()` call with timing.
- **Presentation diagnostics:** T100's `CELLMARK_DUMP_PRESENT_ONLY` and T105's probe, both opt-in.

## 3. Offline results

- **Suite:** `tools/run_suite_t105.cmd ps3recomp-t105` → `logs/suite_t105.txt`.
- **Totals:** **21 PASS / 0 SKIP / 1 FAIL** (the failure is a stale T101 text pin, row T101 below).

| Origin | Tests | Result |
|---|---|---|
| T88 | `test_d3d12_blend_state`, `depth_state`, `rsxi_hooks`, `shader_trace`, `texture_source_order`, `zeta_pool` | PASS |
| T92 | `test_rf_phase` | PASS |
| T95 | `test_geom_expand` | PASS |
| T96 | `test_vp_flush`, `test_prim_stream`, `test_draw_rejection`, `test_present_gate` | PASS. **Primitive restart and winding are unchanged** |
| T99 | `test_rsx_frame_perf` | PASS |
| T100 | `test_race_display_diag.py` (10 pins), `test_race_display_diag.c` (16 checks) | PASS |
| T101 | `test_t101_offscreen_replay.c` (34 checks, against this tree's sources) | PASS |
| T101 | `test_t101_pins.py` | **6/7.** The "early replay no present" regex expects `s_present_this_frame = 0; render_frame();` to be adjacent. T99 inserted a timing line between them. Behaviour is unchanged, and the same failure already exists in T102/T104. The pin is T101's to update; not edited here |
| T102 | `test_vp_expand` (600 random states; S0 vs cache) | PASS. **Vertex expansion is byte-identical** |
| T103 | `test_win_dpi.c` | PASS |
| other | `test_rsxi_frame_gain`, `test_rsxi_geom` | PASS |
| T105 | `test_race_present_probe` (10 pins + 30 header checks) | PASS |
| TU | `rsx_d3d12_backend.c` and `cellGcmSys.c` with the exact T96I flags (`tools/tu_t105.cmd`) | rc=0. **No new warning kinds** (`logs/tu/`) |
| audit | `audit_public.py --staged` | the same 25 pre-existing BLOCKs, none in T105 files (`logs/audit_staged.log`) |

**Missing tests:**
- **T103:** the RSXI sampler-word record has no unit test (RSXI JSON only).
- **Runtime-only:** "no new draw drops or shader-binding failures" can only be checked at runtime (`[VPVB] draw REFUSED`, `dropped_draw`, FP create failures). Statically, no integrated commit changes draw acceptance or binding.

**Known fidelity gap (VERIFIED, pre-existing, not fixed):** the guest-FP root signature uses static samplers: unit 0 is point/clamp, units 1–15 linear/wrap. They **do not** follow the guest's RSX filter/address state. That changes texel values but cannot by itself turn a frame exactly black (T100/T103). Fixing it would be a separate, non-speculative task.

**Loading-screen brightness:** explained by T103 (VERIFIED). The guest's own unclamped fade `gain = 0.5·t` lasts as long as the load; there is no renderer defect.

## 4. Black-screen instrumentation (`36d0fb7`, off by default)

- **What it does:** `RACE_PRESENT_PROBE=<n>` (≤32) probes every k-th presenting replay (`_EVERY`, default 10) of a guest frame with ≥ m records (`_MINDRAWS`, default 200; counted across early replays). Inside that frame's command list it copies three surfaces:
  - **scene:** the offscreen target with the most draws in the guest frame;
  - **comp:** the RT sampled by the last onscreen draw;
  - **bb:** the backbuffer after `guest_fb_present`/`composite_present`, before Present.
- **Cost:** one GPU wait per probed frame. Disabled cost: one branch per replay and one per Present.
- **One line per probed Present:**

```
[race-probe] n replay present flip records replays onscreen disp_id disp_off disp=WxH pitch last_color last_is_disp
             last_clip fmt fi sc_idx hr dumped rtpool_live
             scene=<class>(slot off WxH dxgi nz/samples nan max mean) comp=… bb=… [comp_tex] verdict=A|B|C|D?|?
```

- **Classes:** `black`, `near_black` (<0.1% lit) or `content`. The classifier samples a 4×4 grid and handles RGBA8, BGRA8, RGBA16F (NaN counted separately) and R32F; other formats show as `unclassified`.

| Case | Signature |
|---|---|
| A: scene already black | `scene=black/near_black` → `verdict=A` |
| B: scene lit, composition black | `scene=content`, `bb=black` (`comp` locates which part of the chain) → `B` |
| C: composition lit, host buffer not shown | `bb=content` with `hr` failed or occluded, or `sc_idx≠fi` → `C` |
| D: wrong screenshot | `bb=content` and Present OK → `D?`. Compare with the presenting-only dumps (`dumped=1` on the same replay) |

Other logs used:
- `RTPOOL_LOG` (T100), for evictions;
- `CELLMARK_DUMP_PRESENT_ONLY` (T100), for dump selection;
- `PS3_PRESENT_DIAG_MS`, for the actual Present counts per stage.

No broad RT dumping.

## 5. Remaining black-screen hypotheses (all HYPOTHESIS until the run)

1. **T98's dumps sampled only early replays** (T100: parity lock, 31/31 in the model). Then the race may already be visible.
2. **Exposure:** `RSX_RT_READBACK` is off, so the PPU reads exposure 0 and `c33` sits at its maximum (dark rather than black in the garage).
3. **Bloom/vignette alpha** of 0 multiplies the composite to black.
4. **Live RT eviction across an early replay** (T101 hazard; `rtpool_live` will show it).
5. **The scene itself black:** depth-only drops, or attr0-off draws (T101 class B).

## 6. Proposed runtime validation (prepared, not run)

1. **Build, once, if authorized:**
   - `agent/t105-renderer-integration` @ `36d0fb7`, the same configuration as `build/motorstorm-t96i`, into a new `build/motorstorm-t105`.
   - Then run `python generated/analysis/t105/run_t105.py prepare`. It copies the exe into `t105/exe/` and prints its sha256.
   - Pin that value as `EXE_SHA` and run `prepare` again: it makes fresh, hash-verified private `hdd0`/`hdd1` copies and writes `snapshot_manifest.json`.
   - `preflight` refuses to launch while `EXE_SHA` is unpinned or doesn't match.
2. **Runner:** `t105/run_t105.py`, generated from `run_t98.py` by `tools/make_runner.py`:
   - the same controller and route: the original CROSS-press race-entry navigation, at most 9 presses;
   - `PS3_DEV_SKIP_INTRO=1`, with `GCM_STALL_INTRO=5000:40` aborting if the skip fails;
   - no `--target`;
   - LoadRace/race-intro/`[race-probe]` events only logged, never a stop;
   - 300 s session cap, 310 s host cap;
   - PT config byte-identical to T98's;
   - env scrub extended to `RACE_*`/`RTPOOL*`.
3. **Environment:** T98's set plus
   - `CELLMARK_DUMP=12 CELLMARK_DUMP_EVERY=8 CELLMARK_DUMP_MINDRAWS=200 CELLMARK_DUMP_PRESENT_ONLY=1`
   - `PS3_PRESENT_DIAG_MS=5000 PS3_PRESENT_DIAG_MAX=64 RTPOOL_LOG=64`
   - `RACE_PRESENT_PROBE=12 RACE_PRESENT_PROBE_MINDRAWS=200 RACE_PRESENT_PROBE_EVERY=20`
4. **Expected timeline (from T98):**
   - LOAD RACE START about 110 s;
   - first race frame about 201 s;
   - probes about every 5 s from about 202 s to about 265 s;
   - dumps on presenting replays only, from about 202 s.
   - Not run: dry-run (needs a pinned exe) and the launch itself.
5. **Validity gates:**
   - `[intro-skip]` OK;
   - `[race-probe] on:` printed;
   - race entry (`0x8C2A0` marker);
   - the `[present_diag]` ok count rising after 201 s;
   - no crash, no `[fc-watchdog]`;
   - no new `REFUSED` or `dropped_draw` lines against T98.
6. **Reading the result:**

| Result | Meaning |
|---|---|
| `verdict=D?` and lit presenting dumps | race visible; T98 was a sampling artifact. Confirm by eye |
| `verdict=A` | the scene is black: investigate depth-only/attr0 drops (T101) |
| `verdict=B` | composition, bloom alpha or exposure: `comp` and `scene` give the stage |
| `verdict=C` | swap chain / Present |
| `rtpool_live>0` with a composite input evicted | apply the T101 fix with a regression test |

## 7. Readiness

**Ready for one authorized full build: YES.**
- Integration is conflict-free apart from the include line, and every source patch is preserved.
- The offline suite passes, except one stale T101 text pin whose behaviour is unchanged.
- Changed TUs compile with the exact project flags.
- The new diagnostics change no rendering when unset.

Nothing here claims a visible race, a speedup, or a black-screen fix.

**Files:**
- `tools/` (`edit_backend.py`, `rpp_block.c`, `make_tu.py`, `tu_t105.cmd`, `run_suite_t105.py/.cmd`, `make_runner.py`)
- `run_t105.py`, `pb_stall_t105.cfg`
- `logs/`
