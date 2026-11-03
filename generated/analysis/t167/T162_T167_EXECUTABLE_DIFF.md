# T167: T162 A1 against T167 A1 executables

| | T162 A1 (worked) | T167 A1 (failed) |
|---|---|---|
| SHA-256 | `5098e7e31f8dd17f…c8573` | `b2a720e243ecd297…5b6ae` |
| ps3recomp | `69489f2` | `8a12a61` |
| Recipe | `port-t161`, PPU staging lift, WWS AOT, Havok `--chain-chunks` | same |
| Added env | `RSX_GPU_PROF=60` plus arm A settings | `RSX_WAIT_DIAG=1`, `RSX_SHADER_COMPILE_DIAG=1`, `RSX_GVF_ASYNC=0` |

`git diff 69489f2 8a12a61` touches three runtime files, one new header, and tests. **Nothing under SPURS, syscalls, memory, file I/O or the PPU/SPU runtime changed.** VERIFIED.

## Every runtime change, with fetch off

| Change | Effect in arm A |
|---|---|
| `vs_compile_async.h` included; `s_vca` static | Unused data |
| `gvf_async_on()` | Not called: `s_vs_gvf && gvf_async_on()` stops at `s_vs_gvf == 0`. No queue, no thread |
| `vca_query`, `vca_submit` | Not reached |
| `present_interval()` | One `getenv`, one log line, value 1 as before |
| `wdg_now`, `GetCompletedValue`, `wdg_blocked` around fence waits | Two extra timer reads and fence reads per wait; a line per wait of 20 ms or more, at most 4,000 |
| `s_wdg_present_end` | One timer read per Present |
| `rsc_diag_frame`, `rsc_compile_diag` | One value per frame, one line per real compile; 25 lines in A |
| Decompiler `input_mask`, `[loop]`, `[branch]` | Only in the fetch path |

Async compilation was **disabled in arm A**, and its implementation is inert when disabled. VERIFIED from source. The opt-in claim is backed by reading each path, not only by the flag, and by the diff not reaching SPURS at all.

One limit: this compares source. Link layout and compiler output differ, and the binaries were not diffed. The SPURS collapse in one of one run with this exe doesn't exclude a rare interaction, which is why the next plan repeats it and the guard rejects a collapse.
