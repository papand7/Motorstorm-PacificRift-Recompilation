# Bink intro frame pacing: measured analysis

Runs: lsfwd, av2, beat, texsnap (all cold cache, same EBOOT).
- Tool: `tools/analyze_bink_pacing.py`.
- Inputs: the per-present timeline CSV (`generated/profile/probe_<run>_vstat.csv`), the run's `stderr.log`/`stdout.log`, ftrace (60–70 s) and the texsnap counters.
- No new run was made. Native rules: `BINK_PLAYBACK_SCHEDULER.md`.

```
py -3 tools/analyze_bink_pacing.py --timeline generated/profile/probe_texsnap_vstat.csv \
   --log generated/runs/20261022-224618-texsnap/stderr.log --log .../stdout.log \
   --ftrace generated/profile/probe_texsnap_ftrace.txt --texsnap generated/profile/probe_texsnap_texsnap.csv --summary
```

## 1. Answer

**28.42 decoded fps gives about 10.5 unique fps because the decoder is slower than 29.97 fps and the native Bink rule never forgives lateness.**

**Step 1 (VERIFIED NATIVE + RUNTIME).** Any stretch that puts the player more than 66 ms (two frames) behind switches it to the fixed 4:1 mode.

**Step 2 (VERIFIED NATIVE).** Skipped frames are still fully decoded, so 4:1 does not reduce the decode load.
- In 4:1, lateness keeps changing at `1000 − decode_fps × 33.37` ms per second, which is +52 ms/s at 28.4 fps.
- The display runs at decode/4 ≈ 7 fps until lateness passes 725 ms.

**Step 3.** Past 725 ms the player resyncs:
- audio port Stop;
- a wait for the IO buffer;
- the epoch is cleared;
- audio port Start.

After the resync it plays 1:1 for about 1.3 s, until lateness reaches 66 ms again.

**Cycle (SUPPORTED HYPOTHESIS, from the closed-form model).** At 28.4 fps one cycle lasts about 14 s:
- about 1.3 s at about 28 fps;
- about 12.7 s at about 7 fps.

That predicts about 9 unique fps. The run measured 10.4 on the timeline (the run-level figure was 10.7), because decode varies across the intro.

**Bottleneck: SPU decode throughput (VERIFIED RUNTIME).**
- The Bink SPU host thread is 96.6 % busy (texsnap thread sampler, 20 s, 200 Hz).
- The PPU main thread is 16 % busy and spends most of that in the decode-wait sleep.
- The host flip/present path takes 7.6 ms (median) from request to present, on another thread.

Host scheduling is not what puts the player late; the decoder runs at about 95 % of real time.

## 2. Measured timeline (texsnap)

| Item | Value | Source |
|---|---|---|
| Intro (first to last decoded present) | 115.8 s, 3158 frames, 27.27 fps incl. resync pauses (runner: 28.42 over frames 256–3072) | timeline |
| Unique frames shown | 1204, 10.4 /s | timeline `content_seq` |
| Presents by decode advance | 1: 467, 4: 640, 2–3: 16, 0: 79, 8: 1 | timeline |
| Time in 1:1 / 4:1 / other | 17.0 s / 89.6 s / 9.2 s | timeline |
| 4:1 stretches of 5+ presents | 10: 7 ended by resync, 3 by catch-up | anchored replay |
| Lateness at the end of resync stretches | 643–771 ms (threshold 725; ±1–2 frames replay error) | anchored replay |
| Decode in catch-up stretches | 30.19–31.08 fps (all > 29.97) | timeline |
| Decode in resync stretches | 26.2–29.2 fps (all < 29.97) | timeline |
| Rule agreement (advance 4 ⇔ replayed lateness > 66.7) | 92.8 % of 1107 presents | anchored replay |
| Audio Stop/Start pairs | 7, plus 1 final Stop before `PortClose` | stdout order |
| Flip requests / presents (ftrace 60–70 s) | 81 / 80, request→present median 7.6 ms, max 12.0 ms | ftrace |
| Texture snapshot | 3609 captures, 501 reuses, 0 fallbacks, 0 torn | sampler |

All four runs follow the same rule. The inferred resyncs match the audio Stop/Start pairs exactly:

| Run | Decode fps (timeline) | Unique fps | Resyncs (inferred / pairs) | Catch-ups | Rule agreement | 4:1 time |
|---|---:|---:|---|---:|---:|---:|
| lsfwd | 28.68 | 17.76 | 0 / 0 | 12 | 91.6 % | 50.1 s |
| av2 | 26.76 | 9.24 | 10 / 10 | 6 | 91.6 % | 94.9 s |
| beat | 25.35 | 7.99 | 18 / 18 | 2 | 93.0 % | 104.8 s |
| texsnap | 27.27 | 10.40 | 7 / 7 | 3 | 92.8 % | 89.6 s |

Correction to the texsnap report: there were 7 resyncs, not 8. The eighth `PortStop` is the end of the movie (it is followed by `PortClose`).

## 3. Part C questions

| Question | Answer | Status |
|---|---|---|
| What makes it skip? | Lateness > 66 ms, i.e. decode completion is behind the frame clock by two frames. Not a late semaphore, not FIFO consumption: skipping is decided on the PPU from the frame count and the time. | VERIFIED NATIVE + RUNTIME |
| Does the playback clock run faster than decode? | Yes: the clock is host wall time, and decode averages 95 % of 29.97 fps | VERIFIED |
| Does one slow frame cause prolonged 4:1? | Yes. Once lateness > 66 ms it only recovers with sustained decode > 29.97 fps or a resync at 725 ms. lsfwd (29.99 fps) stayed in 4:1 for 26.3 s with no resync. | VERIFIED RUNTIME |
| Delay to enter / exit | Enter > 66 ms; exit ≤ 66 ms (catch-up) or > 725 ms (resync) | VERIFIED NATIVE |
| Does skipping catch up? | No: it saves render and flip, not decode, and only stops the display from falling further behind | VERIFIED NATIVE |
| Does audio resync reset the video clock? | Yes: the epoch is cleared (`0xC6EF50`) | VERIFIED NATIVE |
| Decoded frames discarded, or draws declined? | Decoded and never drawn: the loop goes back to `DoFrameAsyncWait` | VERIFIED NATIVE |
| Is the game skipping too aggressively? | No: this is Bink's stock rule (2 frames, 3 skips, 725 ms) running on unmodified code. Nothing shows the translated runtime evaluating it wrongly. | VERIFIED NATIVE |
| What is the >30 fps playback the user saw? | 1:1 stretches after a resync or in a catch-up, when decode briefly runs at 30–33 fps | VERIFIED RUNTIME |

## 4. Host stages (Part E)

| Stage | Cost | Evidence |
|---|---|---|
| SPU decode | about 35 ms per frame at 28.4 fps; thread 96.6 % busy | thread sampler |
| SPU idle per frame (completion seen, next DoFrameAsync issued) | ≤ 3.4 % ≈ 1.2 ms (upper bound for all host-side waiting) | thread sampler |
| PPU notices completion | `usleep(10)` sleeps about 530 µs; mean detection delay 266 µs (p95 509 µs) | `generated/profile/bench/pollwake` (RESEARCH.md) |
| Guest flip request → backend present | median 7.6 ms, max 12.0 ms | ftrace |
| Present cost | 1.82 ms mean | vstat |
| VBlank | 59.96 Hz | vstat |

- In 1:1 the decode of N+1 starts before frame N is rendered, so the render/present delay does not hold up decode (VERIFIED NATIVE loop order).
- Removing every host wait would gain at most about 3 %. Decode needs at least 5.5 % (29.97 / 28.42) just to break even.

## 5. The missing flip (Part F)

**What happened (VERIFIED RUNTIME).**
- The ftrace has a request at 60.863 s (buffer 1) with no `PRESENT` span; the next present came at 61.020 s, after the next request (buffer 0, 61.014 s).
- In the timeline, present 1431 covers two guest flips (`flips` 1393→1395, decoded 921→929) with `new` = 1: one requested frame was never shown.
- Drains kept running every ~4 ms in the gap.

**Mechanism.**
- MotorStorm flips through `_cellGcmSetFlipCommand` (NID `0x21397818`, the only flip import besides `SetPrepareFlip`, which was never called). Every traced request took the direct fallback (`in_fifo` = 0), so the flip is not ordered with its FIFO commands (VERIFIED).
- `frame_clock` (`port/main.cpp`) presents a pending flip before it drains. The D3D12 present then skips the swap-chain `Present` (and the `PRESENT` span) when the recorded batch has no onscreen draw (`has_display` = 0). `last_flip` absorbs the flip either way (VERIFIED code).
- If the frame's onscreen draws were still behind `put` when the flip arrived, that present is consumed without display. The frame is superseded by the next flip's present (SUPPORTED HYPOTHESIS; there is no counter for `has_display` = 0 presents).

**Is it a defect?** On hardware the flip sits in the command stream after its draws, so the RSX would have shown that frame for at least one vblank. This is a host ordering defect, not legitimate coalescing.
- It affects about 1 % of flips (1 of 81). It is not a cause of the 4:1 skipping.
- Which `gcm_flip_into_fifo` condition fails for MotorStorm's context is UNKNOWN.

## 6. Gaps and the smallest extra instrumentation

None of these exist in the saved runs; each is bounded and cheap:
1. A guest-side Bink probe: at `ShouldSkip` return (`0xC6F11C`), log `{RADTimer, +0x2B4, +0x2C0, +0x2C4, lateness, r3, +0x340}` as one CSV row per call (about 3200 rows). This replaces the replay and gives exact lateness.
2. Resync timestamps: one row at `0xC6EEDC`, plus the IO-wait duration (`0xC6EF00` loop exit).
3. `PS3_FT_SPU_BUSY` spans for the Bink taskset, to get per-frame decode start/end.
4. Counters for presents consumed with `has_display` = 0 at a flip boundary, and for each reason `gcm_flip_into_fifo` returned 0.

Each item is a read-only probe at an HLE/hook boundary and does not change guest timing.
