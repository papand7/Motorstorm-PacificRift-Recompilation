# Bink playback scheduler (original PPU code)

Scope: the intro movie (`GUI_INTRO_EU.BIK`, 29.97 fps: FrameRate 30000 / FrameRateDiv 1001, 3159 frames, one audio track).

Sources:
- `generated/decrypted/EBOOT.elf`, read with `generated/analysis/dis.py`;
- existing listings `generated/analysis/dis_5c4a40.txt` and `dis_bink.txt`;
- the four saved runs (lsfwd, av2, beat, texsnap).

The Bink library is at `0xC5D000`–`0xC74000`, with its own TOC `0x10CE894`. The game reaches it through cross-TOC stubs at `0x757E78`–`0x757F98`.

Labels:
- **VERIFIED NATIVE** — read from the original instructions.
- **VERIFIED RUNTIME** — seen in a saved trace.
- **SUPPORTED HYPOTHESIS** — consistent with the evidence, not proven.
- **UNKNOWN** — not established.

## 1. Call graph

| Address | Role | Status |
|---|---|---|
| `0x5C4A40` | Movie player per-frame update (game code) | VERIFIED NATIVE |
| `0x5C65DC`–`0x5C668C` | Decode loop inside it | VERIFIED NATIVE |
| `0xC6C770` (stub `0x757F48`) | `BinkWait`: non-zero means "not time for the next frame yet". The loop exits to `0x5C6550` and the current frame stays up. | VERIFIED NATIVE (control flow); internals summarised only |
| `0xC70318` (stub `0x757F58`) | `BinkDoFrameAsyncWait(bink, -1)`: waits for the in-flight SPU decode. It polls through helper `0xC735E8`, which sleeps with `sys_timer_usleep(10)` (`0xC73694`); the helper returns to `lr 0xC704EC`. | VERIFIED NATIVE; the usleep is VERIFIED RUNTIME (ftrace `USLEEP` spans, lr `0xC704EC`) |
| `0xC6ED28` | `BinkNextFrame`: advances the frame counter, re-checks lateness, and runs the resync | VERIFIED NATIVE |
| `0xC70540` (stub `0x757F68`) | `BinkDoFrameAsync(bink, 0, 0)`: starts the SPU decode of the next frame (Bink taskset `0x0135D080`, one task) | VERIFIED NATIVE / RUNTIME |
| `0xC6F088` (stub `0x757F78`) | `BinkShouldSkip`: returns 1 if the frame just decoded must not be shown | VERIFIED NATIVE |
| `0xC70798` | `RADTimerRead`: ms since its first call, from `sys_time_get_system_time` (`0xCC011C`) | VERIFIED NATIVE |
| `0xC6CC40` | Sound pause/resume (`bink`, `0`=pause / `1`=resume). On this port it reaches `cellAudioPortStop`/`PortStart` on port 1. | VERIFIED NATIVE (call sites); VERIFIED RUNTIME (Stop/Start pairs) |
| `0xC6E200`–`0xC6E254`, `0xC6EA88` | `BinkOpen` sets `+0x2C8` and `+0x114` | VERIFIED NATIVE |

Decode loop (`0x5C65DC`):

```
if (BinkWait(bink)) return-to-game;           // too early: keep the shown frame
loop:
    BinkDoFrameAsyncWait(bink, -1);           // block until frame N decoded
    BinkNextFrame(bink);                      // N -> N+1, lateness/resync
    BinkDoFrameAsync(bink, 0, 0);             // start decoding N+1 on the SPU
    if (BinkShouldSkip(bink)) goto loop;      // frame N is NOT drawn
render + flip frame N
```

**VERIFIED NATIVE:** a skipped frame is fully decoded and then not drawn. Skipping saves the PPU render and the flip, but not one SPU cycle of decode.

## 2. State (offsets into the `BINK` struct)

| Offset | Meaning | Status |
|---|---|---|
| `+0x08` / `+0x0C` | Frames / current frame number (`ShouldSkip` returns 0 when the current frame is at or past the last) | VERIFIED NATIVE |
| `+0x14` / `+0x18` | FrameRate / FrameRateDiv (30000 / 1001) | VERIFIED NATIVE (read with `mulli 1000` and `divdu`) |
| `+0x114` | Number of open sound tracks (loop over `+0x118`, stride 384) | VERIFIED NATIVE |
| `+0x118`→`+0x3C` | 16.16 playback-speed factor, set to `0x10000` (1.0) at open (`0xC6E24C`) | VERIFIED NATIVE |
| `+0x2B4` | Frame counter | VERIFIED NATIVE |
| `+0x2C0` | Epoch: `RADTimerRead` value at the reference frame (0 = re-arm on next use) | VERIFIED NATIVE |
| `+0x2C4` | Frame number at the epoch (`+0x2B4 - 1` when armed) | VERIFIED NATIVE |
| `+0x2C8` | Skip threshold = `2000 * FrameRateDiv / FrameRate` ms = 66 ms (66.7 truncated to an integer), or 2000 when the rate is 0 (`0xC6EA88`) | VERIFIED NATIVE (`0xC6E20C`–`0xC6E214`) |
| `+0x330` | Resync count | VERIFIED NATIVE (`0xC6EEDC`–`0xC6EEF4`) |
| `+0x334` | Per-frame cached `ShouldSkip` answer (`0`=not computed, `1`=show, `2`=skip). `NextFrame` clears it. | VERIFIED NATIVE |
| `+0x338` | Resync request flag | VERIFIED NATIVE |
| `+0x33C` | Total skipped frames | VERIFIED NATIVE |
| `+0x340` | Consecutive skips | VERIFIED NATIVE |
| `+0x344` | Cleared whenever the epoch is re-armed | VERIFIED NATIVE (role UNKNOWN) |

## 3. Lateness (`0xC6F158`–`0xC6F1A0`, mirrored in `NextFrame` at `0xC6EF90`–`0xC6EFD8`)

```
now      = RADTimerRead()                                        // ms
expected = ((+0x2B4 - +0x2C4) * 1000 * FrameRateDiv / FrameRate) * speed16_16 >> 16
lateness = (now - +0x2C0) - expected                             // signed ms
```

- The epoch is armed lazily: when `+0x2C0 == 0`, `ShouldSkip` and `NextFrame` set `+0x2C0 = now` and `+0x2C4 = +0x2B4 - 1` (`0xC6F138`–`0xC6F150`, `0xC6F010`–`0xC6F028`).
- **VERIFIED NATIVE:** the audio position is never read. Lateness compares host-derived wall time with a frame count. Nothing forgives accumulated lateness except the two epoch re-arms below.

## 4. Skip rule (`BinkShouldSkip`, `0xC6F088`)

1. It returns 0 (show) when any of these hold:
   - `bink == 0`;
   - `+0xEC != 0`;
   - `+0x114 == 0` (no sound track, `0xC6F0B4`);
   - `+0xF8 == 0`;
   - the current frame is at or past the last;
   - `+0x334` already says "show".
2. Otherwise it computes the lateness. If `lateness < 0` or `lateness <= +0x2C8` (66 ms), it shows the frame (`+0x334 = 1`).
3. Late, with no sound track (`+0x114 == 0`): it re-arms the epoch to now (`0xC6F1C4`–`0xC6F1D0`) and shows. A silent Bink never skips; it slips.
4. Late, with sound:
   - if `lateness > 725`, it sets `+0x338 = 1` (resync request) (`0xC6F1D8 cmpwi r9, 725`);
   - if `+0x340 > 2` (`0xC6F1EC cmplwi r11, 2`), it sets `+0x340 = 0` and shows. This is the fourth frame;
   - otherwise it increments `+0x340` and `+0x33C`, sets `+0x334 = 2` and `+0x110 = 1`, and returns 1 (skip).

**Result (VERIFIED NATIVE):** while lateness stays above 66 ms, exactly three of every four decoded frames are skipped. The 4:1 ratio is a constant of the library, not a measurement.

## 5. Resync (`BinkNextFrame`, `0xC6ED28`)

- `NextFrame` repeats the same lateness test (`0xC6EF90`–`0xC6F078`), including the 725 ms check and the skip counter.
- With `+0x338` set (`0xC6ED98` → `0xC6EED8`):
  1. clear `+0x338`; increment the resync count `+0x330`;
  2. `0xC6CC40(bink, 0)`: sound pause (port 1 `PortStop`);
  3. **wait for the IO buffer**: loop `while ((+0x198 * 29) >> 5 > +0x19C)` calling the IO callback `+0x160` (`0xC6EF00`–`0xC6EF3C`). It runs until the read-ahead buffer is about 90 % (29/32) full;
  4. `+0x2C0 = 0` and `+0x344 = 0` (`0xC6EF4C`–`0xC6EF50`): the **epoch is cleared**, so lateness restarts from 0 at the next frame;
  5. `0xC6CC40(bink, 1)`: sound resume (`PortStart`).
- **VERIFIED NATIVE:** a resync resets the video clock. It does not seek audio and does not drop decoded frames.

## 6. Enter, stay and exit conditions

| Transition | Condition | Status |
|---|---|---|
| 1:1 → 4:1 | lateness > 66 ms at `ShouldSkip`/`NextFrame` | VERIFIED NATIVE |
| Stay in 4:1 | lateness stays > 66 ms. Skipped frames still cost full decode, so lateness changes at `1000 − decode_fps × 33.37` ms/s whatever the skipping. | VERIFIED NATIVE; VERIFIED RUNTIME (decode rate in 4:1 stretches equals the run's decode rate) |
| 4:1 → 1:1 by catch-up | lateness falls to 66 ms or below, which needs decode > 29.97 fps sustained | VERIFIED NATIVE; VERIFIED RUNTIME (3 catch-ups in texsnap at 30.2–31.1 fps) |
| 4:1 → 1:1 by resync | lateness > 725 ms, then sound pause, IO-buffer wait, epoch cleared, resume | VERIFIED NATIVE; VERIFIED RUNTIME (inferred resyncs equal the PortStop/PortStart pairs in all runs: texsnap 7, beat 18, av2 10, lsfwd 0) |
| No skip at all | no open sound track (`+0x114 == 0`): the epoch slips instead | VERIFIED NATIVE (not exercised by the intro) |

## 7. Unknowns

- `BinkWait` (`0xC6C770`) internals beyond "non-zero means wait". It also reads `+0x2C0`/`+0x114` (`0xC6C7B4`–`0xC6C934`), so it may re-arm or shift the epoch on pause paths. UNKNOWN.
- The roles of `+0xEC`, `+0xF0`, `+0xF4`, `+0xF8` and `+0x344`. UNKNOWN; they gate the rule but are constant during the intro (SUPPORTED HYPOTHESIS: the skip rule is active for the whole intro, since 4:1 stretches occur throughout).
- The guest event used before buffer reuse (see `UPSTREAM_INTEGRATION.md`, texture lifetime). UNKNOWN.
