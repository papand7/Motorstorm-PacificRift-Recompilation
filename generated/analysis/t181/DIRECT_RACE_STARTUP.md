# T181: direct-to-race startup

Status: **PARTIAL. Static analysis plus an off-by-default hook; never run.** Skipping menus does not fix loading: the 85-90 s (poll) or 20-22 s (wake) from load screen to race remains and is measured separately. The saving is only the frontend, from about 20 s (wake) to about 37 s (poll) before the load screen.

## A. Native selection

| Route | Evidence | Selection | Verdict |
|---|---|---|---|
| Existing state-based pad route | Used by the race runs: 4 CROSS, confirmed by guest page loads and function hits, no screen coordinates | None; `Track1a` | VERIFIED, use for the matrix |
| Retail config boot | Static, below | Track from `benchmark_*`; vehicle only as the config says | HYPOTHESIS, needs arms S and T |
| Direct guest calls (`SetSelectedTicket` 0x338C0 etc.) | Functions known; never tried; needs frontend objects alive | Full, in principle | Not attempted, more invasive |

**Config boot, verified statically:**

- `func_00061984` loads the literal `configs/ms2_config.cfg` (VA `0xDF8170`, TOC slot `0x0109AD4C`) and passes it to the parser `func_002009F0`.
- The parser still matches the config type against the table at `0x1031300` (RACE, COMMANDLINE_RACE, GUI, BENCHMARK and 14 more), so the retail parser is live.
- The caller compares the stored result with 0x11, the index of `GUI_FOCUSDAYTESTING`, just before `0x00061DF4`, so at least one consumer exists. **Other consumers are untraced, so whether BENCHMARK or RACE still starts a race is unknown.**
- The archive holds 37 config members, including 16 `benchmark_*.cfg` and `skill_race.cfg`.

**Implemented:** `PS3_DEV_GUEST_STR=<slot>:<expected>:<replacement>` (`00f76bcc`, `include/ps3emu/dev_guest_str.h`, `runtime/ppu/ppu_loader.cpp`). It repoints the one slot before entry after checking the expected string, so all init still runs and no guest code changes. Other lifted reads of that TOC offset are a float load and two functions in another code region (HYPOTHESIS: a different TOC). `--dev-race` isn't added: the port's `main.cpp` is shared `port-t161`, and the variable does the same job.

**Limits:** off unless set, but compiled in unless `PS3_NO_DEV_TOOLS` is defined, and the current build does not define it, so a normal build must define it. That falls short of the brief's "disabled in normal builds" until a release build does so. Benchmark configs change options and use a camera path, so their frames may not match a real race and can't replace the pad route for FPS claims.

## B. Warm caches

| Cache | Finding | Status |
|---|---|---|
| Shader, `RSX_SHADER_CACHE=3` | Exists: bytecode plus D3D12 pipeline library, keyed by content, compiler, adapter and driver, in a versioned directory. Saves at most the 2.85 s of misses, projected load about 17.6 s | Arm W measures it |
| FIOS `cache.dat` | **A warm cache can't occur today.** The runtime clears on a new id and the game also calls `SysCacheClear` (`libs/system/cellSysutil.c`). T178's "W twice on one HDD copy" would not be warm. Grows 459 MB to 1.94 GB per session | BLOCKED; retention changes guest-visible behaviour |
| Texture, geometry | No persistence found | Not pursued |

## C. Checkpoint

**Not feasible** (T161 §5, VERIFIED from the design). Guest call stacks are host frames inside AOT code, so no instant has all ~28 threads at a resumable point, and SPU, SPURS, D3D12, file and timer state can't be restored. It would need continuation-style lifting or an interpreter, which `AGENTS.md` forbids. So 2-5 s repeat loads have no path.

## Proposed test (needs authorization)

Arms S (`benchmark_happyJungle`) and T (`skill_race`): 2 launches, no pad route, 60 s stall stop. Success: race entry reached with no crash. Each failure costs one launch and shows that config does not start a race this way.
