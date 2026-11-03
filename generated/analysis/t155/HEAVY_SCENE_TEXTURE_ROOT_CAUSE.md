# T155: why heavy-scene texture recording costs 200 ms per frame

2026-10-29. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. One authorised diagnostic launch, no retry. Nothing was pushed or merged.

## 0. Root cause (VERIFIED)

**The heavy scene's texture working set is larger than the backend's fixed 96-slot upload table.** Per-pass cache resets are not the cause, and neither is hashing.

- **The pass split.** A heavy guest frame (about 6,900 draws) replays as 4 RSX passes, because `MAX_DRAWS` = 2,048 draw records per pass.
- **What happens at each pass.** Every pass clears every slot's "bound this pass" flag (`render_frame`, `vp_tex[].used = 0`). That is correct and cheap.
- **What goes wrong.** When a bind finds no slot, `vp_upload_tex_slot` takes the first slot not bound in this pass and evicts whatever texture it held. With all 96 slots full, every pass evicts textures that a later pass of the same frame needs again.
  - Each eviction is a resource `Release`. When the shapes differ, which is the common case, it is followed by two `CreateCommittedResource` calls (texture and upload buffer) and a full decode and copy.
  - Once all 96 slots are bound in a pass, the remaining new textures get **no slot at all**: `vp_upload_tex_slot` returns -1 and the draw is recorded **without that texture**. That is a correctness bug, not only a cost.

## 1. Baseline and diagnostic exe

| Item | Value |
|---|---|
| ps3recomp | `agent/t155-rsx-heavy-texture` (worktree `ps3recomp-t155-rsx-heavy-texture`) from T154 `e8e972a` (which contains T153 `2a764e1`; verified ancestor) |
| diagnostic commit | **`746ff2c`**: `RSX_TEXREC_STATS=1` (one `[tex-rec]` line per render pass: lookup outcomes, evictions, refetches, re-creations, SRVs, checksum count and bytes, decode bytes, rdtsc time per step; read-only, off by default) |
| port / build | `port-t155` = `port-t154` (the `MSPR_WWS_AOT` block); `tools/build_t155.cmd` = the T154 recipe; 312/312, rc 0, `Wws job AOT: 31 module(s)` |
| diagnostic exe | **`2125c901ba0a3ca5995f07cc9513c1d2de17463819828fd55ebd493993d48a19`** (pinned `ab/exe_d`) |
| T154 references checked | exe `e8386a74…` (`build/motorstorm-t154` and `t154/ab/exe_w`), root `334e173` |

## 2. The launch (VERIFIED)

- **Run:** `ab/run_t155diag.py launch D Dr1` (from `tools/make_runner_t155.py`), 14:48–14:52.
- **Exit:** rc 0, `controller_stop=race entry + 90 s`; 744 race frames, so the heavy scene is covered (frames 600–743).
- **Environment:** exactly T154 arm BA (T153 preset + `PS3_TEX_SNAPSHOT_WWATCH=1` + `PS3_SPU_WWS_STATS` + `PS3_SPU_WWS_AOT=1`) + `RSX_TEXREC_STATS=1`. Same route, controller, race and stop as T154.
- **Host:** other projects' Python jobs were waited out first (busy 0.7 core at launch).
- **Data:** logs are private (`generated/runs/20261029-144831-t155-diag-Dr1`, `ab/runtime-Dr1-*`). Analysis: `tools/ana_texrec_t155.py` → `ab/texrec_Dr1.json`.
- **Comparison with T154 BA, phase-matched by race-frame index (`t154/tools/phase_match_t154.py`):**

  | | T155 diagnostic | T154 BA |
  |---|---|---|
  | light FPS | 19.78 | 21.0 / 21.2 |
  | heavy FPS | 3.39 | 3.53 / 3.59 |
  | heavy texture ms per frame | 206 | 186–194 |

  The counters cost a few percent, and the workload is the same.

## 3. Light vs heavy, per guest frame (means; race frames 40–499 and 600–743)

| | light (1 pass) | heavy (4 passes) |
|---|---|---|
| draws / texture lookups | 2,085 / 14,085 | 7,022 / 67,783 |
| time in `vp_upload_tex_slot` (= `[rsx-frame-perf]` tex) | 1.9 ms (0.14 µs per lookup) | **208 ms (3.07 µs per lookup)** |
| slots in use at pass end | 84 of 96 | **96 of 96** |
| bound this pass (no work) | 14,002 | 63,935 |
| checksum hits / stale | 83 / 0 | 79 / 0 |
| misses that took another texture's slot | 0.2 | **227** |
| … of which refetch a texture evicted earlier in this guest frame | 0.2 | **100** |
| resource re-creations (Release + 2 × CreateCommittedResource) | 0.2 | **193** |
| SRV creations | 0.3 | 227 |
| binds with **no slot** (drawn without that texture) | 0 | **3,542** |
| decoded bytes | 0.05 MB | 36.8 MB |
| checksum: count / source bytes / time | 83 / 18 MB / 0.31 ms | 79 / 11 MB / 0.22 ms |
| CreateCommittedResource time | 0.10 ms | **96.0 ms** |
| Map + decode + Unmap | 0.04 ms | **30.6 ms** |
| copy + barriers / SRV | 0.004 / 0.001 ms | 2.6 / 0.5 ms |
| not split out: the 2 × `Release` per re-creation, mip planning, the 96-slot scan | 1.5 ms | **78 ms** |

**Per pass of a heavy frame** (mean of 144 frames):

| pass | draws | lookups | new | no slot | refetch | re-create | ms total | create ms | decode ms |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2,048 | 19,025 | 61 | 209 | 6 | 51 | 61.0 | 28.0 | 7.1 |
| 2 | 2,048 | 22,528 | 74 | 3,067 | 10 | 61 | 59.1 | 28.6 | 6.6 |
| 3 | 2,048 | 20,971 | 83 | 267 | 76 | 72 | 77.4 | 34.8 | 15.0 |
| 4 | 587 | 5,260 | 8 | 0 | 8 | 8 | 10.7 | 4.6 | 1.9 |

## 4. Each suspected cause against the evidence

| Suspect | Evidence | Verdict |
|---|---|---|
| per-pass cache reset | the reset only clears "bound this pass". 63,935 of 67,783 lookups hit a slot already bound; a re-checked texture costs one sparse checksum (79 per frame, 0.22 ms) | not the cost; required (a texture may change between passes) |
| **slot-table capacity** (96) | 96/96 bound in passes 1–3; 227 evictions, 193 re-creations, 3,542 binds with no slot per frame | **the cause** |
| repeated SRV creation | 227 per frame, 0.5 ms; follows the evictions | consequence, small |
| repeated snapshots / hashing | checksum 0.22 ms; `[tex-snapshot-stats]` total 0.18 ms per frame (T154) | no |
| descriptor heap exhaustion / rollover | the SRV heap is statically partitioned (slots 1..96, RT, zeta, per-draw windows); no rollover path | no |
| redundant descriptor-table construction | per-draw window writes are not in `vp_upload_tex_slot` (the 208 ms is all inside it) | not this cost |
| texture/RT aliasing, feedback | RT-sampled units resolve to the offscreen-RT SRV before `vp_upload_tex_slot` is called | not this cost |
| resource-state tracking | copy + barriers 2.6 ms per frame | no |
| recording / submission synchronisation | every pass starts with `wait_for_gpu()`; GPU fence wait about 0 (T153/T154) | no |

- **Are the evictions needed for correctness?** No. They exist only because the table is full.
  - The textures are unchanged: 0 stale checksums in the heavy frames.
  - The no-slot binds lose texturing, which is an accuracy defect.
  - What *is* needed: re-checking (checksum) a kept texture at its first bind in a pass, re-uploading it when it changed, and replacing a slot only while the pass being recorded does not reference it. All of these are kept.
