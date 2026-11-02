# T182: vertex pipeline recovery

Status: **`RSX_VP_DIRECT` recovered, off by default, offline only. EXPERIMENTAL.** All timings are synthetic; no FPS gain is claimed.

Commit `753ff8d9`, branch `agent/t182-unintegrated-recovery`, copied unchanged from the uncommitted work in `ps3recomp-t175`, which was left as it was.

## 1. The T175 test failures were not defects

| Failure in `generated/analysis/t175/ev` | Cause | Label |
|---|---|---|
| `test_vp_direct`, `test_vp_indexed` FAIL in `ev/suite.txt` (17:08) | Stale. The current files pass: 576,000 byte comparisons, 0 failures, all pins pass. A pin was probably corrected after that suite; the exact order is inferred from file times | VERIFIED pass, HYPOTHESIS for timing |
| `ev/pin_test_*.txt` TypeError (17:10) | Run without `env_t169.cmd`, so `CC` was `None`. A harness error | VERIFIED |
| `test_rt_pool_srv_layout`, `test_vpc_watch` | Inherited stale pins, fixed by T176 in T181 | VERIFIED |

The one pin edit in T175 is correct and not a weakening: `|| o + 3 > ixc) continue;` must now appear in two loops, because the direct path has its own.

No implementation defect was found, so none was repaired. Checked in source:

| Risk | Finding |
|---|---|
| Attributes | The direct path writes all four components: `rsx_fetch_attrib` fills from the constant register first, and the plan fills from `tmpl` | 
| Slot order | `vp_vx_begin` and `vp_compact_active` use the same active rule, so slots match `vpc_put_vertex` |
| Offsets, capacity | Same `VPC_UNIT + nv * cs` and the same worst-case room check as the indexed loop |
| Skipped `post` hook | Only `VTX_POS` sets it, and `VTX_POS` forces indexed off |
| Lifetime, sync | Writes inside the already reserved record; no new buffer, wait or thread |
| Exclusions | Needs `RSX_VP_INDEXED`, so inherits its limits (`RSX_VP_COMPACT` on; off under RSXI, `VTX_POS`, `RSX_VP_PARALLEL`) |

## 2. Benchmarks

`bench_draw_path`, heavy, 6,900 draws, median wall ms of 3 runs per arm, one interleaved series. `llama-server` kept about 6.7 GiB on the RTX at low utilization, so RTX figures are noisier than AMD's; some ranges are wide (`ffm` at 2.93x: 42-78).

| Arm | RTX, 2.93x reuse | RTX, 1.5x | AMD, 2.93x | AMD, 1.5x | Upload MB/frame, 2.93x, 1.5x |
|---|---:|---:|---:|---:|---:|
| Off | 65.6 | 66.2 | 58.2 | 58.2 | 131.9, 131.9 |
| Fast fetch | 56.4 | 56.2 | 48.9 | 50.6 | 131.9, 131.9 |
| Scan memo | 50.7 | 51.3 | 47.0 | 48.8 | 131.9, 131.9 |
| Both | 61.6 | 44.3 | 37.2 | 36.8 | 131.9, 131.9 |
| Indexed | 49.9 | 61.8 | 42.0 | 58.5 | 50.6, 93.2 |
| Both + indexed | 36.9 | 40.9 | 25.8 | 38.2 | 50.6, 93.2 |
| Direct (indexed + direct) | 51.4 | 55.5 | 39.2 | 50.9 | 50.6, 93.2 |
| **Both + direct** | **36.3** | **34.8** | **20.4** | **25.9** | 50.6, 93.2 |

- Direct matters most with fast fetch at 1.5x reuse: 40.9 to 34.8 ms on RTX, 38.2 to 25.9 ms on AMD. It writes the same bytes, so upload is unchanged.
- Peak working set 288, 288 and 321 MiB and peak private 649, 648 and 648 MiB for off, both + indexed and both + direct, RTX, 2.93x. Direct adds no allocation.
- Real vertex reuse in the race is unknown, so which column applies is unknown.

## 3. Pixels

Against the T181 binary, 4 frames per arm, with a sensitivity control (`ctrl` changes one position byte and is correctly seen as different).

| Device | Off, fast fetch, both | Indexed, direct and combinations |
|---|---|---|
| RTX 5060, both reuses | Identical | Identical |
| WARP, both reuses (temporary build, one adapter line changed) | Identical | Identical |
| AMD iGPU, both reuses | Identical | **Differ, 0/4** |

Direct equals indexed byte for byte on AMD too (0 changed pixels), so direct adds no difference of its own.

## 4. AMD difference

| Comparison, frame 2, 2.93x, of 691,200 pixels | Changed |
|---|---:|
| AMD corner vs AMD indexed | 3,066 (0.44 %) |
| Same with depth test off | 3,066 |
| AMD indexed vs AMD direct | 0 |
| AMD corner vs RTX corner, same draws | 407,397 (59 %) |
| AMD indexed vs RTX corner | 407,491 |
| RTX corner vs RTX indexed | 0 |

- **Refuted:** T174's idea that coplanar depth ties cause it. With depth off the count is the same.
- **Bytes:** RTX and WARP match, and with no vertex reuse AMD also matched (T174), so the written data and indices are not at fault (VERIFIED by those arms).
- **Context:** AMD already differs from RTX in 59 % of pixels on the same draws, over 100 times the indexed effect. Indexed is no further from RTX than corner. The bench's high-contrast texture makes small sampling changes show as large deltas.
- **Cause:** still unknown. Vertex reuse changing attribute interpolation precision on that hardware is a HYPOTHESIS. Whether game frames show it is unmeasured.

**Decision:** no code change. Keep indexed and direct to RTX in any run until a real game frame has been compared on AMD.

## 5. Other vertex work

T162 GPU fetch stays out (`UNINTEGRATED_WORK_AUDIT.md`). T175's `patch_lane`, `patch_loop`, `patch_ool`, `patch_stage` and `patch_wb` are experiment scripts, not kept results of a selected path, and were not recovered.

## 6. Tests

`test_vp_direct`, `test_vp_indexed`, `test_vp_fetch_plan`, `test_t119_pins`, `test_rsxi_geom` pass; full suite in the audit report. No test was weakened.
