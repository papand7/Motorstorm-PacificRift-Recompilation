## T41: main-menu initialisation and fade (2026-10-26)

Offline only. No launch, no build, no code change, no commit.

Inputs:
- T36 run `generated/runs/20261026-061327-t36-first-race` and `t36/FIRST_RACE_ENTRY.md`.
- Retail EBOOT disassembly (`generated/analysis/dis.py`).
- msre / T38 call graph (`Motorstorm01/t36-worktree`).
- T30 GUI decoder (`t30/frontend/graph.py`).

Helper scripts and dumps: `t41/scratch_a/` (code path) and `t41/scratch_b/` (log and RSXI analysis).

Note: the GUI code addresses globals through TOC `0x10AFBE4`, not `0x109FBF0`. That is why earlier `xref.py` searches missed it.

### Summary
- **Hypothesis "fade-in never reaches the input threshold": REFUTED as stated (VERIFIED).**
  - Main-menu page opacity is an idle-dim value, not an intro fade.
  - It starts at 1.0, drops only after 30 s without input to that page, and reaches 0 at 33 s.
- **Best-supported explanation: the mainmenu page is not the input-controlled page, so it never receives real pad input (HYPOTHESIS, strongly consistent).**
  - Its idle timer then runs from the moment it loads.
  - At the CROSS, 18 s after load, opacity was still 1.0, so the gate would pass. That press therefore most likely never reached mainmenu.
  - By the capture, 42 s after load, opacity is 0. Since page opacity multiplies every widget's alpha, all widget draws are submitted but invisible, which is exactly what T36 captured.
- **Root cause: not established.** It is unknown why mainmenu lacks control after the garage → `SetConfigGUIPage(mainmenu)` path, and no emulator defect is proven. So there is no fix and no commit.
- **Separate defect (PARTIAL):** text glyphs are invisible in both the garage and the menu, while icons and bars draw. This is unrelated to the menu hang.

### 1. GUI state machine (original code)
**Action binding (VERIFIED):**
- `0x5C8244` builds a 74-entry table of action names; the index is the action type. Examples:
  - ExecuteFunction 0, TransitionPage 2, PushPage 3, TestBoolean 11, TestInequality 14, MapValueWithFCurve 16, SetChannelValue 17, MapAnimationChannel 18, GetTimeSinceLastInput 26, SetVisible 28, GetPageOpacity 63, SetMenuSelection 68.
- Resolver: `0x598058`. `0x58A8F8` stores the action type at action+0x40; arguments go through the switch at `0x598104`.
- Interpreter: `0x59F2F8`, switch `0x59F430`, jump table `0x59F44C`. Cases:
  - GetPageOpacity `0x5A0318`, TestInequality `0x5A3618`, SetChannelValue `0x5A399C`, MapAnimationChannel `0x5A3878`, GetTimeSinceLastInput `0x5A2824`, PushPage/TransitionPage `0x5A2FC8`, SetVisible `0x5A274C`, SetMenuSelection `0x59FFA8`.
- Scheduler: `0x5B2520` runs slots of 68 B starting at mgr+0x7C, up to 50 steps per slot per frame. Slot fields: +0x14 page, +0x18 widget, +0x24 return value. `QueueHandler` is `0x59D7A8` (r4 page, r5 widget, r6 handler).

**Frame driver `0x1F7560` (VERIFIED):**
- dt comes from `sys_time_get_system_time` (stub `0xCC011C`) through `0x435F28` and `0x434D00`; f31 holds it at `0x1F7710`.
- It walks the page-stack entries (loop `0x1F7B48`; entry+0x74 = page). For each entry:
  - +7 == 0: timers advance, but no handlers run.
  - +6 == 1 and mgr+0x250 set: `PageUpdate` with real input (`0x1F8A00`).
  - only +5 == 1: `PageUpdate` with zeroed input (`0x1F8934`, also `0x1F8704`).
- While any extro runs, input is blocked (`0x1F7B14` clears mgr+0x250).

**`PageUpdate 0x57EA38` (page r4, input r5, dt f1) (VERIFIED):**
- `0x57EAA4`: P+0x68 (time since input) += dt.
- `0x57ECB4`: P+0x6C += dt.
- `0x57ECFC`: P+0x68 = 0 if any input byte 0..0xF is non-zero.
- It then queues button handlers, then the page update handler (`0x57F024`).

**Mainmenu page (`mainmenu.gui`) (VERIFIED):**
- Enter handler (`+0x2C4`): `SetAudioMixStateGUI`, `GameTypeReset`, `PushPage(invitation-popup, Undefined, False)`, `OnlineOnline`, info text.
- Update handler (file +0x50 = `0xD8`), every frame:
  1. `MainMenuMotorStoreGuard`
  2. `GetTimeSinceLastInput` (reads P+0x68 at `0x5A7174`)
  3. `MapValueWithFCurve(Fade)`
  4. `SetChannelValue(visibility)`, which writes the page opacity
  5. `GetTimeSinceLastInput`
  6. `TestInequality(Undefined, 90)`: if ≥ 90 s, `TransitionPage(attractvideo)`.
- Items: `Main_menu` (type 9) has
  - THE FESTIVAL, Accept `0x367C`;
  - WRECKREATION `0x3A6C`;
  - GARAGE `0x3F5C`;
  - OPTIONS `0x437C`;
  - MOTORSTORE `0x48FC`, ungated.
  - The page's own Back/Accept slots are null.
- Festival Accept: `GetPageOpacity` → `TestInequality(Undefined, 0.5)` → GE branch → `PlaySoundEvent` → `GameTypeSetFestival 0x76AF40` → `TransitionPage(festivalguide)`.
- Widget visibility: init slot (`0x575260`) and intro slot (`0x575280`); `MapAnimationChannel` intros last 0.333 s (P+0x84) on the widget clock widget+0x1C (`0x5C1010`). GainFocus/LoseFocus switch the highlight art.

### 2. Fade hypothesis
**Opacity (VERIFIED):**
- Variable: float at page+0x74, initialised to 1.0 from the .gui header (`0x5BF6D0`, store `0x5BFF4C`).
- Only writer: `SetChannelValueImpl 0x58B7B0`. With a null widget and channel 6, it writes `clamp(v, 0, 1)` via fsel at `0x58B9D8` / `0x58B9FC`. NaN clamps to 0.
- Readers: draw `0x5BB28C`, GetPageOpacity `0x5A0338`, and the copy constructor.

**How it changes per frame (VERIFIED):**
- `opacity = Fade(P+0x68)`. The `Fade` curve sits at file offset `0x58E0` with keys (1, 0 s), (1, 30 s), (0, 33 s). Key order was verified from evaluator `0x5798A8`; linear interpolation is a HYPOTHESIS.
- So opacity is 1.0 until 30 s without input, below 0.5 after about 31.5 s, and 0 from 33 s.

**What stops it reaching ≥ 0.5 (VERIFIED):**
- no real input reaching this page for more than 31.5 s, or
- a broken dt (a NaN or very large dt pushes it to 0).

**Threshold (VERIFIED):** `P+0x74 >= 0.5`, inclusive. TestInequality takes the GE branch at `0x5A3850`; on failure the handler ends silently (`0x5A5038`).

**Other gates on Accept (VERIFIED):**
- the menu widget is focused (flag scan +0x68 bit 0x8, `0x57EB2C`);
- the selected item is valid (`0x5C0320`, item+0xC != −1);
- input byte 6 is set (`0x57F5E0`), which queues item+0x94 (`0x57F9FC`);
- the page is the controlled one (+6).

**Do the logs show the threshold was never reached? No.**
- No opacity values were logged.
- From the curve and the timing: at the CROSS (72.65 s host, about 18 s after load) opacity should be 1.0, unless dt is broken. The gate is therefore not the likely reason that press was ignored.

### 3. Alternatives, using T36 logs and RSXI (scratch_b)
| Check | Result | Status |
|---|---|---|
| Menu init / item data | `0x536A30` loads black → mainmenu (326 ms) → invitation-popup; all r3=0; no later page loads. `gui_b.bik` opened, AutoSave2 completed, 0 non-zero HLE returns, no fs failures. | VERIFIED |
| UI resources | Font atlas `0x04E88580` (2048×1024, B8) is bound. Bars and icons use the same textures as the garage, where they show. | VERIFIED |
| Callbacks / events | No unsupported, NOSYS or stub lines between 54 s and 96 s. | VERIFIED |
| Guest clock | About 63 frames/s; `0x3BFA0` runs once per frame (+632 per 10 s); bink decodes in real time; no fc-watchdog report. dt values were not logged. | VERIFIED / dt PARTIAL |
| RSX | Captured frame f004569: 19 widget draws (ops 22–40) are submitted with the same fp/vs/blend state as the garage. The backbuffer differs from the bink RT only by video motion. | VERIFIED |
| Draw alpha | Page opacity multiplies into every widget's alpha (`0x5BB28C` → `0x5B4620`, child `fmuls` at `0x5B476C`). Opacity 0 → every widget draws transparent. | VERIFIED (code) |
| Input routing | `PushPage(invitation-popup, Undefined, False)`: "False" leaves the control name empty (`0x5A9BF8`, `0x5A7C44`), so the popup gets +6=0 and mainmenu keeps its flags. The popup has no SetPageControlled / PopPage. | VERIFIED |
| Garage contrast | The garage Accept uses `PushPage(quit-confirm1, Undefined, True)`, which gives control to the popup (`0x1F6334`) and clears the garage page (`0x1F699C`). This is why CROSS reached Yes. | VERIFIED |
| How mainmenu gets +6 after `SetConfigGUIPage` | Not traced. Candidates: a `TransitionPage(mainmenu)` (`0x1F5ED8` → `0x1F6334`), or restore/activate `0x1F44C8` (+7=+6=1 at `0x1F4B74/78`; 22 callers). | BLOCKED (offline) |
| Text glyphs | Invisible in the garage too (B8 remap `0x56FF` suspected). | PARTIAL, separate |

**Logic or rendering?** The rendering pipeline works for these assets. The missing pixels are explained by guest logic setting alpha to 0 (idle dim), which depends on input not reaching the page. This is a logic- or input-routing-level failure, not a backend rendering fault. The exception is text, which is a separate rendering bug.

### 4. A–E status and minimal trace plan
| Case | Status now | Deciding hooks (one run) |
|---|---|---|
| A: fade never progresses | Refuted as an intro fade. Possible only with a broken dt. | `0x1F7710` (f31 = dt), `0x57EAA4` (P+0x68), `0x58B9FC`/`0x58B9D8` (opacity write) |
| B: fade done, items absent | Ruled out: items are drawn. | none needed |
| C: items exist, not rendered | Explained by opacity 0, not the backend (except text). | `0x5BB28C` (f1 at draw) |
| D: renders, but input disabled / not routed | **Leading hypothesis.** | `0x1F8A00` (r4 = page with real input), `0x1F8934`, `0x57ECFC` (timer reset), `0x57F5E0`, `0x57F9FC`, `0x5A3850`/`0x5A5038` |
| E: init never completes | Unlikely: the update handler must run for the dim to apply. | `0x59D7A8` (r6 = `0xD8` handler), `0x5B25B4` |

**Control-flag writes** (log the entry and its page name, entry+0x74 → page +0x88 name): `0x1F4B78`, `0x1F5EF4`, `0x1F6334`, `0x1F699C`, `0x1ECEC8`, plus `0x5A9BF8` (arg3 compare) and `0x1F7B14` (extro block).

**Recommended future run:**
- About 12 hook sites from the list above, `limit=64`, `sample=pow2`.
- Press CROSS at about 5 s and about 25 s after mainmenu loads, before the 30 s dim, and capture at about 10 s.
- One extra check is worth considering: press any button at 35 s and see whether the widgets reappear (expected only if input reaches mainmenu).
- The PT tracer currently supports fn/ret/hle hooks. Mid-function sites (e.g. `0x1F8A00`) need `ret=`-style site hooks; check that they exist in hooked staging before planning.

### 5. Fixes and tests
None. No defect is proven offline:
- The control-flag mechanism, opacity curve and draw alpha are original guest logic behaving as designed.
- The open question (why mainmenu has no control, if that is the case) needs the trace above. If that trace shows dt as the cause, the suspect is host `sys_time_get_system_time` / timer behaviour, which should be checked in a focused offline test before any change.
- No frontend or renderer code was edited, so no owner coordination was needed.
