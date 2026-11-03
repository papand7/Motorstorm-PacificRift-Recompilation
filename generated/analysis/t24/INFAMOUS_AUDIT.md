# T24: inFAMOUSreborn audit for MotorStorm (2026-10-25)

Read-only audit: no build, no launch, no code change, no merge. Detailed notes, each with file:line evidence:
- `agents/render/notes.md`
- `agents/ppu/notes.md`
- `agents/spu/notes.md`
- `agents/build/notes.md`

## Provenance (VERIFIED)
- **Upstream repository:** `https://github.com/whompay/inFAMOUSreborn` at `2e9405c72408d28f505b6636a2f9cb6b6125aa85` (2026-10-23, 19 commits). Clone: `upstream/repo/`.
- **Vendored ps3recomp:** a single squashed import (`b24300c`), later touched by:
  - `cdb5815`: low-CPU mode;
  - `2a66df5`: SDL3 pad, DLSS, gcm and D3D12 work;
  - `f844b5d`: audio, DualSense, PGO.
  - `2e9405c` only sets `RF_TRIPLE=1` / `RF_EARLY=1` in `installer/infamous.toml`, and that code logs "perf207: no gain".
- **Nearest sp00nznet ancestor:** `a679051` (2026-09-29, PR #205). Of 258 commits in v0.12.1..v0.14.0 it has the fewest differing files (115: 72 modified, 36 added, 7 deleted). Evidence: `vendored_tree.txt`, `cands.txt`, `vendored_vs_a679051.txt`.
- **Our side:** `motorstorm/v0.17-integration` @ `307b08a`, which is v0.17.0 plus our work. Our tree is therefore about 3 weeks *newer* in its common upstream code.
- **Presence check:** `presence2.txt` holds a hunk-level check after CRLF normalisation (`n/b`, `n/v`, `n/o`, `pt/*.diff`).
  - 21 small patches apply cleanly to ours, 4 are already present, and the rest conflict because our code has diverged.
  - None of the 36 added files exists in ours.
  - Every candidate below was checked by reading the code.

## Runtime flags (VERIFIED; all are environment variables set only by the installer, `installer/infamous.toml:256`; none exists in sp00nznet or ours)
| Flag | What it does | Correctness |
|---|---|---|
| `PS3_FAST_HOST` | Checks only that the variable exists, so `=0` still turns it on. Sets ABOVE_NORMAL priority and opts out of EcoQoS for the process; FIFO, render and write-watch threads run at ABOVE_NORMAL (`infamous-recomp/main.cpp:980-988`, `rsx_d3d12_backend.c:11582,14151`). | Host scheduling only. |
| `PS3_FAST_RUNTIME` | Skips diagnostics: PUTLLC/GETLLAR logs, the spin detector, a shared counter, printfs (`spu_channels.c:797-844,1071-1085,1237-1251`; `spu_workload.c:943,978,1365`). | The CAS commit, rollback, reservation notify and locks always run. Safe. |
| `PS3_PCORE` | On unless set to `0`. Restricts threads to P-cores through CPU sets on hybrid CPUs with at least 8 P-core threads, and raises their priority (`ppu_loader.cpp:3858-3916`). Applies to main (HIGHEST), FIFO, VCACHE, audio and SPURS instance 1. | Only priority and placement. Our non-hybrid Ryzen 9600X would get only the priority change. |
| `PS3_SPURS_PCORE` | Off by default. Pins upstream's own SPURS lane-worker pool (`cellSpurs.c:2946-2964,4030-4036,4094-4104`). | That pool has no counterpart in ours. Rank D. |

None of the four enables fast-math, relaxed ordering or skipped checks.

Upstream also compiles lifted SPU code with `-mfma` and default contraction, which it admits fuses `spu_fi` (`infamous-recomp/CMakeLists.txt:612-627`). We must not copy that.

## Findings
### A: directly reusable generic fix
| # | Change (upstream) | Ours | Benefit | Risk | Tests | Size |
|---|---|---|---|---|---|---|
| A1 | `PPU_THREAD_LOCAL` with `require_constant_initialization` (`ppu_context.h:26-31`, `ppu_tls.h:21-26`, `ppu_lifter.py:153-158`; `b24300c`) | Missing (`ppu_context.h:27`, `ppu_tls.h:22`, `ppu_lifter.py:247`). VERIFIED: `ppu_recomp_000.cpp.obj` has 81,548 `__tls_guard` and `__dyn_tls_on_demand_init` relocations. | Removes the TLS guard check from almost every register access in lifted code: CPU time, possibly part of the 75 ms frames. | Clang rejects the build if any variable needs runtime initialisation, so it fails loudly; the generated `ppu_recomp.h` copy must change too. | Build, compare relocation counts, PPU conformance suite. | S |
| A2 | Lifter: switch-base search skips `ld/lwz rX,d(r1)` epilogue restores on tail-call paths (`ppu_lifter.py:3797-3806`) | Stops at that restore (`ppu_lifter.py:4535-4547`), so the jump table is left unresolved. | More switch tables resolved; affects only switches that fail today. | Low. | Re-lift into `generated/`, diff the resolved tables. | S |
| A3 | HLE dispatch caches for NID→index and host→guest (`ppu_hle.cpp:214-292`) | Linear scan per import call (`ppu_hle.cpp:294,722,744`). | CPU only; behaviour unchanged. | Low. | HLE dispatch unit test. | S |
| A4 | Savedata write with NULL buffer and size 0 treated as empty (`cellSaveData.c:673-678`) | Returns a parameter error (`cellSaveData.c:677-680`). | Matches the firmware; no MotorStorm failure seen. | Low. | Unit test. | S |

### B: adaptable; correctness first, then first race
| # | Change (upstream) | Ours | Benefit for MotorStorm | Risk | Tests | Size |
|---|---|---|---|---|---|---|
| B1 | **Guest sampler state per draw** (filter, wrap, border, LOD bias, anisotropy; `SAMP_GUEST/BORDER/PACK`, default on, `rsx_d3d12_backend.c:724,756,776,15669`) | VERIFIED: static samplers, all linear+wrap, s0 point+clamp (`rsx_d3d12_backend.c:1292-1303`). | The garage scene pass samples a 4x1 cascade table, 256x1 and 32x512 lookups and a shadow map. Linear+wrap distorts them. HYPOTHESIS: contributes to the dark garage. | Descriptor-heap churn; upstream's backend layout differs, so reimplement. | Unit test decoding the RSX sampler registers into D3D12 samplers; offline replay of an RSXI garage frame. | M |
| B2 | **Texture gamma (sRGB) / sign-expand** (`TEX_XF`, `rsx_d3d12_backend.c:4348-4400`) | VERIFIED: the D3D12 path calls `rsx_fp_decompile_shadow_ex` without gamma or expand masks (`:2346`), though our own draw engine passes them (`rsx_draw_engine.c:1645-1660`). | The garage u1 is a sign-expanded normal. HYPOTHESIS: wrong N·L, so a dark scene. This mostly reuses our own code. | Shader cache key change. | Decompiler unit test (mask → HLSL), RSXI replay. | S-M |
| B3 | **SPU PUTLLC vs PPU CAS lost update**: PUTLLC commits only the changed words, by CAS (`spu_channels.c:803,1246`) | Same race (code reading, not reproduced). The PPU store-conditional checks `spu_coh_is_reserved` *before* taking the lock (`ppu_loader.cpp:965-980`); if it reads 0 and an SPU then reserves the line, a PPU CAS can land between PUTLLC's memcmp and its full-line memcpy (`spu_channels.c:769-771`). | Removes a lost-update race on job and dependency counters (PLAUSIBLE source of rare hangs). Cleaner fix for ours: re-check the reservation under the lock on the PPU side. | Lock-ordering mistakes; must keep 128-byte atomicity. | New stress test: PPU CAS vs SPU PUTLLC on the same line, counting lost increments. | S-M |
| B4 | **SPURS workload Shutdown / WaitForWorkloadShutdown / Remove** with real states, Remove returning BUSY (`cellSpurs.c:101-336,725,755,1857`) | VERIFIED: Shutdown and Wait are no-ops (`cellSpurs.c:3182-3194`); Remove writes state 3 (`:1608-1630`). MotorStorm imports all three. | The garage → race transition tears down and creates workloads, on the path to the first race. | Do not copy the 5 s forced-removal escape. | Unit test: shutdown with a quantum in flight. | M |
| B5 | **FIFO wake on put-store kick** (`infamous-recomp/main.cpp:211-231`, `ppu_loader.cpp:2245`) | `port/main.cpp:227` uses a flat `Sleep(4)`; `cellGcm_fifo_kick_wait` exists but is unused (`cellGcmSys.c:1744`). | Lower FIFO latency, a likely part of the 75 ms frames (garage run: 1.34 busy cores). | Timing only. | Vblank-clock and beat unit tests. | S |
| B6 | **Real lwcond signal/wait** (`ppu_sysprx.cpp:448-799`) | Signal is a no-op; wait is `Sleep(1)` and ignores the timeout (`ppu_sysprx.cpp:344-371`). | Wake latency of the FIOS and IO workers (HYPOTHESIS: loading gaps). | Keep upstream's 1 ms poll cap; strict mode stalled inFamous' FIOS. | Waiter/signal ordering test. | M |
| B7 | **Depth function / write mask / stencil; per-target colour mask and blend (0x0370/0x036C); feedback snapshot** (`rsx_d3d12_backend.c:3474,3882-3924,4965-5012,7987-8023`) | VERIFIED: LESS_EQUAL with depth write always on when the depth test is enabled, stencil off (`:2630-2641`); target 0's mask mirrored to all targets. | Correct MRT luminance target and passes with depth writes off. | PSO-key growth. | PSO-key unit test, RSXI replay. | M |
| B8 | `usleep` precision: spin ≤50 µs, yield up to 1 ms (`sys_timer.c:247-307`) | About 530 µs for `usleep(10)` (`sys_timer.c:263-313`). | MotorStorm's LockFreeMutex back-off. First try the existing `PS3_USLEEP_SPIN=1`, no code needed. | Host CPU cost. | Timer unit test. | S |
| B9 | GETLLAR poll backoff, EventFlagWait woken by DMA PUT, parked-task wake lock (`spu_channels.c:1086-1175`, `spu_workload.c:928-1000`) | No backoff; flag wait is a 2 ms poll (`cellSpurs.c:2050`). | CPU and wake latency. | Low. | Latency unit tests. | S each |
| B10 | Build: restore the timestamps of byte-identical files after an SPU re-lift (installer `--keep-mtimes`, `main.rs:424-452`); `-w` on lifted SPU sources | Every reconfigure recompiles all 33 SPU files and relinks; 41k warnings. | Faster diagnostic turnaround. | None for the game. | Unit test in `tools/`. | S |

### C: design reference only
- Frame overlap through a separate render thread (`RF_ASYNC`, `rsx_d3d12_backend.c:11578-11706`; ours calls `wait_for_gpu()` every frame, `:5989`). Do it only after timing data.
- Render-target aliasing per format.
- Vertex cache and staging ring.
- PPU/SPU register caching (`ppu_regcache*.py`, `spu_regcache.py`).
- Indirect-call front cache (`ppu_loader.cpp:3026-3190`; must honour our `g_icall_target_set`).
- Out-of-line store fast path.
- HLE and file-read timers (`hz_stats.h`).
- Affinity-aware thread sizing.
- PGO probe.
- Frame cap through a store-watch hook (`infamous_clock_probe.h`; the address is game-specific).

### D: game-specific, irrelevant, or worse than ours
- Already in ours, or ours is better:
  - SPU float model, shufb, interpreter decode fixes;
  - LFQueue push (ours is stricter and verified);
  - vertex-constant window (V keeps the 64-word bug that ours fixed at 32 words);
  - render-target readback (inFamous has none, so nothing for exposure).
- Upstream bugs: unbraced draw handlers in `rsx_commands.c`.
- Against AGENTS.md policy:
  - `FIOS_HLE` native zlib replacing the SPU task;
  - LFQueue auto-wake without a signal;
  - inFamous address and shader-hash hacks (`SUN_NDL_CLAMP`, `CULL_VP_SCALE`, `LOD_*`, `car_v233.h`, trainer);
  - DLSS/FSR, UI overlay, `PS3_LANG`, msg-dialog string matches.
- Nothing upstream implements `cellFontInitLibraryFreeTypeWithRevision`, so no help with the missing menu text.

## License and attribution
- **`ps3recomp/`:** MIT, © 2026 Ned Heller / sp00nznet. Reuse needs the MIT notice kept, plus credit to whompay/inFAMOUSreborn and the commit in the commit message and `THIRD_PARTY_LICENSES.md`. Whether whompay's edits are explicitly MIT is a HYPOTHESIS; the vendored LICENSE covers the directory.
- **`infamous-recomp/`:** no license, so all rights reserved. Do not copy; reimplement ideas only.
- **`installer/`:** only `Cargo.toml` says MIT, with no license text, so it is ambiguous. Reimplement.
- **`installer/patches`:** lifted-code diffs; never import.
- **Others:** `xxhash.h` BSD-2 (keep the notice); SDL3 zlib.
- **Our own docs:** `THIRD_PARTY_LICENSES.md` still pins ps3recomp `0fe7dbf` while we build `307b08a`. Recheck before release.

## Top three (approval required before any implementation)
1. **B1 + B2, guest sampler state and texture gamma/sign-expand in the D3D12 path.** Most direct lead on the dark garage: both gaps verified in our code, generic, offline-testable by decoder unit tests and RSXI replay.
2. **B3, the PPU CAS vs SPU PUTLLC lost-update race.** A generic atomicity bug confirmed by reading the code; a new stress test proves both the bug and the fix.
3. **B4, SPURS workload shutdown lifecycle.** The garage → race transition is on the path to the first race, and our no-op Shutdown/Wait could hang or corrupt workload reuse there.
- Cheap follow-ups:
  - A1 (TLS guard, CPU);
  - B5 (FIFO kick wait);
  - env-only experiments `PS3_USLEEP_SPIN=1` and `GCM_SEMA_ACQUIRE=1 GCM_SEMA_ACQUIRE_MS=50`, which need launch authorization.
