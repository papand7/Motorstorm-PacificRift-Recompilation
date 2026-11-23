## pcmenu: GUI ExecuteFunction / SetTranslatedText internals (2026-11-05)

Static only. No launch, no build, no git, nothing written outside `generated/analysis/pcmenu/`. Private (contains game symbol names and addresses).

Input: `generated/decrypted/EBOOT.elf`. "GUI module" code uses TOC `0x10AFBE4`; main-module code calls it through TOC-switch trampolines `std r2,0x28(r1); addis/addi r2; b target` (e.g. `0x753218` → `0x597190`).

Helpers (in `pcmenu/tools/`):
- `gdis.py <start> [end|fn] [gui]`: disassembly that resolves trampolines and annotates TOC strings.
- `regtable.py`: register/stack tracker over init `0x19CB0`. Writes `../regtable.txt` (883 registrations).
- `thunk.py <regex>`: maps a registered OPD → PMF thunk → real member function (`../examples.txt`).
- `sigs.py`: summarises the 25 dispatcher cases (`../sigs.txt`).
- `actions.txt`: the 74 action names.
- `g_options-*.txt`: decoded option pages (`t30/frontend/graph.py`).

### 1. Name → function resolution

**Registration (VERIFIED)**
- `0x19CB0(this)` is the frontend function-table init. Its single caller is `0x61D8C` (in `0x60D70`).
- It loads `{name, OPD}` pairs from the TOC into stack slots. It then calls one of 24 main-module wrappers `0x1E6620..0x1E6E08` (stride `0x58`) as `wrapper(handle, name, &{this, OPD})`.
- The loop runs over 4 GUI-manager handles, `this+0x5C[0..3]` (`r26`, `cmpdi r26,4` at `0x2A5BC`). So every function is registered 4×, once per manager. 883 names in total.
- Each wrapper does `mgr = 0x59CFD0(handle)` and then calls a GUI-side register function. There is one per signature: `0x596490, 0x596630, … 0x597190 (bool()), 0x597EA0 (void(string)), 0x5974D0 (int(string)), 0x599B90 (void()), 0x5B2900`, … (full list in `regtable.py`).
- No other code calls these (whole-binary `bl` scan). Native registration exists only in `0x19CB0`.

**Container (VERIFIED)**
- There are 25 Dinkumware `stdext::hash_map<const char*, Functor>` maps per manager, at `mgr+0x855C + 0x28*sig`, for sig = 0..24.
  - Map layout: `+0x08` list end node; `+0x14` bucket vector; `+0x20` mask; `+0x24` maxidx.
- Hash: `h=0; h = h*5 + (signed char)c`. Bucket = `h & mask`; if `>= maxidx`, subtract `(mask>>1)+1` (linear hashing).
- Within a bucket, keys are ordered with `strcmp` (`0x6F98D8`). Insert uses e.g. `0x9D9690`.
- Node layout: `+0 next`, `+4 prev`, `+8 key` (the pointer is stored, not copied), `+0xC this`, `+0x10 OPD`.
- Sig 11 (`+0x8714`) has no registrations.

**Lookup (VERIFIED)**
- `0x594C10(out, mgr, name)` probes the 25 maps in a fixed order.
- It returns `out = {&node->this (functor ptr), sigIndex}`.
- Its only callers are:
  - the page-load resolver `0x598458` (ExecuteFunction/AndWait case of `0x598058`). It stores the result at action `+0x5C/+0x60`; action size is 100 B, and the name is at `+0x20`.
  - the runtime retry in dispatcher `0x59DF7C`.

**Unknown name (VERIFIED)**
- `0x595E50..0x595FA4` adds the name once to a debug `vector<string>` at `0x12CB7C0+0xC`. It returns `{0, 666}`.
- At run time, interpreter `0x59F2F8` (ExecuteFunction case `0x59F690`) sees the null functor (`0x59F6F8` → `0x5A86E0`) and copies the name inline into arg-record 0.
- The dispatcher `0x59DC60` then:
  1. looks the name up in a per-manager cache map at `mgr+0x54`;
  2. on a miss, calls `0x594C10` again;
  3. caches the result;
  4. since `sig > 0x18`, returns without calling anything (`0x59DCD8` → `0x59DCE0`).
- So an unknown function is a silent no-op, and `currentReturnValue` is left unchanged.

**Calling convention (VERIFIED for the cases below; full signature table PARTIAL)**
- The dispatcher is `0x59DC60(mgr, &slot->retval, argRecs, &action->func)`, with jump table `0x59DE44`.
- The call is `OPD(this, args…)`, with `r3 = this`.
- Each OPD entry is a pointer-to-member thunk (e.g. `0x772140`) that jumps to the real member function.
- GUI args are 68-byte records (`stride 0x44`). Record `k ≥ 1` has the arg `char*` at `+4`. Conversion depends on the signature:
  - bool: `stricmp(arg,"TRUE")==0` (`0x6FA700`)
  - int: `strtol`
  - float: `strtod`
  - `std::string`: a temporary built by `0x785C68`, passed by pointer
- Return value: an any-like value at `slot+0x24`, which is `currentReturnValue`.
  - `+0` holds the kind: 0 void, 1 `std::string`, 2 float, 3 int, 4 unsigned, 5 bool, 6 `const char*`.
  - Per-kind holder pointers follow, e.g. float `+0xC`, int `+0x10`, bool `+0x18`. Each holder is `{vtbl, value@+4}`.
  - bool is written with `0x9C5D10`. `std::string` is returned via sret and stored with kind 1.
- TestBoolean (`0x5A28A8`) and SetChannelValue (`0x5A399C`) read `slot+0x24`. SetTranslatedText reads it too when its arg is `currentReturnValue`.

**Signature table (sig: C type, example)**
- 0: `void()` — ProfileSave
- 1: `void(int)`
- 2: `void(bool)` — SetFirstGarageVisit
- 3: `void(bool,str)` — SetBoolOptionValue
- 4: `void(int,str)` — SetOptionValue
- 5: `void(str)` — **IncreaseOption**/DecreaseOption
- 6: `void(str,str)`
- 7: `void(str,str,str)`
- 8: `void(str,bool…)` — SetDimmed (PARTIAL)
- 9: `float()`
- 10: `float(int)`
- 11: unused
- 12: `int()` — GetFocusWidgetTextID
- 13: `int(str)` — **GetOptionValue**
- 14: `int(int…)`
- 15: LoadScreenGrab
- 16: `bool()` — **UsingWidescreenDisplay**
- 17: `bool(int)`
- 18: `bool(str)`
- 19: `bool(str,str)`
- 20: `bool(bool,str)` — **GetBoolOptionValue**
- 21: `string()`
- 22: `string(int)`
- 23: `string(str)` — GetStringOptionValue
- 24: `const char*()` (kind 6)

**Worked examples (VERIFIED)**

`profile = *(this+0xDAD0)`. Values are stored as strings: GetInt `0x255EA0` uses `"%d"`/`strtol`, SetInt is `0x255348`, GetBool `0x255B80` uses `"TRUE"/"FALSE"`.

| Name | thunk → impl | Behaviour |
|---|---|---|
| IncreaseOption(key) | `0x772140` → `0x16F68` | `v = GetInt(key, default 0)`; if `v <= 99`, `SetInt(key, v+10)`. The step and limit are hard-coded for all keys and not clamped (95 → 105). |
| DecreaseOption(key) | `0x7720D8` → `0x16FE0` | if `v > 0`, `v-10`, not clamped. |
| GetOptionValue(key) | `0x771E98` → `0x17058` | returns int (kind 3). |
| GetBoolOptionValue(default, key) | `0x771F78` → `0x14F40` | `0x255B80(profile, key, &b, default)`. The script calls it as `(True, options.horizontalsplit)`. |
| UsingWidescreenDisplay() | `0x76F728` → `0x18280` | returns `0x437FA8() > 4/3`. `0x437FA8` returns 16/9 if `[0x12AAA90]+0x13 == 2`, otherwise 4/3. |
| SetDisplayOption() | `0x77D528` → `0x106A0` | an empty `blr`, a no-op in retail. |

### 2. Hook point for new native functions

1. **Recommended: miss path of `0x594C10` (VERIFIED as the single choke point).**
   - Wrap it: call the original, and if `out[1]==666` and the name is in the host table, return `{ptr to persistent guest {this, OPD}, sig}`.
   - This covers both page-load resolution and the runtime retry. The result is cached in `mgr+0x54` and in action `+0x5C/+0x60`, so the functor memory must stay valid.
   - Existing dispatch and `currentReturnValue`/TestBoolean semantics are reused unchanged.
   - It needs a guest OPD whose entry is serviced by host code.
2. **Alternative (VERIFIED mechanism): register after `0x19CB0` returns.** After `0x61D8C`, for each handle in `this+0x5C[0..3]`, call the matching wrapper (e.g. `0x1E68E0` for `bool()`, `0x1E6C50` for `void(string)`). The name string and functor must live in persistent guest memory, because the key pointer is stored, not copied.
3. **Last resort: dispatcher `0x59DCD8`, when `sig==666`.** The name is inline at `argRecs+0` and the args are at `argRecs+0x44*k+4`. The host would have to write the any-holder layout itself, which is more fragile.

### 3. SetTranslatedText and literal text

**Action table (VERIFIED)**

`0x5C8244` fills `std::string[74]` at `0x12CBB20` from TOC `0x10AA988`. See `actions.txt`:
- 0 ExecuteFunction, 1 ExecuteFunctionAndWait
- 2 TransitionPage, 3 PushPage, 4 TransitionPageFromUpdate
- 5 PopPage, 6 PopPageFromUpdate, 7 PopSpecific
- 8 TransitionBack, 9 TransitionBackMultiple, 10 TransitionBackToPage
- 11 TestBoolean, 12 TestFinishedIntro, 13 TestFinishedExtro, 14 TestInequality, 15 TestIfStringsEqual
- 16 MapValueWithFCurve, 17 SetChannelValue, 18 MapAnimationChannel, 19 MapExtroAnimationChannel, 20 MapGainFocusAnimationChannel, 21 MapLoseFocusAnimationChannel
- 22 GetIntroAnimLength, 23 GetExtroAnimLength, 24 GetUpdateAnimLength
- 25 TestIfSelected, 26 GetTimeSinceLastInput, 27 GetDisplayedTime
- 28 SetVisible, 29 SetInVisible, 30 SetDimmed, 31 SetNotDimmed, 32 SetSelectable, 33 SetNotSelectable
- 34 ResetDisplayTime, 35 SetBitmap, 36 KillPageThreads, 37 PopulateTable, 38 PopulateSpinner
- 39 VideoStart, 40 VideoStop, 41 VideoIsFinished, 42 VideoSetLooping, 43 VideoSetVolume
- 44 GetVisible, 45 SetTranslatedText, 46 PlaySoundEvent, 47 TestIfIntsEqual
- 48 DoGainFocusAnimation, 49 SetWidgetActive, 50 GetDimmed, 51 GetSelectable
- 52 SpinnerNextColumn, 53 SpinnerPrevColumn, 54 DoingGainFocus, 55 ResetWidgetPosition, 56 DoLoseFocusAnimation, 57 DoingLoseFocus
- 58 ScrollText, 59 ScrollTextReset, 60 SelectActiveCell, 61 SpinnerNextRow, 62 SpinnerPrevRow
- 63 GetPageOpacity, 64 SetDynamicTableCellHilight, 65 ClearDynamicTableCellHilight
- 66 ScrollTextClamped, 67 SetLoLight, 68 SetMenuSelection, 69 SetTexCoordMask
- 70 ScrollTableUp, 71 ScrollTableDown, 72 ScrollTextResetIfLonger, 73 SetOverrideSelectionColour

There is no SetText action. Channel names (TOC `0x10AAAB0`):
- rotate 0, translatex 1, translatey 2, scalex 3, scaley 4
- **text 5**, visibility 6, masklimit 7
- red, green, blue, alpha, colour

**SetTranslatedText (VERIFIED)**
- Interpreter case `0x5A168C`. The id is either `strtol(arg,10)` (`0x5A64D0`) or the int conversion of `currentReturnValue`.
- For each target widget with `+0x64 == 0`, let T = `widget+0x84`. It sets `T+0 = id`, frees the literal buffer `T+0xC` and sets it to 0, then calls `0x574CC0` (scroll reset) if the id changed.
- Text is resolved lazily when drawn (`0x5BA4E0`): if `T+0xC` is set, the literal UTF-8 is converted by `0x551550` (UTF-8 → UTF-32). Otherwise:
  1. `idx = 0x5898B8(table, id)` (binary search);
  2. `0x58A198(table, wbuf, 0x7800, idx)`.
  The result is `"TEXT NOT FOUND."` for an unknown id.
- The string table singleton is `0x5898B0()`, which returns `0x12CB774`.
  - Layout: `+0 count`, `+4 file buffer`, `+8 entries {u32 id, char* utf8}` (sorted by id; offsets relocated to absolute pointers at load), `+0xC string data`, `+0x10 decimal char`, `+0x14 font set ("asian"/language)`.
- The loader is `0x589B10(table, langName)`. It builds `sprintf("gui/text_%s.lang")` (string at `0xE2ED58`). The file comes from `MS2.PSARC` (not extracted here).
- Callers of the loader: `0x2AA7C`, `0x47664`.
- Other readers:
  - `0x58A218(id)` returns a `char*` (71 main-module callers, e.g. the `Get*Text` functions).
  - `0x589918(table, idx)` (21 callers).

**Best hook for custom strings (HYPOTHESIS, design based on VERIFIED code)**
- After `0x589B10` returns (at both call sites), rebuild the guest table: allocate a new entry array containing the original entries plus the new `{id, utf8 ptr}` entries, keeping it sorted, then update `+0 count` and `+8 entries`.
- Every reader (GUI draw, `0x58A218`, `0x589918`) then sees the new ids with no code hooks.
- Overriding the functions instead would need 4 functions (`0x5898B8`, `0x589918`, `0x58A198`, `0x58A218`), and `0x58A218` inlines its own search.
- Use ids that do not collide with existing ones; choose them only after reading `count` at run time.

**Literal strings (VERIFIED from data and code)**
- The scripts already do `ExecuteFunction(GetLocalPlayerName)` → `SetChannelValue(currentReturnValue, W, text)`.
- The text channel (`0x58C12C`) allocates a 128-byte buffer at `T+0xC` (`0x58E100`) and copies the converted string into it. The copy bound is not verified.
- A literal first argument to SetChannelValue is parsed with `strtod` into a float (`0x5A6600`). So literal text cannot be passed directly; a native `string(...)` function (sig 21/23) or `const char*()` function (sig 24) must provide it through `currentReturnValue`.
