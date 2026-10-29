# T157: T155 `RSX_TEX_SLOTS=1024` game A/B, heavy and light scenes

2026-10-29. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. These are T155's four authorised launches, run here once, A → B → A → B (they had not been run before T157). No other launch.

## 1. Setup (VERIFIED)

| Item | Value |
|---|---|
| exe (all 4 runs) | `build/motorstorm-t155` at ps3recomp `c1512fb`, pinned `t155/ab/exe_f`, sha256 `d8483b4a3ed18907b232ca2e8b18a648980a6f53f860241e5a6ffb6559ef1c6c` (checked against `exe_f.sha256` and the build copy before launch; not rebuilt) |
| environment | T154 arm BA (T153 preset + `PS3_TEX_SNAPSHOT_WWATCH=1` + `PS3_SPU_WWS_STATS` + `PS3_SPU_WWS_AOT=1`) + `PS3_CRITICAL_PATH_TRACE` + `RSX_TEXREC_STATS=1`. A: `RSX_TEX_SLOTS` unset. B: `RSX_TEX_SLOTS=1024` |
| runner | `t155/ab/seq_t155ab.sh` → `run_t155ab.py`; stop at race entry + 90 s |
| runs | Ar1 15:53, Br1 15:57, Ar2 16:01, Br2 16:05 (private logs `generated/runs/20261029-1553..1605-t155-ab-*`) |
| host | another project's `SSX Tricky` (pid 12996, running since 2026-10-27, ≈ 15 % GPU 3D, 0.4 core) and a Godot process (0.65 core) were present throughout, as in the T155 diagnostic. They could not be stopped (not ours) |
| GPU memory | external sampler `t157/tools/gpumem_sampler.ps1` (Windows `GPU Process Memory` counters, every 2 s; passive) |

**Validity.** Ar1, Br1 and Ar2 are valid (race entry + 90 s). **Br2 is invalid for the heavy scene**: at race frame ≈ 541, the light → heavy transition, the FIFO walker logged `FIFO resync (unmapped-JUMP)` at io `0x01AC0FFC`, then the game logged `GcKernel::Present() Timeout!`, and the runner stopped on that line (race entry + 44 s). Br2's light segment (race frames 40–499) completed before this and is used. See §5.

## 2. Frame-matched FPS (race-frame index; `t157/tools/frame_dist_t157.py`, same segments as `t154/tools/phase_match_t154.py`)

Light = race frames 40–499 (≈ 2,085 draws, 1 pass). Heavy = 600–651 for the three valid runs (Ar2 ends at 652), and 600–729 for Ar1/Br1.

| Run | light FPS | light p50 / p95 / p99 ms | heavy FPS (600–651) | heavy p50 / p95 / p99 ms | heavy FPS (600–729) |
|---|---|---|---|---|---|
| Ar1 | 19.78 | 49.5 / 57.8 / 80.4 | 3.29 | 299 / 337 / 338 | 3.26 |
| Br1 | 14.36 | 65.0 / 105.4 / 158.5 | **7.44** | **128 / 159 / 170** | **7.60** |
| Ar2 | 14.73 | 64.5 / 99.3 / 137.7 | 2.35 | 398 / 583 / 608 | — |
| Br2 | 13.23 | 68.7 / 119.3 / 182.0 | invalid | — | — |

- **Heavy scene: B is 2.3–3.2× faster (VERIFIED, one valid B run).** Br1 7.44 FPS vs Ar1 3.29 and Ar2 2.35 over the same race frames. Still far from 30 FPS.
- **Light scene: no effect of the switch (VERIFIED).** The host slowed after Ar1: Ar2 (A) fell to 14.73, in line with Br1/Br2. Light texture time is the same in both arms (1.8 / 1.6 / 2.3 / 1.7 ms), while every unrelated stage got 20–30 % slower in Br1, Ar2 and Br2 (vertex expansion 14.6 → 17.5–18.0 ms, Havok wait 18.6 → 31–32 ms). This is host drift (clocks or the other project's load), not the switch.
- Draw counts per race frame are equal across arms (light median 2,004, heavy 7,049–7,054).

## 3. RSX cost per guest frame (means, `[rsx-frame-perf]`)

| ms per guest frame | light Ar1 | light Br1 | heavy Ar1 | heavy Ar2 | **heavy Br1** |
|---|---|---|---|---|---|
| frame wall | 50.5 | 69.6 | 306.8 | 425 | **131.7** |
| drain (FIFO walk + draw callbacks) | 18.1 | 22.9 | 288.1 | 381.4 | **111.0** |
| ↳ vertex expansion | 14.6 | 18.0 | 53.4 | 62.2 | **67.3** |
| ↳ in-drain early replays (flush) | 0 | 0 | 227.7 | 310.1 | **33.2** |
| render_frame | 11.4 | 20.1 | 243.8 | 351.3 | **48.2** |
| ↳ record | 6.3 | 7.4 | 239.8 | 336.5 | **34.4** |
| ↳↳ texture binding (`tex`) | 1.8 | 1.6 | 218.4 | 310.4 | **7.5** |
| ↳↳ PSO lookup | 1.7 | 2.1 | 9.5 | 11.3 | **11.4** |
| ↳↳ command recording (`cmd`) | 2.8 | 3.7 | 11.9 | 14.8 | **15.4** |
| submit / GPU wait / present | 0.1 / 0.0 / 0.3 | 0.2 / 0.0 / 0.4 | 0.5 / 0.1 / 0.3 | 0.6 / 1.8 / – | 0.7 / 0.1 / 0.4 |
| frame-clock idle (`other`) | 21.1 | 26.7 | 2.5 | 3.4 | 5.7 |
| vertices / upload MB | 104k / 25.4 | 104k / 25.4 | 414k / 101.1 | – / 100.4 | 414k / 101.0 |

(Heavy Br1 here is 600–729; heavy Ar2 is 600–651.)

## 4. Texture cache effectiveness (`t155/tools/ana_texrec_t155.py`, per guest frame)

| | light A | light B | heavy A (Ar1 / Ar2) | **heavy B (Br1)** |
|---|---|---|---|---|
| slots in use at pass end (max per frame) | 84 (82–90) | 84 (82–90) | 96 / 96 | **218 (204–232)** |
| binds with no slot (drawn without the texture) | 0 | 0 | 3,506 / 3,161 | **0** |
| evictions | 0.2 | 0 | 226 / 216 | **0** |
| re-creations | 0.16 | 0 | 192 / 184 | **0** |
| creates / SRVs | 0.17 / 0.25 | 0.02 / 0.03 | 192 / 226 | 0.03 / 0.03 |
| decoded MB | 0.05 | 0.00 | 36.6 / 35.2 | 0.00 |
| texture time (`[tex-rec]` total) ms | 1.4 | 1.2 | 216.6 / 308.5 | **5.6** |
| of which CreateCommittedResource / decode / checksum ms | 0.11 / 0.04 / 0.33 | 0.05 / 0.02 / 0.38 | 101.3 / 31.4 / 0.21 | 0.10 / 0.02 / **1.89** |

- **The working set fits (VERIFIED).** The heavy scene needs ≈ 218 slots (≤ 232 seen, 233 total with light-scene textures), well under 1,024. Its churn is gone: no evictions, no re-creations, no dropped binds. Texture time per heavy frame falls 216 → 5.6 ms (39×).
- The remaining 5.6 ms is mostly the per-pass sparse checksum of the kept textures (1.9 ms) and lookups.

## 5. Correctness findings

**5.1 Regression: stale glyph-atlas text under B (VERIFIED in game, root cause VERIFIED offline).**
- The CELLMARK frame dumps (12 race-start frames per run, light scene) show the "Press ⓧ to Skip" overlay as "re ⓧ t ki" in **every dumped frame of both B runs**, and complete in every frame of Ar1, Ar2 and the T155 diagnostic (montage: private `t157/scratch/skip_text.png`).
- **Cause:** `tex_csum` (the per-pass re-check of a kept texture) reads one 32-bit word every `size/1024` bytes. For atlas shapes it misses 75–98 % of glyph-sized writes (`tools/csum_blindspot_t157.py`: 1024² 8-bit atlas, 32² glyphs: 992 of 1,024 positions never sampled). With 96 slots, the atlas was evicted now and then (light A: up to 28 evictions in a frame), and the re-upload picked up the new glyphs. With 1,024 slots, it is never evicted, so the copy uploaded before the glyphs were written stays.
- **Offline reproduction** (`tools/harness/t157/correct_partial.sh`; new partial-write mode of `test_t155_texslots`, commit `59fcab5`; debug layer on, 0 errors, compared per pass by `t155/tools/cmp_snaps_t155.py`):

  | Case (300 textures, partial rewrites in pass 2) | vs never-reuse reference (`TEX_NOCACHE=1`) |
  |---|---|
  | `RSX_TEX_SLOTS=1024` (T155 arm B) | **4 of 8 passes differ (stale)** |
  | `RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1` (exact hash), + rerun | 8/8 identical ×2 |
  | same, no rewrites | 8/8 identical |
  | 80 textures, default 96 slots / `RSX_TEX_CACHE=1` | 8/8 identical / 8/8 identical |

- So **B as tested breaks "no stale texture reuse" and must not be enabled.** The blind spot exists in the default path too (same `tex_csum`; HYPOTHESIS that it shows wherever a kept texture is partly rewritten). The 80-texture default case did not trigger it.

**5.2 Other visual comparison (PARTIAL).** The dumped frames are not run-to-run deterministic (Ar1 vs Ar2: 0 of 12 identical, 113k–385k of 922k pixels differ; A vs B similar). They are sampled at host times of an animated intro, so pixel equality cannot judge B. Apart from the overlay text, an A and a B frame were visually equivalent. **The dumps do not reach the heavy scene**, so the expected repair of the 3,500 dropped binds per heavy frame is not visually confirmed (BLOCKED, needs a heavy-scene capture).

**5.3 Br2 FIFO desync (HYPOTHESIS: unexplained).**
- This is the first `FIFO resync` line in all 160 run logs under `generated/runs`.
- It happened at the light → heavy transition. In that pass, B creates 165 new textures (227 ms of texture work).
- The words the walker parsed at `0x01AC0FE0..0FFC` differ from the words dumped right after. So the ring memory changed under the walker, which points to a producer/consumer visibility or ring-reuse race.
- Br1 went through the same 165-texture pass (168 ms) without a resync, and A runs survived single passes of up to 755 ms. So a long pass alone does not explain it.
- The texture slot code never writes guest memory or FIFO state, so any link to B is through timing.
- One occurrence in 2 B runs (0 in 3 A runs) is too few to call this either noise or a B regression. It needs an offline FIFO stress test before B' is run again.

## 6. PPU / SPU waits (`t154/tools/phase_sites_t154.py`, ms per guest frame)

| | light Ar1 | light Br1 | light Ar2 | heavy Ar1 | heavy Ar2 | **heavy Br1** |
|---|---|---|---|---|---|---|
| Havok wait `0x30B710` | 18.6 | 31.4 | 32.2 | 20.1 | 29.7 | 31.6 |
| Wws spin `0x50C818` | 1.7 | 1.3 | 1.3 | 25.3 | 25.0 | 25.0 |
| RSX reference throttle `0x72E1E0` | 0.6 | 0.7 | 0.8 | 222.8 | 332.0 | **35.6** |
| Wws jobs / job ms (SPU time) | 207 / 51.6 | 206 / 56.4 | 208 / 56.3 | 275 / 184.5 | 275 / 187.2 | 270 / 186.3 |
| ↳ `renderablejob` ms (SPU time) | 22.9 | 24.8 | 24.9 | 146.2 | 147.6 | 147.3 |

- Heavy B: the PPU still waits 35.6 ms per frame for the RSX (reference throttle). With the RSX thread busy for 111 of 132 ms, **the RSX thread is still the heavy-scene critical path**.
- Light: the RSX thread is idle 21–27 ms per frame. The PPU frame thread is the limit, and its Havok wait (18.6 ms on the fast host, 31–32 ms after the drift) is the largest single wait.

## 7. Memory (VERIFIED, peaks per run)

| | Ar1 | Br1 | Ar2 | Br2 (to failure) |
|---|---|---|---|---|
| GPU dedicated (local) MB | 442 | **585** | 443 | 529 |
| GPU shared (non-local) MB | 33 | 33 | 33 | 32 |
| process private MB (runner) | 1,134 | 1,262 | 1,135 | 1,237 |
| peak working set MB | 688 | 687 | 686 | 677 |

- B adds about 143 MB of GPU memory and 127 MB of private memory for about 137 extra live textures, roughly **1 MB per kept texture**. Each slot keeps its texture and its upload buffer.
- At the measured working set, B's footprint is fine on this RTX 5060. **At the full 1,024 slots, the same rate would mean about +0.9 GB**, which a Radeon 890M takes out of shared system memory. See `NEXT_CRITICAL_PATH.md` §3.
- Live texture resources: about 233 (B) vs ≤ 96 (A).
- Resource churn, B heavy: 0.03 creates per frame vs 192 for A; decoded bytes 0 vs 36 MB per frame.
- Peak allocations beyond the totals above are not instrumented (missing, not zero).
