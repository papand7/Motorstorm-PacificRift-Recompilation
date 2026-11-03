# T157: what limits each scene after the texture fix, and what to do next

2026-10-29. Labels: VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED. Data: `HEAVY_SCENE_AB_RESULTS.md` (T155's 4 launches, run by T157). Target: 30 FPS = 33.3 ms per guest frame, **in each scene separately**.

## 1. Where each scene stands

| | light (race start) | heavy |
|---|---|---|
| best measured | 19.78 FPS, 50.5 ms (Ar1, fast host); 14.4–14.7 after the host drift | **7.44–7.60 FPS, 128–132 ms (Br1, `RSX_TEX_SLOTS=1024`)** |
| gap to 33.3 ms | −17 ms (−34 %) | −98 ms (−75 %) |
| critical path | **PPU frame thread.** The RSX thread is busy 29.5 ms and idle 21 ms, with no RSX throttle (0.6 ms). Havok wait 18.6 ms (T156: lifted solver + collide execution) | **RSX frame-clock thread**, busy 111 of 132 ms; the PPU waits 35.6 ms for it (reference throttle) |

Heavy, RSX thread under B, per guest frame (VERIFIED):
- vertex expansion **67.3 ms**;
- in-drain replays plus `render_frame` 48 ms. Of the recording's 34.4 ms: commands 15.4, PSO lookup 11.4, textures 7.5;
- FIFO walk and other callbacks ≈ 10 ms.

Uploads: 414k vertices and 101 MB per frame, which is 244 B per vertex. The compact layout is 64 B per vertex; the fat layout is 256 B.

## 2. Top three opportunities

| # | Opportunity | Measured contribution | Removable (estimate) | Correctness risk | Complexity | Radeon 890M | Independence |
|---|---|---|---|---|---|---|---|
| **1** | **Heavy-scene vertex expansion and upload** (RSX thread) | 67.3 ms per heavy frame (VERIFIED), plus 101 MB per frame of upload writes | 30–50 ms (HYPOTHESIS). (a) At 244 B per vertex the game's draws mostly take the 256 B fat path: `RSX_VP_COMPACT` covers only indexed strip/fan draws, and T151 found fat expansion write-bound. (b) The 4 passes' draws are independent CPU work and could be expanded on worker threads in guest order | medium: byte-exact vertex records, checked by the existing RSXI harness sets | medium–high | high: 101 MB per frame of CPU writes to upload memory costs UMA bandwidth | RSX only; T156 untouched |
| **2** | **Make the 1,024-slot cache correct** (exact re-check, `RSX_TEX_CACHE=1`) **and bound its memory** | removes the stale-atlas regression; keeps the 216 → 5.6 ms texture win (VERIFIED in game for the win, offline for the fix) | the win itself; the exact hash costs +0.9 ms per synthetic heavy frame (3.5 → 4.5 ms, `tools/harness/t157/perf_texcache.sh`, 3 repeats). In game it depends on the bytes hashed (HYPOTHESIS: a few ms) | low with exact hashing (8/8 identical, partial writes included) | low (existing switch) | needed: about 1 MB per kept texture, so a byte budget beats a fixed 1,024 count | RSX only |
| **3** | **Havok / Wws SPU execution** (the light scene's limit) | Havok wait 18.6 ms per light frame (31–32 ms after drift); heavy Wws spin 25 ms; `renderablejob` 147 ms of SPU time per heavy frame | light: the 17 ms gap is about the Havok wait. T156 found only 0.3–0.45 ms removable by thread pooling; the rest is lifted SPU code speed | medium (SPU codegen) | high | scales with core count (fewer, slower cores make it worse) | T156 workstream |

Not chosen:
- **PSO lookup and command recording** (27 ms per heavy frame) are real but second order. T151 found 6–8 re-scans of fragment-program ucode per lookup; worth taking after #1.
- **GPU work** is not visible: the GPU wait is about 0 everywhere.

## 3. Texture memory: count vs budget

- **Measured.** B kept about 233 textures for about +143 MB of GPU memory and +127 MB of private memory, about 1 MB per kept texture. Each slot holds its texture and its own upload buffer, which is sized to the decoded texture and kept for the slot's lifetime.
- **Upper bound.** At 1,024 slots and the same mean, the cache would use about 0.9 GB (+ upload). On a Radeon 890M with shared system memory that is too much to assume.
- **Recommendation** (needs measurement first, not implemented):
  - release or pool the upload buffers once their copy has completed. The GPU is idle at every pass start, so this is safe at that point. It roughly halves the footprint;
  - then a byte budget (for example `RSX_TEX_BUDGET_MB`) with the same "not bound in this pass" LRU rule.

  The heavy working set (≈ 220 textures) is well below any reasonable budget, so no new eviction policy is justified yet.

## 4. Recommended next engineering task

**T158: correct the texture cache, then attack heavy-scene vertex expansion.**

1. **Gate (small).**
   - Arm B' = `RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1`.
   - Reproduce and explain the Br2 FIFO desync offline: a FIFO stress test with a long pass at a scene transition. No new game launch for that.
2. **Main.** Measure the heavy scene's primitive and attribute mix, using a read-only counter of draws per fat/compact path, primitive type and indexed/non-indexed. Then:
   - extend the compact record to the paths the heavy scene uses, or
   - expand passes on worker threads.

   Byte-identical RSXI per pass vs the current path, under the debug layer.
3. Keep both opt-in until a game A/B validates them.

## 5. Proposed bounded game validation (NOT AUTHORISED; needs explicit approval)

| Item | Proposal |
|---|---|
| exe | **new** T157 integration exe `build/motorstorm-t157`, sha256 `959ebd3152c100f689ecafbc388e5b90ef3227a763dc14f189a7aa8f065aa629` (ps3recomp `c535cc0`; contains T155 and T156 code, T156 switches off). It is not the T155 exe and has not been launched |
| arms | A = T154 BA environment (as T155 arm A); C = A + `RSX_TEX_SLOTS=1024 RSX_TEX_CACHE=1` |
| order | A → C → A → C, 4 launches, race entry + 90 s, same runner (re-pinned to the new exe) |
| extra capture | one RSXI snapshot set at race entry + 40 s (heavy scene) in each arm, to check the 3,500 dropped binds are repaired and that nothing else changed |
| pass criteria | 4 valid runs, no `FIFO resync`; C's overlay text identical to A's; heavy `noslot` 0 and texture ms < 15; light FPS of C within A's run spread; GPU memory recorded |
| host | the other project's GPU process should be stopped by its owner first. The T157 runs drifted about 25 % after the first run |
