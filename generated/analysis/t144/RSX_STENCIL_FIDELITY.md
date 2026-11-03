# T144: RSX stencil and depth-test fidelity

Date: 2026-10-28.

- **Branch:** `agent/t144-rsx-stencil-fidelity`, worktree `ps3recomp-t144`, based on `07b453f` (T141 tip; contains T113, T120, T133, T137).
- **Scope:** offline only. No game build or launch, no merge, no push.
- **Ownership check:** `ListAgents` showed two idle/busy peer sessions. There was no T144 branch, worktree or report, and the T141/T142/T143 worktrees were not touched.

Labels: VERIFIED / PARTIAL / HYPOTHESIS.

## 1. Original RSX stencil semantics

**Registers (VERIFIED, `rsx_commands.c` against the NV4097 method map in `docs/rsxfifo.txt`)**

| Register | Address(es) |
|---|---|
| `STENCIL_TEST_ENABLE` | 0x328 |
| `STENCIL_MASK` (write mask) | 0x32C |
| `STENCIL_FUNC` | 0x330 |
| `STENCIL_FUNC_REF` | 0x334 |
| `STENCIL_FUNC_MASK` (read mask) | 0x338 |
| `STENCIL_OP_FAIL` / `OP_ZFAIL` / `OP_ZPASS` | 0x33C / 0x340 / 0x344 |
| `TWO_SIDED_STENCIL_TEST_ENABLE` | 0x348 |
| `BACK_STENCIL_MASK`, `_FUNC`, `_FUNC_REF`, `_FUNC_MASK`, `_OP_*` | 0x34C–0x364 |
| `ZSTENCIL_CLEAR_VALUE` | 0x1D8C (Z24S8: depth in [31:8], stencil in [7:0]) |
| `CLEAR_SURFACE` | 0x1D94 (bit 0 depth, bit 1 stencil) |
| `SET_SURFACE_FORMAT` | [7:5]: 1 = Z16 (no stencil), 2 = Z24S8 |

The decoder maps each register to the right field; reset values are ALWAYS, ref 0, masks 0xFF, ops KEEP.

**Rules (PARTIAL: the NV40 RSX follows the GL model; no PS3 hardware test was possible offline)**

- **Payloads:** GL enums. Compare is 0x200 + {NEVER … ALWAYS}. Ops are KEEP, ZERO, REPLACE, INCR (clamped), DECR (clamped), INVERT, INCR_WRAP and DECR_WRAP.
- **Test:** `(ref & read_mask) FUNC (stencil & read_mask)`.
- **Write:** `stencil = (stencil & ~wmask) | (op(stencil) & wmask)`.
- **Which op runs:**
  - sfail when the stencil test fails;
  - zfail when the stencil test passes and the depth test fails;
  - zpass when both pass, or when the depth test is off (then depth is neither tested nor written).
- **Faces:** one-sided means back faces use the front state. Two-sided gives back faces their own func, ops, ref and masks.
- **No stencil:** a Z16 or absent zeta has no stencil.

## 2. Current D3D12 behaviour (VERIFIED by code reading)

| Path | Stencil |
|---|---|
| Default (no switch) | Every guest-FP pipeline is built with `StencilEnable = FALSE`. Guest stencil state is recorded but ignored. |
| `RSX_DEPTH_STATE=1` (T120, `169e618`) | Full translation via `rsx_ds_key` → `rsx_ds_apply`: compare, all three ops, read/write masks, two-sided func/ops. The reference comes from `OMSetStencilRef`. Bundled with the guest depth-write mask and compare. |
| Clears | `ClearDepthStencilView` with the guest clear value and the CLEAR_SURFACE bits. It ignores scissor and the stencil write mask. |
| Depth target | Each guest zeta has its own D24S8 slot, which keeps its contents across binds. A draw that samples its own zeta as depth gets the shared buffer instead, which is cleared to stencil 0 on every bind. |
| `RSX_MSAA` (T137) | A 2-sample zeta twin; 1↔2-sample contents are not carried over ("depth/stencil resolve is not implemented"). |

## 3. Verified mismatches

| # | Mismatch | Status | T144 action |
|---|---|---|---|
| M1 | Default path: no stencil at all. | VERIFIED (code, harness `base` arm) | Unchanged (default stays). Opt-in fix below. |
| M2 | Stencil existed only together with `RSX_DEPTH_STATE`'s depth changes. `rsx_ds_apply` returned early without the full-key bit, so stencil could not be validated on its own. | VERIFIED (76 WARP failures with the base header) | **Fixed:** `RSX_STENCIL_EXACT=1` |
| M3 | RSXI never recorded depth/stencil clears: the clear path returned before `rsxi_on_clear` when there were no colour bits. No capture shows MotorStorm's stencil clear values. | VERIFIED | **Fixed:** `zs_clear` events |
| M4 | Back-face ref and read/write masks are reduced to the front values. D3D12's base desc has one ref and one mask pair. | VERIFIED (code, already logged by T120). MotorStorm's use is unknown: two-sided state was never recorded. | Recorded now (`stencil_back`). No translation: there is no evidence of use. |
| M5 | A stencil test on the shared depth buffer (draw samples its own zeta as depth) does not see the guest's stencil. | VERIFIED (code). Not seen in the race captures: the velocity pass reads its zeta as colour, which keeps the zeta bound under either switch. | Logged (`[ds] op …`) |
| M6 | Z16 surfaces get a D24S8 slot, so stencil ops would act on a non-existent buffer. | VERIFIED (code). All captured race stencil draws use Z24S8 (format 2). | None |
| M7 | Clears ignore scissor and the stencil write mask. | Code VERIFIED. Whether RSX clears honour them is HYPOTHESIS (no hardware or reference source here). | None |
| M8 | `RSX_MSAA`: 2-sample stencil writes are not visible to a later 1-sample pass on the same zeta. | VERIFIED (code). Every captured writer and reader on zeta `0x00ED0000` uses antialias 3, so this is not triggered. | None |

T120's full-key translation matches the model on all 95 cases of its arm (VERIFIED, §6).

## 4. Affected MotorStorm draw operations

Source: race captures I and G (`t113/runtime-{I,G}…/rsxi`), tallied with `t144/tools/stencil_usage.py` (output in
`t144/usage_*.txt`). Ops, write masks and two-sided state are absent from those captures, because they predate `ds_key`.

| Frame | Draws | Stencil on | Use |
|---|---|---|---|
| I f006502 / G f006264 (main scene) | 665 / 546 | 442 / 424 | **Tags:** ALWAYS with ref 0 (397), 255 (31) and 64 (12), on zeta `0x00ED0000` (1280×720, AA3) and `0x0B920000` (640×360). **Readers:** op 594 / 480 (`fp_022CD841`, NOTEQUAL 128 mask 128, depth test on, writes off) and op 651 / 532 (velocity pass `fp_0074CE81`, NOTEQUAL 255, depth off, reads its zeta as colour). |
| I f006527 / G f006289 (shadow atlas) | 917 / 947 | 755 / 682 | **EQUAL 64** on zeta `0x0B030000` (1024×2048, 3 cascade viewports). No draw in the frame writes stencil, so the outcome depends on the stencil clear value. |

Effects (all HYPOTHESIS until a run records the clear values):

- **Op 594:** it passes wherever stencil bit 7 is clear. The ref-255 writers come after it (ops 620–650), so at op 594 only the clear value can set bit 7. If the clear value has bit 7 set, op 594 skips untouched (sky) pixels; otherwise it covers everything, as it does today.
- **Velocity pass:** it skips pixels tagged 255 by ops 620–650 (`fp_022C2301` / `fp_0252B541`, probably the vehicles), plus any pixels left at a clear value of 255.
- **Shadow atlas:** a stencil clear to 64 means no change from today; any other value means the shadow casters drawn today would be masked out. MotorStorm does issue stencil-only (0x2) and depth+stencil (0x3) clears ("CLEAR_SURFACE new mask=0x2/0x3" in 101 earlier logs); their values were never logged.

## 5. Implementation and commits

| Commit | Change |
|---|---|
| `121879f` | **Header (`rsx_depth_state.h`):** a stencil-only key (bit 48: legacy depth bit plus guest stencil bits [47:6], below the MSAA byte). `rsx_ds_apply` applies depth only from a full key and stencil from a full or stencil-only key. **Backend:** `RSX_STENCIL_EXACT=1` (opt-in, read once) selects that key. With either switch, a zeta read only as colour stays bound (`ds_bind_exact`), and the legacy depth write marks the zeta image stale. `RSXI` gains `zs_clear` events (mask, depth, stencil, zeta, slot) and a `stencil_back` field on draw records. The shared-buffer stencil case is logged. Also: the WARP test `test_t144_stencil_warp.c`, the driver `tools/test_stencil_exact.py`, and the T120 test pins updated for the rename. |
| `c31aa83` | Real-backend harness `test_t144_stencil_backend.c` |

- **Defaults unchanged:** no switch gives the old key, bit for bit; `RSX_DEPTH_STATE=1` gives the same key as before.
- **Game commands untouched.** Stencil is never forced on.
- **Audit:** `audit_public --staged` shows the same 25 inherited items.
- **Private tools:** `generated/analysis/t144/tools/` holds `stencil_usage.py`, `stencil_backend.py`, `run_arms.sh`, `build_backend_test.py` / `bbt.cmd` / `bw.cmd` (from T141) and `env.cmd`.

## 6. Offline test results

**`test_t144_stencil_warp`** checks every pixel of the stencil plane (subresource 1) against the C model in §1. It runs every case under both keys:

- stencil off;
- the 8 compares × refs below, at and above the stored value;
- read masks (5 cases);
- 8 ops × start values {0x00, 0x7F, 0xFF} × write masks {0xFF, 0x0F};
- sfail vs zfail vs zpass;
- depth test off;
- two-sided front/back, and one-sided;
- stencil-only and depth-only clears, each preserving the other plane;
- a tag surviving a switch of depth target plus a DEPTH_WRITE → shader-read → DEPTH_WRITE round trip;
- the two keys differing only in depth writes.

| Run | Result |
|---|---|
| WARP + debug layer | **191 checks, 0 failed**, 0 errors |
| WARP + GPU-based validation | 191 / 0, 0 errors |
| RTX 5060 driver (`T144_HW=1`) | 191 / 0 |
| WARP against the **base** `rsx_depth_state.h` (new key helper shimmed in) | **76 failed, all in the stencil-only arm.** The `RSX_DEPTH_STATE` arm has 0 failures, which means T120's translation matches the model. |

**Real backend `test_t144_stencil_backend`** (RTX 5060, debug layer and message drain, RSXI snapshots at frame 5), from `logs/stencil_backend.txt`:

| Arm | Tag + NOTEQUAL across a zeta switch | Stencil-only clear 64 + EQUAL 64 / stencil 0 + EQUAL 64 | Debug-layer errors |
|---|---|---|---|
| none (`base`, `base_gbv`) | NOT RSX: left half drawn | NOT RSX: the stencil-0 pass draws | 0 |
| `RSX_STENCIL_EXACT=1` (also with GBV) | RSX: left 1.000 clear, right 1.000 white | RSX: 1.000 / 1.000 | 0 |
| `RSX_DEPTH_STATE=1`, both switches | RSX | RSX | 0 |
| antialias 3, with `RSX_MSAA=1` (also with GBV) | RSX | RSX | 0 |
| all switches (MSAA, window, feedback, zeta exact, MRT, depth state, stencil) | RSX | RSX | 0 |

Each arm records 5 `zs_clear` events per frame, including the stencil-only 0x02 clear with value 64, and `stencil_back` on every draw.

**Suites:**

- These pass: `test_stencil_exact` (10), `test_depth_state`, `test_d3d12_depth_state`, `test_blend_feedback`, `test_msaa`, plus 15 further RSX/D3D12 drivers.
- Six drivers fail identically at base `07b453f`, so not because of T144: `test_d3d12_zeta_pool`, `test_fp_alias`, `test_rsxi_geom`, `test_rt_pool_srv_layout`, `test_rt_readback`, `test_rt_vis_trace`. The base run used a temporary detached worktree, since removed.

## 7. Performance impact

RTX 5060, no debug layer, an 8×4 target, so the numbers are state-change bound (`logs/perf_hw_nodebug.txt`; two runs agree within 2%):

| Case | Recorded | Recorded + executed |
|---|---|---|
| one pipeline | 23 ns/draw | 28 ns/draw |
| stencil on/off pipeline every draw | 90–100 | 488 |
| + `OMSetStencilRef` every other draw | 95–98 | 492 (the ref itself costs about nothing) |
| stencil clear every 16 draws | 40 | 56 |
| depth-target rebind every 16 draws | 32–34 | 83 |
| new stencil pipeline | 0.011 ms each (shaders already cached) | |

**In the race captures** (PARTIAL: the approximate key leaves out the unrecorded ops):

- the stencil state changes only where the fragment program and other pipeline state change anyway;
- that means **+0 pipeline switches and +0 distinct pipelines per frame** (133 / 49 / 122 / 59 key changes, unchanged);
- there are 4 reference changes per frame;
- no extra clears or transitions: the guest's own clears are replayed as before.

Expected game cost: negligible (HYPOTHESIS until a runtime A/B).

## 8. Integration considerations

| Line | Relation | Result |
|---|---|---|
| T113 `2562ba8`, T120 `169e618`, T137 `876a403`, T141 `07b453f` | ancestors of T144 | no conflict |
| T142 `e9f3237` (2 commits) | separate; touches `rsx_d3d12_backend.c` (fetched-unit windows) | `merge-tree` clean; no zeta/stencil overlap |
| T143, T140, T119, T122, T134 | separate | `merge-tree` clean |

Further points:

- **T120:** `RSX_STENCIL_EXACT` reuses T120's zeta-as-colour binding rule under either switch. With both switches on, behaviour is exactly `RSX_DEPTH_STATE=1`.
- **T137 MSAA:** the stencil tests also pass on the 2-sample twins. The 1↔2-sample carry-over gap (M8) stays.
- **T141 feedback / zeta exact:** the "all" arm is clean. The stencil byte in the zeta-as-colour image is refreshed after stencil writes.
- **Depth encoding:** stencil clears preserve depth, which the WARP clear cases check.

## 9. Proposed bounded runtime validation (needs authorisation; not run)

**Run:**

- the existing race route (scripted pad), stopped at race entry + 30 s;
- `RSX_TEX_MIPS=1 RSX_GUEST_SAMPLERS=15 RSXI=1 RSXI_SNAP=passes` at 2 race frames, including one shadow-atlas frame.

**Arms:**

- A: none;
- B: `RSX_STENCIL_EXACT=1`;
- C: `RSX_DEPTH_STATE=1`;
- D: B + C.

**Read from the records:**

1. `zs_clear` values for zetas `0x00ED0000` and `0x0B030000`. This settles the §4 hypotheses (bit 7 of the main clear; 64 for the atlas).
2. `ds_key` ops and write masks of the tag draws, and `stencil_back` together with the two-sided bit.
3. The pass snapshots after op 594 and after the velocity pass. Compare the cascade atlas between A and B; any shadow loss in B would mean a wrong clear value or an ordering problem.
4. The `[ds]` log lines (shared-buffer stencil tests, back-face values differing from front).
5. The frame time against A (expected unchanged).

**Exit criteria:** B's records satisfy §1's rules against the recorded clears, the images change only inside stencil-masked regions, and there are no new D3D12 errors.
