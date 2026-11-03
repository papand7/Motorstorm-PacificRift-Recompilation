# T116: shader compilation and PSO performance

Worktree `ps3recomp-t116`, branch `agent/t116-shader-pso-cache`. Nothing was built in full, launched, merged or pushed.

## 1. Integration base and commits

- **Base:** `e3b961d` (T110 tip, also T114's base; contains T108 `6b1a7e4`). T113's `19d6b6d` (black-race repair, renderer owner) is one commit ahead of it and is not included.
- **Commits:**
  - `c8d8a0a`: `rsx_shader_cache.h` and its WARP test. Self-contained; nothing calls it yet.
  - `30b817b`: wires the backend to it. Off by default. Also adds a pin test and updates one existing pin.
- **T106 numbers came from a different tree.** The 7.17 FPS runs used `b84ed80` (the T109 line, guest maxContention). That line and `e3b961d` already conflict in `rsx_d3d12_backend.c`, independently of T116 (`git merge-tree` exit 1). See §13.

## 2. Existing shader pipeline (VERIFIED by reading `rsx_d3d12_backend.c` at `e3b961d`)

**Compiler.** fxc `D3DCompile` (d3dcompiler_47), producing DXBC SM 5.0 (`vs_5_0`/`ps_5_0`) with flags 0. Flags 0 means the default optimisation level, no debug info and no skip-validation. The same settings apply to every build type. No DXC/DXIL is used anywhere.

**Vertex path:**
1. `vp_get_vs` runs at draw-record time.
2. It hashes the program's own ucode with 32-bit FNV-1a. The program starts at `transform_program_start` and ends at its end bit.
3. It does a linear lookup in `vp_vs[128]`.
4. On a miss: `rsx_vp_decompile`, then `D3DCompile("guest_vp2")`, then the blob is kept in a slot. There is no PSO at this stage.
5. Eviction is FIFO with `memmove`, which shifts slot indices.

**Fragment path:**
1. `vp_get_fp_pso` runs in the replay prepass and draw loop. A `s_fpm` memo lets the draw loop reuse the prepass answer.
2. It resolves the FP address and computes `rsx_fp_code_hash`, a 32-bit hash of the code that excludes inline constants. It also scans the program's units for shadow, gamma and expand.
3. It does a linear lookup in `vp_fp[256]`, keyed on:
   - shader: `vs_idx`, `vs_hash`, `gen`, `uhash`, `exp32`, `cube_mask`, `shadow_key`, `xf_*`;
   - render state: `blend`, `nrt`, `rtfmt`, `cmask`, `cull`, `depth`.
4. On a miss:
   - decompile, apply the env-gated debug rewrites, then `D3DCompile("guest_fp")`;
   - build the PSO description (fixed: input layout, `vp_root_sig`, D24S8, `LESS_EQUAL`, TRIANGLE, 1 sample);
   - `CreateGraphicsPipelineState`, then FIFO insert. The PS blob is released after PSO creation.

**Other PSOs** (`compile_vp` base pipelines, zconv, the blit/live-draw paths) are created once. They are not on the race path and were left unchanged.

**What is cached today:**

| Stage | Cached? |
|---|---|
| VS decompile + compile | yes (memory, 128 slots) |
| Fragment PSO | yes (memory, 256 entries) |
| PS bytecode on its own | **no**: any state-only or VS-only PSO miss re-decompiles and re-compiles the PS |
| Failures | **no**: retried on every lookup |
| Across runs | **nothing persists**; the only cross-run cache is the driver's own |

Root signature: one VP layout per process (static samplers, or the `RSX_GUEST_SAMPLERS` tables), chosen at init.

## 3. Limitations found

| # | Finding | Label |
|---|---|---|
| L1 | A program that fails to compile is recompiled on every lookup. T106 A1/B1 race frames show **2 PSO misses per frame, every frame**, costing **5.0–5.3 ms per frame** (median; frame-perf samples, records > 1000). The only failing compile in B1's stdout is `fp=0x07200641`, `error X3004: undeclared identifier '_rsx_expand_input'` (16 lines, the log cap). | VERIFIED (counts); the exact link of the 2 per-frame misses to that program is PARTIAL |
| L2 | The PS bytecode is not cached separately from the PSO, so a new blend, cull, depth, cmask, rtfmt or VS pairing pays the full decompile plus fxc again. | VERIFIED (code) |
| L3 | Nothing persists across runs. Every run pays every fxc compile again. | VERIFIED (code) |
| L4 | The VS key ignores the start slot, but a branching program's HLSL depends on it (`rsx_vp_set_branch_base`). The same bytes at another slot would reuse a wrong shader. | VERIFIED (code + test 8); not observed in game |
| L5 | With `RSX_COLOR_XFER` on and the sRGB rewrite not applicable, the entry is stored with `xs=0` while lookups use `xs=1`, so it misses on every lookup. | VERIFIED (code); `RSX_COLOR_XFER` is off by default |
| L6 | The cache identities are 32-bit hashes (VS ucode, FP code, shadow key) with no byte comparison. Collision risk is about n²/2³³ (about 5×10⁻⁶ for 200 programs). | HYPOTHESIS: low risk, unchanged |
| L7 | `vs_idx` is part of the FP key, and VS eviction shifts slots, so after more than 128 VPs every FP pipeline misses. These are redundant compiles, not wrong shaders, because `vs_hash` validates. | VERIFIED (code); not reached in T106 (`vs` misses 0) |
| L8 | Decompiler bug behind L1: `_rsx_expand_input` is used where the helper is not emitted. The helper is emitted only when the scanners find expand/bx2 units. The emitter's condition differs, plausibly on `FP_BRANCH`-flagged words. This is **renderer correctness and is not fixed here**: fixing it changes what that draw renders. For the renderer owner. | HYPOTHESIS (cause); VERIFIED that the bug is still at `e3b961d` (decompiler identical apart from a new entry point) |

## 4. The measured race stalls (VERIFIED)

Each fc-watchdog stack was resolved without a PDB: disassemble the exe frame and read the strings it passes. All 6 stalled T106 runs stalled inside the present thread's `render_frame`, in the record phase:

| Run(s) | Top of the stack | Exe caller |
|---|---|---|
| B2, C1, C2, D1, D2 | `D3DCOMPILER_47.dll` | `D3DCompile(…, "guest_fp", …, "main", "ps_5_0")`: **fxc compiling a guest fragment program** in `vp_get_fp_pso` (non-AOT RVA `+0x175b3303`, AOT RVA `+0x17b89213`) |
| B1 | `nvgpucomp64.dll` under `nvwgf2umx.dll` | the driver compiling a pipeline, i.e. `CreateGraphicsPipelineState` |

- **Not determined:** whether a stall is one huge program or many state variants in one frame. The watchdog shows only the 2-second sample.
- B1's sampled frame 2642 near the stall had 25 misses costing 122.6 ms.
- `RSX_SHADER_STATS=1` now logs every compile or PSO creation ≥ 50 ms with fp, ucode hash, HLSL size and frame, which answers this in one run.

## 5. Cache-key audit

Bytecode identity and pipeline identity are now separate.

**Bytecode** (`rsc_compile_key`): a 128-bit hash of:
- the format version and the d3dcompiler build (PE stamp, size, checksum and `D3D_COMPILER_VERSION`);
- the source name, entry, target, both flag words and the length;
- the HLSL text.

All translation inputs therefore enter through the text: decompiler version, debug env rewrites (`FP_*`, `VP_W_ONE`, `VP_BYPASS`), shadow/cube/xfer options and exp32. Nothing has to remember to bump a version. Guest addresses and inline constants do not enter, because they don't change the text.

**Pipeline** (`rsc_pso_key`): a field-by-field serialisation of the full description, with no struct padding or pointers:
- VS/PS bytecode by content;
- root signature as the hash of its serialized blob;
- input layout (semantic name, index, format, slot, offset, class, rate);
- all 8 blend targets plus alpha-to-coverage and independent blend;
- sample mask, rasterizer (all fields) and depth-stencil (including both stencil faces);
- strip cut, topology type, RT count, all 8 RTV formats, DSV, sample desc, node mask and flags.

It excludes dynamic state: viewport, scissor, blend factor, stencil ref, descriptors and constants. Descriptions it cannot represent (stream output, cached-PSO input, HS/DS/GS) get no key and are never served from the library.

**The existing in-memory FP key** is unchanged at level 0. At level ≥ 1, L4 and L5 are fixed (§7).

**Tests** (`test_rsx_shader_cache.c`):
- each of 7 compile inputs separates the key;
- each of 27 pipeline fields separates the key;
- equal content behind different pointers shares a key;
- **negative:** a text-only key collides although the flags change the bytecode, and a key without the DSV format collides for two different pipelines.

## 6. Persistent compiled-shader cache (`rsx_shader_cache.h`)

**Levels** (`RSX_SHADER_CACHE`; default 0, which is exactly the old calls):
- **1:** in-memory blobs (FIFO, `RSX_SHADER_MEMCACHE`, default 4096) plus remembered compile errors (only `E_FAIL` with compiler messages, never transient failures).
- **2:** adds disk.

**Disk:**
- Location: `RSX_SHADER_CACHE_DIR`, default `%LOCALAPPDATA%\ps3recomp\shader_cache\v1`. Never the game or asset directories.
- Each entry has a 56-byte header with magic, format, kind, 128-bit key, compiler build, length and a 128-bit payload hash, followed by the DXBC.
- **Checks on read:** every header field, the length, the payload hash and the `DXBC` magic. On any failure the entry is counted, deleted and the shader recompiled; it is never used. D3D12 also verifies the DXBC's own signature at PSO creation.
- **Writes** go to `name.<pid>.<tid>.<seq>.tmp`, then `MoveFileEx(REPLACE_EXISTING)`. Readers never see partial entries.
- **Housekeeping:** temporaries older than an hour are removed at open.
- **Bounded size:** `RSX_SHADER_CACHE_MAX_MB` (default 256). Over budget at open, the oldest entries are deleted down to 75%; writes that would exceed it are skipped.
- **Clearing:** `RSX_SHADER_CACHE_CLEAR=1`.
- **Concurrency:** an SRW lock covers the tables. fxc itself runs outside the lock, as before.
- **Stored content:** only DXBC derived from translation. No guest ucode and no HLSL text are written.

## 7. PSO caching

- **A. In-process.** The existing 256-entry FP PSO cache is kept and not replaced. At level ≥ 1:
  - translate and compile failures are stored as entries with no pipeline, so the lookup returns NULL (the same answer as before) without retrying (fixes L1);
  - the VS key includes the start slot (L4);
  - entries are keyed with the sRGB bit as looked up (L5);
  - state-only misses now hit the bytecode cache, so they cost only `CreateGraphicsPipelineState` (L2).
- **B. Persistent (level 3).** An `ID3D12PipelineLibrary` (via `ID3D12Device1`):
  - **Naming:** each pipeline is named by its 128-bit description key.
  - **Validity:** the file is valid only for the same vendor, device, subsystem, revision, UMD driver version, adapter flags and `D3D12_SDK_VERSION`. That identity is stored in the file and also checked by the driver.
  - **Fallbacks:** a corrupt or foreign file falls back to an empty library. A failed load means normal creation followed by a store.
  - **Blob lifetime:** the loaded blob is kept for the library's lifetime.
  - **Saving:** after `RSX_PSO_LIB_SAVE_FRAMES` (default 120) frames with no new pipeline, and at shutdown; the write is atomic.
  - **Portability:** PSO binaries are never assumed portable across GPU, device or driver.

## 8. Prewarming (design only; not implemented)

- **Warm runs:** at levels 2–3 a warm run already turns every previously seen compile into a disk load (about 0.04–0.6 ms) and every previously seen pipeline into a library load. That is lazy prewarming with no placeholder pipelines and no concurrent D3D12 creation.
- **Cold first runs:** they still pay full cost. The design for a later step:
  - record the bytecode and pipeline keys first used in each phase (boot, menu, garage, track load, race entry) into a manifest under the cache directory;
  - during the next track load, run fxc for missing keys on one worker thread. fxc is thread-safe; D3D12 PSO creation stays on the render thread;
  - a draw still blocks for its own compile if it isn't ready. It never renders with an incompatible PSO.
- Not done, because the T106 evidence doesn't yet show whether the race stall is one program or many (§4). Measure first with `RSX_SHADER_STATS`.

## 9. Hot path

| Item | Measurement | Label |
|---|---|---|
| Hit lookup cost | T106 A1/B1: **1.8–1.9 µs per FP lookup**, about 3.7 ms/frame for about 2,000 lookups, out of 134–214 ms. Per lookup it hashes the code and scans units 3–5 times, then does a linear scan of up to 256 entries. | VERIFIED (frame-perf, derived) |
| Change to the hit path | Not changed: under 3% of the frame, and the per-component split isn't measured. Candidates: one combined unit scan; a hash index instead of the linear scan. | — |
| New code on the hit path | None; it runs on misses only. Costs: key **about 0.07–0.14 µs per KB of HLSL**; PSO key **0.4 µs** per request. | VERIFIED (bench) |

## 10. Benchmarks

Setup: WARP and real fxc (synthetic; **not race performance**). 40 shaders: 8 real decompiler outputs and 32 generated shaders with 4–60 unrolled steps. Source: `logs/test_d3d12_shader_cache.log`, with an earlier run's disk figures in parentheses.

| Measurement | median | p95 | p99 | max | total |
|---|---|---|---|---|---|
| Cold compile, level 0 | 19.6 ms | 46.4 | 48.9 | 48.9 | 822 ms |
| Cold compile + disk write, level 2 | 20.3 | 45.5 | 45.9 | 45.9 | 834 ms |
| Warm memory hit | < 0.001 | 0.001 | 0.001 | 0.001 | ≈ 0 |
| Warm start from disk | 0.58 (earlier run: 0.04) | 3.6 (0.08) | 4.3 | 4.3 | 62 ms (4 ms) |
| PSO create on WARP | 3.5 | 5.9 | 6.6 | 6.6 | 56 ms / 16 |
| PSO from library on WARP | 0.62 | 1.03 | 1.04 | 1.04 | 10 ms / 16 |
| Library save | — | — | — | — | 4.0 ms (249 KiB) |

- **Warm vs cold:** a warm start is **13–200× faster** than cold. Disk-read time varies run to run, probably from on-access file scanning (HYPOTHESIS).
- **Compiler invocations:** warm start 0 of 40. Failure memory: 1 fxc call for 5 requests. 8-thread run: 31 compiles for 240 requests (10 unique shaders; the extra compiles are concurrent first misses).
- **Memory:** 284 KiB for 40 blobs (about 7 KiB each; worst case at the 4096 cap ≈ 30 MB). Disk: 287 KiB.
- **Hardware stalls are not modelled:** WARP doesn't model the NVIDIA driver compile (B1).

## 11. Regression tests

| Test | Result |
|---|---|
| `test_d3d12_shader_cache.py` (new) | **70 PASS**: 25 source pins on the backend and header, 44 C checks, and the C run itself from `test_rsx_shader_cache.c` (keys, level 0 equivalence, failure memory, FIFO, 7 corrupt/partial/foreign disk entries, temporaries, eviction, clear, threads and multi-writer, pipeline keys, library cold/warm/corrupt/foreign, VP branch base) |
| `shader_trace` | 17 PASS (the stage-order pin now names `rsc_compile`/`rsc_create_pso`) |
| `color_xfer` | 14 PASS |
| `blend_state` | 17 PASS |
| `depth_state` | 10 PASS |
| `t110_pins` | 27 PASS |
| `rsxi_hooks`, `texture_source_order` | rc 0 |
| `zeta_pool` | 40 PASS, 1 FAIL: harness link `m.lib`, same failure on untouched `e3b961d` |

Log: `logs/suite_t116.txt`.

**TU compile:** `rsx_d3d12_backend.c` with the exact game flags (`tools/tu_t116.cmd`, from T110's) gives rc=0 with the **same warning kinds** as base `e3b961d` (`logs/tu_*`). One new `-Wnrvo` was removed.

## 12. Public-source audit

`audit_public.py --staged` before each commit (`logs/audit_c1.log`, `audit_c2.log`): the same 25 pre-existing items as misc1/T108, none in T116 files. The tests use only hand-assembled programs and generated HLSL.

## 13. Runtime A/B plan (not run; needs build and launch authorization)

- **Tree:** the T116 branch, or an integration of T116 with the renderer and SPU line. All arms use one exe and identical env, apart from the variables below.
- **Window:** T106's (race entry +10 to +80 s, `ab_fps.cfg`, `RSX_FRAME_PERF` on), with `RSX_SHADER_STATS=1` in every arm.
- **Arms:**
  1. `RSX_SHADER_CACHE=0`
  2. `=1`
  3. `=2` cold (`RSX_SHADER_CACHE_CLEAR=1`), then `=2` warm
  4. `=3` cold, then `=3` warm
  5. (prewarm: n/a until §8 exists)
- **Order:** ABBA-style, with each cold run immediately followed by its warm run. Use a fresh `RSX_SHADER_CACHE_DIR` per arm pair, under `generated/`.
- **Metrics:** FPS excluding stalls, p50/p99 interval, `[shader-stats]` (fxc count and ms, max stall, negative hits, disk and library hits), fc-watchdog reports, and frame-perf `pso miss/miss_ms`.
- **Expected results:**
  - level ≥ 1 removes the steady 2 misses/frame (about 5 ms/frame; HYPOTHESIS until measured);
  - warm level 2 removes the fxc part of the race stalls (5/6 of them);
  - warm level 3 removes the driver part (B1).
- **Comparability with T106's 7.17 FPS:** those runs need the T109 maxContention change, which conflicts with the T110 line in this file. Resolving that is the integration owner's task. Until then, compare only within one tree.
- **Correctness check:** level 0 against level 3 (warm) RSXI or frame captures of the same race frame should be identical. Bytecode identity is checked; image identity is not yet.

## 14. Remaining risks and opportunities

- **Risks:**
  - The fragment-program decompiler bug (L8) remains. Its draw still falls back exactly as before.
  - The 32-bit in-memory identities (L6) are unchanged.
  - The cold first run still stalls.
  - The pipeline library depends on a driver that serialises well. It is tested on WARP only; NVIDIA behaviour is unverified.
  - The disk cache trusts its own directory only after the checks in §6. Any process that can write there can only cause a recompile.
- **Opportunities:** the §8 manifest prewarm; fixing L8 (removes the fallback draw); a cheaper hit path (§9); `D3DCOMPILE_OPTIMIZATION_LEVEL0` for very large programs. The last one is a behaviour and precision change, so it needs validation and is not proposed as a default.

## 15. Commits and changed files

| Commit | Files |
|---|---|
| `c8d8a0a` | `libs/video/rsx_shader_cache.h` (new), `libs/video/tests/test_rsx_shader_cache.c` (new) |
| `30b817b` | `libs/video/rsx_d3d12_backend.c` (+64/−8: include, root-signature identity, init, VS key and compile call, FP failure memory, FP compile/create calls, sRGB key line, frame-end and shutdown hooks), `tools/test_d3d12_shader_cache.py` (new), `tools/test_d3d12_shader_trace.py` (one pin line) |

- **Cherry-picking:**
  - `c8d8a0a` applies anywhere.
  - `30b817b` needs T110's `vp_get_fp_pso` signature (the `xf` parameter). It does not apply to `b84ed80` as is. Re-run `generated/analysis/t116/tools/patch_backend.py <tree>`, which matches exact strings and fails loudly.
- **Private tools:** `generated/analysis/t116/tools/` (`build_test.cmd`, `tu_t116.cmd`, `patch_backend.py`).
