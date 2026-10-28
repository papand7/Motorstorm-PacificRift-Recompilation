# Original intro skip: analysis (offline, 2026-10-23)

No MotorStorm launch was made. Sources: `generated/decrypted/EBOOT.elf` and the original
`MS2.PSARC` (read-only; pages extracted privately under `generated/analysis/gui/`).
Helpers: `generated/analysis/introskip_probe.py`, `psarc_manifest.py`, `gui_strings.py`,
`gui_page_events.py`, `gui_slot_survey.py`.

## Result

The intro is skippable by the original frontend script, not by the movie player.

| Finding | Label |
|---|---|
| The intro plays on GUI page `introvideo` (`/gui/introvideo.gui`, layout `introvideo.lyt`). Its widget `hBGMovie` runs `VideoStart(currentWidget, gui/gui_intro_EU.bik)`, and its update handler runs `VideoIsFinished(currentWidget)` → `TransitionPage(black)`. | VERIFIED (original page data) |
| The page has one input handler: slot **+0x4C** → `TransitionPage(black, Undefined)`, with no condition and no delay test. | VERIFIED (original page data) |
| Slot **+0x58** runs `PlaySoundEvent(Next_Page)`, `ExecuteFunction(SetIntroVideoSeen)`, `ExecuteFunction(PlayGameMusic)`. It is the page-exit handler, run on both paths. | VERIFIED (data); "exit" role SUPPORTED HYPOTHESIS (24 pages: pop/reset/cleanup actions) |
| Slot +0x4C is the GUI **Accept** input. Across all `.gui` pages in `MS2.PSARC` it is used by 61, always for select/confirm (`Select`/`Next_Page` sounds, forward transitions). +0x48 is Back (87 pages: `TransitionBack` + `back` sound), +0x5C Start (pause), +0x50 per-frame update, +0x54 page enter. | SUPPORTED HYPOTHESIS (consistent data; the slot dispatcher was not located in code) |
| Accept is Cross. `controlconfigs.xml` defines `PressAccept` as "the 'Accept' button (GUI)". The game has `IsAsianButtonMode`, and reads `CELL_SYSUTIL_SYSTEMPARAM_ID_ENTER_BUTTON_ASSIGN` (0x112, `0x4382A4`). The runtime answers `CROSS`. | SUPPORTED HYPOTHESIS (the Accept→Cross resolution is not traced in code) |
| Both paths converge. Skip and natural end both run `TransitionPage(black)`. `black` waits 0.1 s, runs `SetFirstGarageVisit(True)` and `SetGarageType(false)`, then goes to `loadscreen-garage` (or `mainmenu`). `loadscreen-garage` enter runs `GotoGarage`, `PrepareLoadingScreen` and `FirstGarageVisit`. | VERIFIED (data) |
| `black` and `loadscreen-garage` have no Accept handler, so a held or late Cross does nothing there. | VERIFIED (data) |
| Start, Circle and other buttons do nothing on the intro page. It has no +0x48 (Back) or +0x5C (Start) handler. | VERIFIED (data) |
| `BinkShouldSkip` (`0xC6F088`) is frame scheduling only. It is not a movie-level skip. | VERIFIED (earlier) |

**Availability:** the Accept handler has no `GetDisplayedTime`/`TestFinishedIntro` gate, so by
the data it applies whenever the page processes input. Whether the GUI ignores input during the
page's intro animation is **UNKNOWN**.

**Press vs held:** the GUI acts on Accept as a press (`PressAccept`). Edge vs level detection in
code is **UNKNOWN**. A single press/release covers both.

## Movie lifecycle (static, from earlier work and this pass)

- **Player:** `0x5C4A40`, with the decode loop at `0x5C65DC`–`0x5C668C`. It lives in the GUI module, TOC `0x10AFBE4`, which also holds the action-name table (`0x10AA988`: `ExecuteFunction` … `VideoStart`, `VideoStop`, `VideoIsFinished`) and the movie names (`0x10AA908`: `gui/gui_intro_EU.bik`, …, `BinkMoviePlayer open failed`, `OpenMovieAsyncTask`).
- **Teardown:** the movie teardown `0x5C6DB4` → Bink teardown `0xC6BFF0` are reached when the widget/page is left. The exact caller on page exit is still **UNKNOWN** (not traced). The skip uses whatever the page exit does on the natural path; nothing is called directly.
- **Natural completion:** `VideoIsFinished` in the widget update. Its implementation (frame ≥ frames, or a Bink EOS flag) is **UNKNOWN**. No frame-skip branch is treated as EOS.
- **Concurrent with the intro:** FIOS/PSARC streaming, glyph atlas, Bink audio/IO threads (from earlier runs). There is no new finding here.

## Native input (audit of `ps3recomp-int/libs/input/cellPad.c`)

- **XInput:** A→Cross, B→Circle, Start→Start.
- **Keyboard fallback** (port 0, only with no XInput device, only while the game window has focus): Z→Cross, X→Circle, Enter→Start.
- **Polling:**
  - The game's pad thread (`0x72ADF0`) polls `cellPadGetInfo` + `cellPadGetData` for 7 ports into a 20-entry ring.
  - The native side re-polls the host every 4 ms and hands out one change packet per host report.
  - It is independent of Bink.
  - Focus loss releases keyboard keys. XInput is not focus-gated.
- **Result:** a person can already try the skip with A (pad) or Z (keyboard).

## Not verified, next targeted step

Locate the GUI slot dispatcher (input → slot) and the Accept→Cross resolution in code. A bounded
runtime check is cheaper: the proposed validation run (see `INTRO_SKIP_VALIDATION.md`).
