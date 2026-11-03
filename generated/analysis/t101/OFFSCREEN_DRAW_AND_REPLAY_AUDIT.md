# T101: offscreen draw loss and early-replay audit (2026-10-27)

**Result:**
- The `position_attrib_disabled` drops are **valid draws that the backend rejects (class B)**. They go only to depth-only/shadow targets, so they are **unlikely to explain a completely black display on their own** (HYPOTHESIS).
- Early replay preserves the displayed image in every modelled case, with one exception: a **proven latent defect in the offscreen-RT pool across an early replay**. Whether it was hit in T98 is unknown.

Offline only: no build, no launch, nothing merged or pushed.

## Ownership
- **Sessions:** `ListAgents` shows one peer, motorstorm01-21. It is T99 (finished), not T100. No live T100 session exists, so surface identities could not be exchanged; they are recorded below for T100.
- **Worktree:** `ps3recomp-t101`, branch `agent/t101-offscreen-draw-audit`, from T96I `95a906d`, the exe that T98 ran.
  - Commit **`5cb0181`** (tests only).
  - In this tree T96 `c7e84e3` is `667ce4e` and `bd09877` is `95a906d`.

## 1. `position_attrib_disabled`: classification B (valid draws rejected)
- **Producer (VERIFIED):** six identical gates, `if (!state->vertex_attribs[0].enabled) → DA_R_POSITION_ATTRIB_DISABLED`, in `rsx_d3d12_backend.c`:
  - `upload_quads_vp` `:8318`, `upload_tris_vp` `:8352`, `upload_strip_vp` `:8518`;
  - `upload_quads_vp_indexed` `:8614`, `upload_tris_vp_indexed` `:8655`, `upload_strip_vp_indexed` `:8873`.
  - There is no other producer.
- **What "disabled" means (VERIFIED):** `enabled = (size != 0)` (`rsx_commands.c:292-317`). The FORMAT word is `type[3:0] size[7:4] stride[15:8] freq[31:16]`, and PSGL/libgcm write `0x00000002` (size 0) into unused slots.
- **RSX semantics:**
  - An attribute whose array is off feeds its `SET_VERTEX_DATA4F_M` constant register (`0x1C00+16i`) to every vertex.
  - The vertex program, via `VERTEX_ATTRIB_INPUT_MASK` (`0x1FF0`), decides which inputs it reads and which output is the position.
  - Nothing makes attribute 0 special for array draws.
  - The backend already implements the constant rule (`rsx_fetch_attrib`, `rsx_vertex_fetch.c:29-38`), and the VP path fetches all 16 inputs the same way (`read_vp_vertex`, `:8180`). The attr0 gate is the only thing that drops these draws.
  - Label: VERIFIED by code reading; there is no documented RSX rule to the contrary.
- **Outcome on RSX for each case:**
  - **Program does not read v0:** the draw renders real geometry; the backend loses it (**B**).
  - **Program reads v0 while its array is off:** every vertex gets one constant position, giving zero-area triangles that cover nothing. Dropping such a draw changes no pixels (A-equivalent).
  - T98 did not log the input mask, so the split between these two cases is **C, not yet classified**.
- **The rejected draws in T98 (VERIFIED from logs):**
  - all are prim 6 (triangle strip), indexed, with 20–43 indices, fp `0x022C23C1`, and a 128-byte vertex program (8 instructions);
  - the first event was before the race (flip 2109, `rt=0x0B030000`);
  - all 19 periodic `last_drop` samples in the race are `rt=0x00ED0000`, `display=0`;
  - **161,429 race drops** (162,235 − 806 before the race) over 368 guest frames, about **440 per guest frame**, against 657,764 recorded callbacks.

## 2. What the dropped draws feed
- **The drop's `rt=` is `surface_color_offset[0]`** (`da_account`, `:9627`). In T98 both values equal zeta surfaces (VERIFIED, stderr):
  - `0x0B030000` = zeta surface 0, **1024×2048**;
  - `0x00ED0000` = zeta surface 1, **1280×720** (`SetTile` index 2, pitch 10240).
- **Pass type:** the colour offset aliases the depth surface, so these are **depth-only passes** (colour target NONE). PARTIAL: `color_target` was not logged.
  - HYPOTHESIS from the dimensions: `0x0B030000` is a shadow map (for example two stacked 1024² cascades), and `0x00ED0000` is the main-view depth or Z pre-pass.
- **Sampled later (VERIFIED):** `0x00ED0000` is read as a texture (`depth surface 0x00ED0000 read as A8R8G8B8: converted 1280x720`, 4 lines), for example by fog, soft particles or depth of field. Whether `0x0B030000` is sampled is not logged.
- **Impact (HYPOTHESIS):**
  - Missing depth-only geometry produces missing shadows, wrong depth-based effects, or (with a Z pre-pass and an EQUAL depth test) missing objects.
  - It does not remove colour-pass draws, and the HUD would still draw. The T98 dumps are **zero in every sampled byte**. That points at the composition or display path (T100's scope), not at these drops.
  - The 20% aggregate is **not** evidence of the black screen.

## 3. Early replay (T96 `c7e84e3` + `bd09877`): findings

| Item | Result |
|---|---|
| Colour/depth attachments | **Backbuffer and shared DSV** are kept: the host clear is skipped when `keep_targets` is set (`:6693`). **Zeta surfaces and offscreen RTs** are persistent resources and are not cleared at replay entry. The shared DSV is still reset at RT switches with no zeta surface (`:6969`), as before T96. VERIFIED |
| Barriers, pipeline state | Each replay is a self-contained command list, drained at entry (`:6102`). Nothing carries over unrecorded. VERIFIED (T97) |
| Vertex/index data, order | Parity flip after a drain; a one-queue order; partial-triangle carry. VERIFIED (T97, strict 15,429/0) |
| RT bindings, texture descriptors | Rebuilt per replay from the records. **Defect below.** |
| Present eligibility | `vp_flush` forces `s_present_this_frame = 0`. All three gates OR in `flushed_display`. An offscreen-only or empty remainder still presents. VERIFIED by the model (test 7) |
| Pending GPU reads | `wait_for_gpu` at every `render_frame` entry. VERIFIED |

- **DEFECT (proven in the model; runtime impact unknown): an offscreen RT can be evicted between an early replay and the draw that samples it.**
  - **Mechanism:**
    1. Every replay resets the pool's `used` marks (`:6385`).
    2. It then marks only the RTs its own records target.
    3. `off_rt_get` evicts the first slot not `used` in this replay (`:3822`).
  - **Result:** an RT written before the cut and only sampled after it is evictable. It is released, and the sample reads nothing. Within one `render_frame` this cannot happen. Early replay makes it possible inside a guest frame.
  - **Precondition:** all 32 `MAX_OFF_RTS` slots allocated. T98 cannot show whether that happened: eviction is not logged outside RSXI, and there was no `render-target pool full` line.
  - **Repro:** test 9 (pool of 2): RSX shows 1070, one replay shows 1070, early replay after R1 shows −3 (source lost).
  - **Smallest correction (proposed, not applied):** at `:6385`, reset `used` only when the replay starts a new guest frame (`keep_targets == 0`). Test 9 passes with this rule. An alternative is to also mark RTs that records sample.
- **Measurement correction to T98 (VERIFIED, pinned):**
  - The frame dump (`:7486`) and `[rsx-hb] frames` run on **every** `render_frame`: early replays and offscreen-only batches as well as Presents.
  - T98's "frames keep presenting" therefore holds for render passes, not counted Presents. The 35 black dumps are a mix of presenting and non-presenting passes.
  - With 25-pass spacing and passes of 2–3 per guest frame, both kinds were sampled, so the all-black result stands (PARTIAL).

## 4. Independent tests (`5cb0181`)
- **Files:**
  - `libs/video/tests/test_t101_offscreen_replay.c`;
  - `tools/test_t101_pins.py`;
  - runner `t101/tools/run_t101_tests.cmd`.
- **Result: PASS, 34 checks, 0 failed; pins 7/7** (logs in `t101/logs/`). The public-source audit of both files passed. The baseline `audit_public.py` lives in the parent repo; the files were audited with `--tree`.

| # | Test | Expected from | Result |
|---|---|---|---|
| 1 | Attribute off + DATA4F constant | NV4097 encoding, real `rsx_process_method` / `rsx_fetch_attrib` | constant read for every vertex |
| 2 | Indexed, mixed on/off | same | per-index array values, constants for off slots |
| 3 | VP input mapping | input mask 0x2 reads no constant, so RSX draws it | **backend drops it (class B)** |
| 4 | RT switching across replays | ideal-RSX op model, every 1- and 2-cut placement | matches |
| 5 | Offscreen → post → display | same | matches |
| 6 | Clears between partial submissions | same | matches |
| 7 | Present after replay (offscreen-only or empty remainder) | same | matches |
| 8 | Many submissions, 2 guest frames (records-full 1..7) | same | matches |
| 9 | RT pool across early replay | same | **95a906d loses the RT; proposed fix keeps it** |

- **Limit:** tests 4–9 model `render_frame`, `off_rt_get` and `d3d12_present`. They do not run them; the pins catch drift. The `vp_flush.h` state machine is the real header.

## 5. Minimal runtime evidence (needs authorization; same exe)
Use one bounded launch, with captures at the first presenting race pass and one later presenting pass.
1. **Backbuffer just before Present, presenting passes only**, with `CLEAR_RGB=1,0,1`:
   - magenta means the display was never drawn;
   - black means something drew black.
   - Note: the existing dump cannot select presenting passes. `CELLMARK_DUMP` timing is by pass, so it needs a one-line gate on `s_present_this_frame` (a diagnostic build), or accepting mixed samples.
2. **`RTT_SAVERT=<composite source RT>`**, the surface T100 identifies. This tells "scene present, composition broken" from "scene missing".
3. **The A8R8G8B8 image of zeta `0x00ED0000`**, to see whether race geometry reaches depth despite the drops.
4. **Diagnostic counters only:**
   - per-drop `color_target` and `VERTEX_ATTRIB_INPUT_MASK` for `position_attrib_disabled` (first N);
   - an off-RT eviction count;
   - Presents per guest frame.
   Items 1 and 4 need a diagnostic-only build; items 2 and 3 use existing knobs.

## Remaining uncertainties
- Whether the dropped programs read v0 (class B versus A-equivalent per draw).
- Whether `0x0B030000` is sampled.
- Whether the RT pool is ever full in the race.
- Whether race frames contain any display (`rt_off == 0`) draw at all. That belongs to T100's trace.

## Commits
- `5cb0181` (T101 tests, on `95a906d`). Not merged or pushed.
- No production code was changed.
