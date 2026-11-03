# T113: black/white race, root-cause investigation and repair (2026-10-27; offline phase + authorized runtime phase, §9)

## 1. Base and commits
- **Worktree:** `ps3recomp-t113`, branch `agent/t113-black-race-repair`, from T110 `e3b961d`. T110 = T108 `6b1a7e4` plus `3c1eb4d` `2692ec0` `9ca3877` `089d17a` `e3b961d`, a linear chain (VERIFIED, `git log`).
- **New commit:** **`19d6b6d`**, CPU-read render targets written back to guest memory by default.
- Not merged or pushed. `ListAgents`: no other session. No other worktree was touched.

## 2. Evidence reviewed (no experiment repeated)

| Source | What it shows | Label |
|---|---|---|
| T108 | **No A–D runtime run exists**: no `t108/runtime-*`, no `build/motorstorm-t108` | VERIFIED |
| T98 (`20261027-111836`) | 35 race dumps, all exact 0. Spacing is exactly 240 SPU task ids between every dump (phase-locked), and `frame_000` is a non-presenting early replay (T100). **They are not evidence of a black presented frame** | VERIFIED (lock) / PARTIAL (the other 34) |
| T96I dumps | all 35 show the **loading screen** (`frame_034_small.png`), not the race | VERIFIED |
| T87B RSXI `f004062` | truncated at 326 events (`events.jsonl.part`), no snapshots | VERIFIED |
| T106 A/B presenting dumps (`t106/ab/runtime-*/frames`, ~200 s, race intro) | **correction (runtime phase):** these are presented race frames. Non-black dumps show the race-intro flyover ("Press X to Skip") **saturated almost entirely white** (A2 `frame_011`: 872 680 of 921 600 pixels pure white); the dumps in between are **all black (max 0)**, in every arm. Copies: `t113/prior_t106/*.png` | VERIFIED (viewed) |
| T106 A/B `[present_diag]` | real Presents continue through the race (arm A2: `present_success` rising, 0 failed). A1/C2 show `DXGI_STATUS_OCCLUDED` (0x087A0001) for the whole run or from mid-run: **host window state, not a renderer cause** (identical arms differ) | VERIFIED |
| T72 / T75 / T84 (pre-T96 race RSXI) | every scene/reflection shader multiplies by VP `c33.x`; `c33.x` = 35.3 = Emax in every capture without write-back; drawn pixels saturate to white; the lower screen was unwritten (missing geometry, fixed later by the T85–T96 push-buffer work) | VERIFIED |
| T75 `cpu_exposure.md` | `func_004C3778` disassembled: G half at `base + y*128 + x*8 + 2`, log2 (zero → −127), geometric mean, clamp(K/gm, Emin, Emax), IIR, `c33 = 1 + S(s−1)`, `SetVPConstant(33)` | VERIFIED structure; parameters K=0.3 S=0.7 Emax=50 HYPOTHESIS (reproduce the 35.3 cap) |
| Run manifests | **no run after T68 set `RSX_RT_READBACK`**. T96I, T98, T106 and the T108/T110 runners all ran or would run with it off (default) | VERIFIED |

## 3. Race pipeline map (T84 f005625, T100, T87B pool addresses)

1. **Race entry:** LOAD RACE START ~110 s; PostLevelLoad ~195 s; first race guest frame ~201 s (T98).
2. **Shadow / depth-only:** zeta `0x0B030000` 1024×2048, `0x00ED0000` 1280×720. About 440 draws per frame are dropped by the attribute-0 gate (T101; fix opt-in, `RSX_ATTR0_CONST`).
3. **Reflection:** `0x07B78D80` 640×480.
4. **Main scene:** `0x00750000` + MRT1 `0x01650000` 1280×720. **Every draw multiplies its colour by `c33.x`.**
5. **Downsample → luminance:** `0x02195900` → `0x022C1600` 10×5.
6. **Exposure:** a 16×16 FP16 surface (`0x07EBA600` at T72, `0x06A1E400` in T100's race). It is sampled by no draw and is **read by the CPU** (`func_004C3778`), which sets `c33` for the next frame.
7. **Bloom / vignette:** 80×45 FP16 chain, then the composite (fp `0x02193941`) → display `0x10000`/`0x394000` = swap-chain buffer.
8. **Present:** only in presenting replays. Early replays never present (pinned since T96).

## 4. First incorrect stage

- **White: VERIFIED mechanism, the scene pass (stage A).** Its content is wrong before composition because the CPU-fed constant `c33.x` is pinned at 35.3.
  - **Cause:** the guest exposure surface is never written. The D3D12 backend keeps render targets in host resources and only wrote CPU-read ones back under `RSX_RT_READBACK=1`.
  - **Consequence:** the CPU reads 0, one zero sample drives the target to Emax, and every pixel brighter than 1/35 saturates.
  - **On current exes:** applies to every run after T68 (VERIFIED by manifests). The resulting image is runtime-unverified on post-T96 exes, since no presented race frame was ever captured.
- **Black: NOT localised (PARTIAL).** No presented race image exists, so A–D cannot be ordered from evidence. Candidates, unranked:
  1. scene regions still unwritten (T84's cause before T96; coverage after T96 not measured);
  2. depth-only drops (shadows only, T101);
  3. a black composite (bloom alpha or exposure; the garage composite works).

  A single zero luminance sample also keeps `c33` at 35.3 even with write-back. So black holes and white saturation are coupled: fixing geometry alone would still leave white, and fixing write-back alone still leaves white wherever a luminance sample hits an unwritten region.

## 5. Fix (`19d6b6d`)

**Changes:**
- `include/ps3emu/rt_readback.h`: new `ps3_rtrb_enable_env()`. If the variable is unset or empty it returns `"1"`; `"0"` still turns write-back off.
- `rsx_d3d12_backend.c` `rtrb_on()`: resolves `RSX_RT_READBACK` through that helper.

**What it enables:** the existing, tested mechanism (275-check harness since T13, used in the T18/T25 garage runs):
- surfaces never sampled by the GPU for 2 generations, up to 64 KB;
- asynchronous copies behind their own fence, applied by a worker thread;
- compare-and-swap application, so CPU writes win.

The race exposure surface is 2 KB. Selection rules are unchanged.

**What it is not:** no exposure value, clamp, gamma or shader is changed. This restores RSX memory semantics for render targets the CPU reads.

**Cost and risk:**
- A few small copies per frame.
- T15 saw heartbeat stalls in two garage write-back runs, never attributed to the write-back code (the samples were in draw recording). This needs watching at runtime.
- The opt-out `RSX_RT_READBACK=0` restores the old behaviour exactly.

## 6. Minimal reproducer and tests

**`tests/test_exposure_writeback.c`**
- **Setup:** the real `rt_readback.h` pipeline (note_write, queue, collect, apply into guest memory) with a 16×16 FP16 exposure surface. The CPU side models `func_004C3778` per T75. 11 checks.

| Case | Result |
|---|---|
| Old default (unset = off) | guest surface never written; `c33.x` = **35.300** after 400 flips; mid-grey 0.3 → **255 (white)** |
| New default (unset = on) | first guest write at flip 4; `c33.x` = **1.140** = closed loop 1+0.7·(0.3/0.25−1); 0.3 → **87** |
| `RSX_RT_READBACK=0` | identical to the old default |
| One zero-luminance sample point | 35.3 even with write-back (documents the coupling with missing geometry) |
| Surface the GPU samples | not written back (policy unchanged) |

**Other checks:**
- **Suite** (`t113/tools/run_suite_t113.cmd`, `logs/suite_t113.txt`): **30 PASS / 0 SKIP / 0 FAIL**. That is T110's 28 plus `test_rt_readback` (275 checks, pin updated to "on by default") and `test_exposure_writeback`.
- **TU compiles** (`tools/tu_t113.cmd`, the exact T96I flags): `rsx_d3d12_backend.c`, `cellGcmSys.c`, `rsx_commands.c` and `rsx_fp_decompiler.c` all rc=0, with no new warning classes against T110.
- **Audit:** `audit_public.py --staged` gives 25 BLOCK, all inherited tree files (same as T107–T110). None of the T113 files are flagged (`logs/audit_staged.log`).

## 7. Runtime validation (needs authorization; not run)

**Build:**
- `generated\analysis\t113\configure_t113.cmd`, then `build_t113.cmd` (T110's scripts retargeted to `ps3recomp-t113`, `build\motorstorm-t113`).
- `run_t113.py prepare A` prints the SHA256; pin `EXE_SHA`; then `prepare A..D`. Each arm gets fresh, hash-verified HDD copies.
- `dryrun` refuses until the hash is pinned (checked).

**Run:** `launch <arm>`. Same CROSS-press route, intro skip, 300 s session cap, no `--target`, race markers log-only. The T108 probes are kept:
- `RACE_PRESENT_PROBE` on real Presents;
- presenting-only dumps;
- `PS3_PRESENT_DIAG`, `RTPOOL_LOG`, `RSX_XFER_LOG`.

There is no high-volume tracing. Keep the game window visible and unoccluded, or Presents return `DXGI_STATUS_OCCLUDED` (T106 A1).

| Arm | Env | Question |
|---|---|---|
| A | `RSX_RT_READBACK=0` | old behaviour: baseline verdicts and dumps |
| B | default + `RSX_RT_READBACK_LOG=64` | does `[rtrb]` select and apply the exposure surface? does the scene stop saturating? |
| C | B + `RSX_ATTR0_CONST=1` | shadows / depth-only geometry |
| D | C + `RSX_RTPOOL_GF=1` | evictions (`[rtpool] live=1`) |

**Pass criteria (B vs A):**
- `[rtrb] A off=<exposure>` lines;
- presenting dumps of race frames with graded, non-saturated colour (more than 2 unique levels in scene areas);
- probe verdict `D?` with lit presenting dumps.

**If B is still black:** the probe verdict localises it.
- A (scene black) → per-region coverage: T84's `zero_draws`/occlusion method on one RSXI presenting frame, with `RSXI_RTS` as in T100 option B.
- B → composite inputs (bloom alpha).

## 8. Remaining defects and open hypotheses

| Item | Status |
|---|---|
| Race visible in presented frames | **not runtime-verified** |
| Black regions / localisation | PARTIAL, needs arm A/B probe verdicts |
| Exposure parameters K/S/Emax | HYPOTHESIS (T75); the fix does not depend on them |
| T110 fixes (samplers, attr0, colour transfer, RT pool) | still opt-in |
| Mip chains never uploaded (T110 D2) | open |
| Write-back cost in race | unmeasured |

## Files
- **Source (T113):**
  - `include/ps3emu/rt_readback.h`, `libs/video/rsx_d3d12_backend.c`;
  - `tests/test_exposure_writeback.c`, `tools/test_exposure_writeback.py`;
  - `tools/test_rt_readback.py` (pin).
- **Analysis:**
  - `t113/tools/` (`run_suite_t113.*`, `tu_t113.cmd`, `make_runner.py`);
  - `run_t113.py`, `pb_stall_t113.cfg`, `configure_t113.cmd`, `build_t113.cmd`;
  - `logs/`.

## 9. Runtime validation (authorized 2026-10-27)

**Build:** `build/motorstorm-t113` from `ps3recomp-t113` `19d6b6d` **plus an uncommitted-at-build instrumentation change** in `libs/video/rsx_commands.c` (committed after the runs as `74fd084`; the exe was built from exactly that tree): `RSX_VPC_WATCH_LANE=<0..3>` and `RSX_VPC_WATCH_MS=<ms>` (log the watched lane once per window). It only reads `rsx_state` after the unchanged constant store and writes its own statics and stderr; with `RSX_VPC_WATCH` unset it does nothing. No new warning classes in that TU.
- exe sha256 **`8264aa1a2cc44ccff122e076dbe4c6247882a92baa1252601da407225d3cdca1`** (pinned in `run_t113.py`).
- The configure/build scripts had inherited T96I's 4-level `cd` (T96I lives in `t96/t96i/`); fixed to 3 levels before the build.

**Runs** (each 300 s cap, fresh HDD copies, same route; race loaded ~150-158 s; the race-intro flyover, "Press X to Skip", is on screen from ~156 s to the cap). All six runs: `present_occluded=0`, `present_failed=0`, `last_hresult=0x00000000`, `present_success` rising to ~6600: **all valid**.

| Arm | Env | `c33.x` (game-computed, RSX_VPC_WATCH 33 x, 250 ms) | Race frames | Label |
|---|---|---|---|---|
| A | `RSX_RT_READBACK=0` (old) | 35.29 by 175 s, **35.300 from 190 s to the cap** | 59 of 60 dumps 89-95 % pure-white pixels; flyover reduced to a white sheet with the HUD | **VERIFIED white** |
| B | default (write-back on), 40 dumps every 3 | 1.4-11 (160-190 s), 35.3 (200-230 s), 1.04-1.15 (260-290 s) | 162-179 s: beach scene visible, overexposed, darkening as exposure adapts | VERIFIED |
| B2 | = B, 60 dumps every 10 | same timeline as B (reproducible) | 164-194 s graded scene; **196-236 s white again**; 238-281 s scene progressively correct; `frame_059` (281 s) correct beach/sky/palms/plane | **VERIFIED: race scene visible and correct outside one window** |
| C | B + `RSX_ATTR0_CONST=1` | same as B2 | same as B2 | VERIFIED no effect: **0 draws admitted**; 239 827 draws into `0x00ED0000` still dropped `position_attrib_disabled` (the gate's NO_PROGRAM/NO_INPUTS cases) |
| D | C + `RSX_RTPOOL_GF=1` | same as B2 | same as B2 | VERIFIED no effect; no `[rtpool]` live losses |
| E | B + PT trace of `func_004C3778` / `func_00756E08` (`pb_stall_t113E.cfg`) | same as B2 | (not dumped) | see below |

**Write-back in the race (B2):** the race exposure surface is `0x07EBA600` 16x16 FP16 (same as T72), `selected`, `queued=3000 applied=3000 stale=0 cpu_words=0`. Not a write-back gap. VERIFIED.

**Black:** no presented race frame is black in any T113 arm (220 dumps, 72 race probes all verdict `D?` with `bb=content`). T106's alternating all-black dumps (`B W52 B W87 ...`, all 8 runs) do **not** reproduce on this exe even in control arm A. The remaining black content is a thin pure-black strip at the sea/sand shoreline in some shots (B2 `frame_012`: ~400 px in the 80x110 block at x160-240), not a black screen. VERIFIED (images); cause not localised (PARTIAL).

**The remaining white window (arm E, measured):**
- The exposure object (VERIFIED at runtime): 5 sample points (vector 0x1867A7F0..0x1867A818), first four (0.15, 0.70), (0.325, 0.63), (0.50, 0.30), (0.675, 0.63); **Emax = 50.0** (`[this+0xC4]`=0x42480000; T75's HYPOTHESIS now VERIFIED).
- G values the game read (`tools/gsamples.py`): 152-182 s and 220-300 s no zero sample, `c33` follows the scene (settles at 1.04). **182.8-219.6 s: sample 0 = (0.15, 0.70) -> texel (2, 11) reads exactly 0** every call while the other four read 0.50-0.84; one zero -> log2 = -127 -> target = Emax -> `c33` -> 35.3. When it becomes non-zero (219.6 s, 0.023), `c33` falls immediately. **VERIFIED.**
- The presented frames of that window have **no** black pixels in that texel's screen block (B2 `frame_018/020/030`: 0 black px in x160-240, y450-560). So the zero is produced **inside the GPU luminance -> exposure chain** for texel (2, 11), not by a black visible region. **Blocker, measured and specific.** Candidates (HYPOTHESIS): a luminance-chain level whose region around (0.15, 0.70) is unwritten/cleared in this camera shot (viewport/scissor or a dropped draw in a downsample pass), or the shoreline strip being exactly zero in the pre-tonemap HDR source there.

**Next step (not run):** one RSXI capture of a frame in the 185-215 s shot with `RSXI_RTS` on the luminance chain (`0x02195900`/`0x02206100` 320x180 ... `0x022C1600` 10x5) and `0x07EBA600`, to find the first chain level whose texel under (0.15, 0.70) is zero. No exposure/gamma workaround applied.

**Images:**
- A: `t113/runtime-A-20261027-172434/png/frame_010.png`, `frame_050.png` (white)
- B: `t113/runtime-B-20261027-171830/png/frame_000.png`, `frame_020.png`, `frame_039.png`
- B2: `t113/runtime-B2-20261027-172958/png/frame_012.png` (scene, shoreline strip), `frame_017.png` (white window), `frame_059.png` (correct), `crop012.png`
- C / D: `t113/runtime-C-20261027-173602/png/`, `t113/runtime-D-*/png/`
- Prior T106 race dumps (white/black): `t113/prior_t106/`
- Run dirs: `generated/runs/20261027-17*-t113-exposure-{a,b,b2,c,d,e}`

## 10. The white shot: shoreline program truncated at 4096 bytes (round 4, 2026-10-27)

**Build/exe:** `40d1ccf` (RSXI pass snapshots of MRT targets, diagnostic) on `74fd084` -> exe `04a52ffb...37f7ff7` (arms G, H); `2562ba8` (fix) on top -> exe `36b1e607...a911d` (arms I, J). F ran on `8264aa1a...cdca1`. All runs: window visible, `present_occluded=0`, `present_failed=0`, `present_success` 6529-6656. Logs: `t113/logs/launch_{F,G,H,I,J}.txt`, `build3.log`, `build4.log`, `audit_staged3.log`, `audit_staged4.log`, `suite_fix.log`.

| Arm | Env (beyond B) | Purpose |
|---|---|---|
| F | RSXI from 187 s, `passes`, RTS = chain + `0x07F2B600`; `RSX_RT_READBACK_PROBE=07EBA600:...` | first chain level that is 0 at (0.15, 0.70) |
| G | RSXI, RTS = `0x00750000`, `0x01650000`, particle layers, chain | scene colour and MRT1 as op 502 reads them |
| H | G + `DEPTH_OFF=1` (diagnostic) | depth rejection or no draw |
| I | fix (default) + RSXI from 199 s | re-measure |
| J | fix exe + `RSX_FP_SPAN=0` | control |

**Capture findings (VERIFIED):**
1. Chain (F `f006392`): 16x16 `0x07EBA600` texels (2-4, 10-12) = 0 <- 10x5 `0x022C1600` (1,3),(2,3) = 0 <- ... <- 2267 zero px in 320x180 `0x02195900` (op 502). The op-502 source `0x07F2B600` has no zero pixel. Write-back is faithful: probe `host = payload = after` at `+0x592`; texel (2,11) G was 0 for qflip 5960-6088 (candidate 3 excluded).
2. Op 502 `fp_0074B181` inputs are all 8-bit UNORM (`0x07F2B600`, MRT1 `0x01650000`, particle copy `0x0BA10000`): no Inf/NaN source (candidate 4 excluded for this zero). `0x0BA10000` is cleared to 0 and filled by op 481 (`fp_02FF05C1`, copy of `0x0B830000`), whose particle program writes colour 0. So op 502 = 16*avg4(MRT1)^2 there: the zero means **MRT1 = 0**.
3. G `f006314` (`capG/f006314_colour_mrt1_lum.png`, `capG/f006314_mrt1zero_mask.png`): MRT1 is the correctly exposed scene except a **black strip along the sea/sand shoreline** plus the 16-px right/9-px bottom bands outside the 1264x711 viewport; the scene colour there is stale (never cleared, not redrawn). Every main-pass program writes MRT1 = colour/16, so no draw covers the strip. Between frames MRT1 holds the velocity buffer (ops 509-538), 0 where static.
4. H: MRT1 zero fraction 1.98 % with `DEPTH_OFF=1` vs 1.97 % in G: not depth-rejected.
5. The only failed pipelines in the scene pass are ops 488-489, `fp_07200641`, blended ONE/INV_SRC_ALPHA over MRT1, sampling scene depth (`zeta_as_color`): `[FP] PS compile FAIL (fp=0x07200641): error X3004: undeclared identifier '_rsx_expand_input'` (16x per run), `pso_ptr` null, nothing drawn.
6. Cause: the backend passed a fixed 4096 bytes to every FP walk. `fp_07200641` is 4848 bytes (runtime log). The decompiler translated its first 4096 bytes (187 instructions); the bx2 helper scan never saw END and returned 0, so `_rsx_expand_input` (called for a `TEX_bx2` on unit 3) was not declared. Seven more race programs are 4160-4240 bytes.

Candidate 1 (dropped/failed luminance-pass draw): no -- the chain draws all render; the failed draw is the scene's shore pass feeding MRT1. Candidate 2 (format/clear mismatch in the downsample chain): no (FP16 chain, no clears involved, single-tap copies reproduce the 0).

**Fix `2562ba8`:** `libs/video/rsx_fp_span.h` + the backend's FP call sites: read through END (at most 64 KiB); programs within 4096 bytes unchanged; `RSX_FP_SPAN=0` = old read. Test `libs/video/tests/test_fp_span.c` / `tools/test_fp_span.py`: a 4832-byte hand-assembled program reproduces X3004 and the missing tail under the old read and compiles under the span (13 checks); pins the call sites. Fails before (HEAD had 15 fixed-4096 FP walks), passes after. `tools/test_t110_pins.py` decompile pin updated from the literal 4096 to `fsz`. Suite `tools/run_suite_t113.py`: 31/31 PASS.

**Re-measure (VERIFIED):**

| Arm | `c33.x` 180-240 s | Frames 186-230 s | `fp_07200641` compile FAIL | Pure-black px/dump (max) |
|---|---|---|---|---|
| B2 (before) | 35.3 at 200-230 s | white (196-236 s) | 16 | 3893 |
| **I (fix)** | **0.95-1.11** (whole run from 180 s: 0.93-1.73) | **scene correct**, 7-14 % white px (sky) | **0** | **22** |
| J (fix exe, `RSX_FP_SPAN=0`) | 35.3 at 200-220 s | 88-92 % white (190-226 s) | 16 | 3887 |

Texel (2,11) in I over the former zero window: 0.12-0.14 (non-zero). Images: `t113/runtime-I-20261027-182926/png/shot_195_211_224.png` (195/211/224 s, correctly exposed), `frame_020`...`frame_039.png`; shoreline before/after `png/shore_B2_vs_I_frame012.png`; J: `t113/runtime-J-*/png/frame_020.png` (white).

**Shoreline strip:** the same fix (VERIFIED: black px max 3893 -> 22). The strip now shows the shore draws as a bright surf band; its look against real hardware is unverified (PARTIAL).

**Left open:**
- The 16-px right / 9-px bottom bands: guest surfaces are 1264x711 inside 1280x720 host targets, so normalised sampling reaches unrendered texels (visible as a streaked right-edge column). HYPOTHESIS for a host-size mismatch; not changed.
- fxc folds `x != x` with or without `D3DCOMPILE_IEEE_STRICTNESS` (`t113/fxc/dis_flags0.txt`, `fxc/test_t113_fp_nan_warp.c`): the game's isnan replacement in `fp_0074C781` is dead on D3D12. Not the cause here (UNORM inputs); not changed.
- No gamma/exposure/shader workaround; no state forced; nothing merged or pushed.
