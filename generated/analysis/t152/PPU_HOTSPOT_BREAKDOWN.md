# T152: PPU main-thread hotspot breakdown

Labels: VERIFIED (measured or read in code), PARTIAL (measured offline, or on one run), HYPOTHESIS (inferred), BLOCKED (needs a game run).
No game was run by T152; the in-game numbers below come from T149's existing traces.

## 1. Baseline

| Item | Value |
|---|---|
| ps3recomp | `ps3recomp-t152-ppu-performance`, branch `agent/t152-ppu-recompiler-performance`, base **`80fe5de`** (T146 unified tip; T153 has published no newer baseline) |
| Root repo | worktree `root-t152`, branch `agent/t152-ppu-recompiler-performance`, base `main` **`4bdeed3`** |
| Lifted PPU code | `generated/ppu-hooked-staging` (79 TUs, 3.72 GB of C++, 53,278 lifted functions), the lift every exe since T96 is built from |
| In-game evidence | T149 race runs of the T146 exe: P1 (performance preset) `runtime-p1r1-20261028-202136`, P0 (defaults) `runtime-p0r1-20261028-201734`; `PS3_CRITICAL_PATH_TRACE` window 175–240 s (413 / 362 frames) |
| Host | Ryzen 5 9600X, RTX 5060; clang-cl 23.1.3, `/O2 /Ob2 -fno-strict-aliasing -fwrapv` |

## 2. Methodology

1. **Where the frame thread's running time goes (in game, from existing data).**
   - `tools/site_running.py` re-reads T149's raw `cpath.txt`.
   - Running time = frame span minus the frame thread's blocking syscalls (kind 1) and usleeps (kind 2), the same definition as `tools/cpath_report.py` (it reproduces its 55.98 ms exactly).
   - Each guest-site span (kind 35: the T134/T149 sites) is intersected with that running time. Nested sites credit the innermost one.
   - Log: `logs/site_running.txt`.
2. **Code mix (static, whole lift).** `logs/static_inventory_all.txt` (per-construct site counts over all 79 TUs) and `tools/scan_leaves.py`.
3. **Generated x64 (real lifted functions).**
   - `tools/extract_fn.py` cuts real functions out of the staging lift into a standalone TU.
   - They are compiled with the build's flags under several `ppu_recomp.h` variants and counted with `tools/asm_stats.py` (`scratch/cg/`, private).
4. **Per-operation cost (offline benches against the real runtime objects).**
   - `tools/bench_icall.cpp`.
   - `tools/bench_lifted.cpp`: real lifted leaf functions executed on synthetic guest memory, with the final guest state hashed per variant.
5. **Per-guest-function profile in game: BLOCKED.**
   - No run has ever sampled MotorStorm's frame thread by function (T134/T140/T149 never ran `PS3_SAMPLE`).
   - T152 adds `PS3_SAMPLE_TOP=25` so that run prints a top 25 (§12 of `PPU_RECOMPILER_PERFORMANCE.md`).

## 3. Top 25 hotspots of the PPU frame thread

Rows 1–9 are measured in game, as P1 ms per frame (P0 in brackets). Rows 10–25 are overhead classes of the lifted code: static site counts over the whole lift, with per-operation cost from offline benches. Their in-game frequency is BLOCKED until the `PS3_SAMPLE` / `PS3_VM_STATS` run.

| # | Hotspot | Evidence | Cost | Kind |
|---|---|---|---|---|
| 1 | **`0x50C818` frame-end Wws spin**: busy-polls `[r3+0x44C]` / `[r3+0x2560]` until the frame's SPU Wws jobs are done | `site_running.py` | **33.66 ms running (60.1%)** [22.32 ms, 46.5%] | **waiting for SPU work, not computation** (VERIFIED) |
| 2 | Guest code outside every traced site (game update, AI, scene, render submission) | `site_running.py` | **18.24 ms (32.6%)** [21.56 ms] | genuine guest computation plus recompiler overhead (split: rows 10–25) |
| 3 | `0x30B710` Havok step (its running part) | same | 3.31 ms [3.37] | guest computation (its waits are blocked time) |
| 4 | `0x50D868` ExecutePushBuffer | same | 0.42 ms [0.34] | guest computation (RSX command emission) |
| 5 | `0x4B63F0` wait primitive (running part: spin before `usleep(250)`) | same | 0.11 ms (730 calls; 36.3 ms total, almost all blocked) | wait |
| 6 | `0x5F74B0` PVS WaitForCompletion | same | 0.10 ms (165 calls) | wait |
| 7 | `0x4AACA0` JobBatch::Wait | same | 0.09 ms (123 calls) | wait |
| 8 | `0x736770` PUT flush | same | 0.02 ms | guest |
| 9 | `0x72E1E0` RSX ref throttle | same | 0.01 ms running (49.2 ms total, blocked on the RSX) | wait |
| 10 | Inline-load gate: 4 global re-reads plus about 11 instructions per load | asm: ~15 x64 instr per `vm_read32` site | 5.74 M `ld32` + 0.67 M other load sites | recompiler overhead |
| 11 | Out-of-line scalar stores (`vm_write*` call + spills) | T140 bench 1.0–1.5 ns + call; real lifted fn −31% when inline | 3.94 M sites (`st64` 2.16 M: mostly prologue saves) | recompiler overhead |
| 12 | CR materialization: every compare builds a 4-bit field, ORs XER.SO, read-modify-writes `ctx->cr`, and the branch re-tests a bit | static | 4.65 M sites | recompiler overhead |
| 13 | Guest registers live in `ctx` memory; every lifted instruction loads/stores `ctx->gpr[]` (`-fno-strict-aliasing` + guest stores defeat register promotion) | asm: 3.3 loads per lifted statement in `func_000C9678` | all code | recompiler overhead |
| 14 | XER.CA updates (`addc`/`subfc`/`sraw`…) as read-modify-write of `ctx->xer` | static | 1.77 M sites | recompiler overhead |
| 15 | Tail-call trampolines: TLS write of `g_trampoline_fn`, return, caller's drain loop | static | 3.53 M sites | recompiler overhead |
| 16 | Indirect calls (`bctrl`, vtables, computed `switch` default) via `ps3_indirect_call` | bench 15.2 ns hot / 35 ns cold | 213 k sites + 158 k jump-table switches | recompiler overhead |
| 17 | FP NaN-propagation wrappers (`ppu_fadd/fmul/...`: 3 compares per op) | static | 237 k sites | exact PPC semantics (kept) |
| 18 | `fma()` CRT call for fused `fmadd` (no `-mfma`) | asm: 126 calls in `func_000C9678` | 156 sites (hot inside FP kernels) | recompiler overhead |
| 19 | Direct calls `ctx->lr = …; func_X(ctx); DRAIN_TRAMPOLINE` | static | 550 k sites | recompiler overhead (small) |
| 20 | Syscall dispatch `lv2_syscall` (mutex/cond 0.3–0.5 µs, T121) | T121 | 70–760 calls/s per thread | low |
| 21 | `stwcx.`/`stdcx.` (sharded spinlock + context scan) | T140: 13.4 ns uncontended, 175–585 ns at 4 threads | 940 sites | low frequency (unmeasured) |
| 22 | Stores to SPU-marked lines (global lock-line lock) | T140: 11.6 ns; 260 ns at 4 threads | unknown (`PS3_VM_STATS st_coh`) | coherence (kept) |
| 23 | Float→int conversions with saturation (`ppu_f2i*`) | static | 3.8 k sites | exact semantics (kept) |
| 24 | VMX helpers (`ppu_vmx.h`, exact saturation/NaN) | static | 1.8 k helper sites | exact semantics (kept) |
| 25 | `usleep(250)` returning after about 520 µs (host 0.5 ms tick) | T121 | 1300–1500 calls/s; blocked time, not running | wait latency (T121 `PS3_USLEEP_SPIN=2`, opt-in) |

## 4. Guest computation versus recompilation overhead

| Part of the 55.98 ms per P1 frame | ms | Status |
|---|---:|---|
| Busy-wait for SPU Wws jobs (`0x50C818`) | **33.66** | VERIFIED (100% of the site's time is running; it overlaps SPU busy time 8.8 ms and SPU+RSX 24.8 ms) |
| Guest code (rows 2–4, 8) | **≈ 22.0** | VERIFIED as a total |
| Running part of the wait primitives (rows 5–7, 9) | 0.31 | VERIFIED |

- **So the "56 ms of main-thread computation" is about 60% waiting.** It is the guest's own frame-end spin on the SPU job counters, and it shrinks when the SPU jobs finish sooner, not when PPU code gets faster.
  - The measured lever for it is the Wws job AOT. T106 D measured in game: spin 12.5 → 0.3 ms, emit 21 → 6, PRE 54 → 40 (T134 §1).
  - It was missing from every `port/` build; T152 adds it as a build option (`9cd7ef2`).
- **Of the ≈ 22 ms of real guest code, the recompiler's share is not measurable without a profile.**
  - Static code quality shows a large share: about 16 x64 instructions per lifted statement in `func_000C9678`, and every lifted register access goes through memory.
  - The implemented fixes measure −5 to −13% of instructions (load gates) and −31% time on a store-heavy function (inline stores) offline.
  - HYPOTHESIS for the frame: −1 to −4 ms of the 22 ms (store and load mix unknown in game).
  - The larger structural costs (rows 12–15) need a re-lift with register caching and CR/XER liveness; that was not attempted (§9 of the main report).

## 5. Generated-code analysis (VERIFIED, `scratch/cg/`, real lifted functions)

| Variant of `ppu_recomp.h` | `func_000C9678` insn / branch | `func_002D0D94` | `func_0096B648` |
|---|---|---|---|
| A: staging (relaxed-atomic inline loads, 4-global gate) | 15,499 / 3,259 | 2,552 / 330 | 640 / 81 |
| B: plain (non-atomic) loads | 15,266 / 3,258 | 2,521 / 329 | 635 / 81 |
| D: volatile loads | 14,910 / 3,245 | 2,525 / 319 | 639 / 81 |
| **F: T152 page gate** | **13,526 / 2,329 (−13% / −29%)** | **2,357 / 202 (−8% / −39%)** | **605 / 62 (−5% / −23%)** |

Findings:
1. **The inline-load gate dominated the load's cost, not the atomics.**
   - Each load re-read `vm_inline_ok`, `ppu_hle_inject_base`, `ppu_vm_size` and `vm_base`, because the out-of-line call on the slow path may change any of them. That is about 15 instructions where the access itself is 3 (`mov`, `bswap`, plus address arithmetic).
   - Relaxed atomics vs plain loads: ≤ 1.5% (A vs B), so the single-copy-atomic loads stay.
2. **Every store was a call.**
   - Every `stb…std` called `vm_write*` (T140 made its body fast, but the call stayed). The call forces the live `ctx` values and temporaries to the stack and reloads the gate globals afterwards.
   - Inline (variant E): 157 → 101–107 ms on the store-heavy `func_0096B648` workload (§8 of the main report).
3. **Guest state in memory.**
   - `ctx->gpr[n]` is read and written for every lifted instruction; 3.3 memory loads per lifted statement.
   - The lifter already caches callee-saved restores in locals (`_cs_NN`, 148,868 sites), but nothing else.
4. **CR/XER.**
   - Compares materialize the full CR field including XER.SO and read-modify-write `ctx->cr` (4.65 M sites); the branch then re-extracts a bit.
   - Clang folds part of it, but the `ctx->cr` store stays, because `ctx` escapes.
5. **Dead fragments.**
   - Lifted functions contain unreachable fragments that other entries reach as separate functions (e.g. `func_0096B648` has 1,257 statements and compiles to 605 instructions).
   - Static counts overstate the live code; code-size growth from inline stores is therefore smaller than site counts suggest.
6. **Smaller items.**
   - `fmadd` lowers to a CRT `fma()` call (no `-mfma`).
   - Endianness costs one `bswap` per access (no MOVBE without `-march`).
   - Translation is `vm_base + ea`, with no lookup (VERIFIED; T140).
