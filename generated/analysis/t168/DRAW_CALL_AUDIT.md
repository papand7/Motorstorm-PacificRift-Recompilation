# T168: draw call audit

**Result: no duplicate execution was found in any captured race pass. No category D defect is confirmed. The heavy scene has no capture, so it is not cleared.** No game was launched.

Tool: `tools/analyze_dup_t168.py`. Input: the 8 existing game RSXI captures that record FIFO offsets (`tools/survey_captures_t168.py`), 21 captured RSX passes. Totals below are the 18 passes from builds with push-buffer CALLs working (T113, T145). The 3 T84D passes predate that fix and show the same zero results.

## Totals

| Measure | Value |
|---|---|
| Draw records | 13,471 |
| Unique guest draw packets | 6,201 |
| Records that come from libgcm splitting one packet | 7,270 (54%) |
| **Packets executed again** | **0** |
| **CALL return sites entered twice** | **0** |
| **Call sites with an identical packet sequence (a job run twice)** | **0** |
| Packets whose batches don't fit a libgcm split | 0 |
| Candidates: same target, program, state, textures, constants, mesh proxy | 1,427 packets, 2,744 records |
| Candidates using blending | 0 |

**The "draw" counts overstate guest commands.** A `DRAW_INDEX_ARRAY` packet carries many (first, count) words: for example one packet at a single FIFO offset gave 8 batches of 256 indices and one of 133. Each becomes a record. In these passes 2.2 records make one packet. The heavy scene's ratio isn't known.

## Classification

| Case | Evidence | Verdict |
|---|---|---|
| **A. Multipass** | 371 mesh groups appear in more than one target | Legitimate, as far as visible: targets differ |
| **B. Repeated geometry** | 219 groups with same mesh proxy and state, different constants | Legitimate |
| **C. Redundant state** | T159 measured it on synthetic loads: 99.97% of wrapped setters redundant with identical state, about 2% of time | Exists, no draws involved. No game count from T168 |
| **D. Duplicate execution** | 0 replayed packets, CALLs or jobs | **Not found** |
| **Candidates** | 1,427 packets | **Unresolved, not defects** |

## The 1,427 candidates

| Target | Candidate packets |
|---|---|
| `0x0B030000`, 1024x2048 depth target (likely shadow map, per T101) | 1,160 |
| `0x00750000`, main colour pass | 153 |
| `0x00ED0000`, 1280x720 depth | 111 |
| `0x01650000` | 3 |

Why these aren't confirmed:

- Every one sits at its **own FIFO address**. The walker reached each once, so the guest's SPU wrote them separately.
- **The capture can't tell them apart.** RSXI at those builds records neither vertex array addresses, nor `first`, nor constants above c[63]. The mesh proxy is per-batch index and expanded vertex counts. Different patches of a regular grid would match it exactly (HYPOTHESIS).
- FIFO bytes lie between neighbouring candidates (often about 0x88), and the captured state doesn't change across them. Something else does, most likely vertex array offsets (HYPOTHESIS).

Settling this takes the attribute addresses, which `RSX_DRAW_DUP_DIAG` records: `GAME_CAPTURE_PLAN.md`.

## Limits

- Light scene only. Largest captured pass is 967 draws; none covers the 6,900-draw frames.
- No capture holds consecutive passes of one guest frame on a current build, so replay **across** passes within a frame is excluded by source audit and tests, not by traces.
- A packet replayed immediately after itself would merge into one run. The batch-shape check catches this unless its batches are all exactly 256.
- Captures are from T113, T145 and T84D builds, not the latest integrated one.
