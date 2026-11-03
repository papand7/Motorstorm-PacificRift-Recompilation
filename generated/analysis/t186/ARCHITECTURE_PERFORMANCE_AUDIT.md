# T186: architectural performance audit

Status: **PARTIAL.** This is a source and static-analysis diagnosis with two offline synthetic benchmarks. No game was launched and no production code was changed. Every frame-time figure below comes from the T183/T184 runs (exe `c32cd09d…9b97`, T183 code `766d3575`). Every per-op cost is synthetic or read from disassembly. Anything else is labelled ESTIMATE or HYPOTHESIS.

Source references are to `ps3recomp-t183` (committed T183 tree) unless stated. Lifted output is private and is described here only in schematic form: `generated/ppu-t173-staging/ppu_recomp_*.cpp` (PPU), `build/motorstorm-t183/generated_spu/spu_<sha>/spu_recomp.c` (SPU, as built).

## 1. Executive findings

1. **The 68.5 ms frame is one serial chain on the guest frame thread (tid 1), and almost all of it is lifted guest code running slowly** (VERIFIED as time, T183/T184):
   - Havok SPU waves: 25.0 ms;
   - post-Havok PPU: 23.0 ms;
   - Wws lane work, seen as emit + gap + spin: about 20 ms;
   - The renderer is off the path (RSX wait 0.05 ms).
2. **The translation model is a compiled interpreter of guest state, not native code.** Both lifters emit C in which:
   - every guest register is a field of a context struct in memory;
   - every compare materializes the guest condition register;
   - every guest store (PPU) and every channel access (SPU) is an out-of-line call that escapes the context.
   Measured from disassembly (static): about 10 x64 instructions per PPU instruction in simple loops, and about 19 per SPU instruction in a solver group.
3. **SPU float is emulated bit-exactly at 10–14× the cost of native SSE** (VERIFIED, synthetic, section 4.2). Havok and Wws are float-heavy. A cheaper exact path exists in principle, but its exactness check limits it to 1.3–2.2× per op.
4. **All SPU MFC traffic is serialized through process-wide locks** (VERIFIED in code):
   - a global SRW lock on every MFC channel access (`mfc_for`);
   - one global spinlock for every GETLLAR/PUTLLC (`g_lockline`);
   - a reservation bitmap that is never cleared.
   Under 5-way contention this primitive pattern costs 16–35× its uncontended cost (synthetic, section 6.3).
5. **The Havok solver contains a ticket-lock spin-poll** (site `0x1781C`; VERIFIED as code shape, HYPOTHESIS as the main source of the 6,323 GETLLAR per run). Each spin iteration takes the same global lock-line lock that the lock holder needs to release.
6. **GPU offload of Wws is not practical** (ESTIMATE, strong; section 8). The renderer has avoidable CPU work, but none of it is on the critical path.
7. **60 FPS is not credible on this architecture.** On the evidence, even a deep codegen redesign gives about 25–30 ms (33–40 FPS) at best; section 13. **30 FPS is a credible target**, but only with SPU and PPU codegen changes, not with runtime tuning alone.
8. **First experiment:** de-serialize the SPU MFC/atomic path (section 15). It is runtime-only (no relift), touches both Havok and Wws, and is supported by code and synthetic evidence.

## 2. Current execution architecture

| Layer | Implementation | Source |
|---|---|---|
| PPU | AOT, `tools/ppu_lifter.py` emits one C++ function per guest function. Blocks are `goto` labels; `void func_X(ppu_context* ctx)` | `tools/ppu_lifter.py`, `runtime/ppu/ppu_context.h:53-101` |
| PPU build | clang-cl 23.1.3, `/O2 /Ob2 -fno-strict-aliasing -fwrapv`. No LTO, no `-march`/`-mfma`, `/GS` on | `build/motorstorm-t183/build.ninja:140` |
| SPU | AOT per image, `tools/spu_lifter.py`, into "groups" of chained blocks. Registers are `ctx->gpr[128]` (u128 union). Exits go through the TLS trampoline `g_spu_trampoline_fn` and the drain loop | `runtime/spu/spu_context.h:174,876,938-947,1034` |
| SPU build | clang-cl `/O2 -msse4.1 -DSPU_USE_DISPATCH_MT`, no AVX2 | `build.ninja:1058-1062` |
| Memory | Flat 4 GB + 64 KB reservation at `vm_base`, committed on first touch by a VEH; `ppu_vm_size=0`, so no bounds check | `port-t161/main.cpp:145,366-390`, `runtime/ppu/ppu_memory.h:29,54-56` |
| SPU DMA | Synchronous `memcpy`; tags complete at once | `runtime/spu/spu_dma.h:616,708` |
| SPU atomics | Global TTAS spinlock `g_lockline`, 128 B snapshot copies, sticky bitmap, reserver-list walks | `runtime/spu/spu_coherency.c:38-54,78,103-125,231-261`; `spu_channels.c:614-895` |
| SPURS | Per instance, `nspus` lane threads (5 here) plus a coordinator. Idle lanes wait on a CV. Tasks run on a thread per run, or pooled (`PS3_SPU_TASK_POOL`) | `libs/spurs/cellSpurs.c:1940,2030,2139,2194-2201`; `runtime/spu/spu_task_pool.h` |
| Renderer | Host FIFO walker decodes RSX methods per word. CPU vertex fetch/convert ("expand") into an UPLOAD ring; D3D12 | `libs/video/cellGcmSys.c:2633-2813`, `rsx_commands.c:123`, `rsx_d3d12_backend.c:12600-12720` |

## 3. PPU recompilation analysis

All VERIFIED from the generator, `ppu_recomp.h` and llvm-objdump of two T183 build objects, unless labelled.

| Question | Finding |
|---|---|
| Direct native ops? | Integer ALU yes, but every result is stored to `ctx->gpr[n]` |
| Registers kept in host registers? | **No.** `ctx` is passed to every callee, and stores are opaque calls (no LTO), so values are reloaded after each call. The only locals are callee-save copies (`_cs_31 = ctx->gpr[31]`). 801,286 `ctx->gpr[` sites in `ppu_recomp_000.cpp` |
| Memory translation | `vm_base + ea`, cheap in itself. **Loads** are inline but gated by 4 globals reloaded at every load (`vm_inline_ok`, range, `ppu_hle_inject_base`, `ppu_vm_size`), about 15 x64 instructions per load. The out-of-line path is `vm_read32` (`runtime/ppu/ppu_loader.cpp:1684-1760`) |
| Stores | **Every store is an extern call**: `vm_write32` (`ppu_loader.cpp:2216`), about 30 instructions on the fast path, including a `/GS` cookie check. Its gate ORs 5 globals (`ppu_loader.cpp:2127`) and tests the SPU reservation bitmap. 43,590 `vm_write32` sites in `_000` alone |
| Endian | `__builtin_bswap32` once per access; not repeated |
| CR/XER | Every `cmp`/record form builds the 4-bit field, ORs XER.SO from memory and does a read-modify-write of `ctx->cr`; the branch re-extracts the bit (`tools/ppu_lifter.py:1893-1911`). About 12–14 instructions. No liveness analysis. 34,380 sites in `_000` |
| Calls | `bl` is a direct host call, followed by `DRAIN_TRAMPOLINE`. Each drain pays the on-demand TLS guard (`__dyn_tls_on_demand_init` check, 42 sites in one function) |
| Indirect | `ps3_indirect_call` (`ppu_loader.cpp:2860-2990`): about 20 diagnostic switch tests, then a linear-probe hash (`:2371`). About 15 ns per call (T152). `PS3_ICALL_FAST` cut it to 5.9 ns, but gave no in-game gain (T153) |
| Always-on hooks | The lift used `--trace-hooks`: `PPU_TR_BB` on every label and `PPU_TR_RET` after every call. Each is one global test and branch when off |
| Granularity | One host function per guest function. Median 45 lines, p90 457. Not over-split |

Representative generated shape (schematic, names generalised):

```c
{ int64_t a = (int32_t)ctx->gpr[R]; uint32_t cr_val = ((a < 0) ? 8 : (a > 0) ? 4 : 2) | ((ctx->xer >> 31) & 1u);
  ctx->cr = (ctx->cr & ~0xFu) | cr_val; }          /* cmpwi: about 12-14 x64 instructions */
if (!((ctx->cr >> 1) & 1)) goto loc_X;
vm_write32(ctx->gpr[A] + D, (uint32_t)ctx->gpr[S]); /* every store: an extern call, ctx escapes */
```

Host per guest instruction (ESTIMATE from disassembly): 9.5 in a 9-instruction loop (about 85 x64 instructions including the `vm_write32` body), and 10–12 in a load/compare block. T152 measured about 16 x64 instructions per lifted statement in `func_000C9678`.

T152's page-gated loads and stores, and its inline stores (−31 % on `func_0096B648` offline), **were never integrated**: 0 hits for `vm_ld_page`/`vm_st_page` in this tree.

## 4. SPU recompilation analysis

### 4.1 Model
VERIFIED from `spu_lifter.py`, `spu_helpers.h`, `spu_context.h` and disassembly of solver group `spu_grp_000097E0`.

**Registers.** These live in `ctx->gpr[128]` in memory. Within straight-line code clang reuses a value it has just produced, but it always writes it back, because `ctx` escapes to `spu_wrch`/`spu_rdch`/`spu_drain_call`. In the solver group:
- about 2.4 ctx memory operands per SPU instruction;
- a 6.7 KB stack frame, with 7,220 stack operands (spills).

**SIMD.** Integer, logical, compare and select ops are 1–3 SSE instructions, and `shlqbyi` with an immediate is about 1. `shufb` is about 12 (2×pshufb, blend, compares). Float is the exception (section 4.2).

**Local store.** Masked address, `movdqu`, then one `pshufb` (per-word bswap, folded). One diagnostic test per access (`_spu_lsd`). Cheap.

**Control flow.**
- In-group branches are `goto`s guarded by `SPU_CHAIN_OK`: about 8–10 instructions reading 4 globals, plus `steps++`.
- Cross-group exits write the TLS `g_spu_trampoline_fn` (TLS guard each time) and return to `SPU_DRAIN`. That costs about 40–60 instructions per hop (ESTIMATE): an out-of-line `spu_tailret_enabled()`, the lockstep, interrupt and pchist checks, then an indirect call.
- **Indirect branches always go to the full ~700-line resolver.** `spu_lifter.py:1177` emits `spu_indirect_branch(ctx)` by name, so the `SPU_IB_DISPATCH`/`spu_indirect_branch_mt` fast path (`runtime/spu/spu_dispatch_mt.c`) selected by `-DSPU_USE_DISPATCH_MT` is never used. That is 112 sites in the solver and 300 in collide (VERIFIED).

**Channels.** `spu_wrch`/`spu_rdch` are out-of-line calls, and each MFC channel goes through `mfc_for()` (section 5).

Static counts in the T183 build copy (`grep -c`):

| Image | funcs | groups | trampoline exits | indirect | MFC_Cmd | GETLLAR sites |
|---|---:|---:|---:|---:|---:|---:|
| solver `341580667` | 959 | 90 | 210 | 112 | 83 | 8 |
| collide `491898574` | 1,766 | 169 | 302 | 300 | 77 | 11 |
| raycast `308733018` | 1,582 | 144 | 274 | 235 | 50 | 7 |
| animation `406081863` | 821 | 88 | 132 | 101 | 73 | 7 |

Solver group `000097E0`: about 3,270 SPU instructions compile to 61,395 x64 instructions. That is about 19 per SPU instruction statically, cold paths included; the hot-path ESTIMATE is 8–12 for integer/shuffle blocks and 20–30 for float-dense blocks.

Representative generated shape (schematic):

```c
ctx->gpr[T] = spu_fma(ctx->gpr[A], ctx->gpr[B], ctx->gpr[C]); /* about 55-60 x64 instructions, exact emulation */
spu_wrch(ctx, MFC_LSA, ctx->gpr[L]);                          /* out of line; mfc_for: global SRW lock */
if (ctx->gpr[P]._u32[0] == 0) { ctx->pc = X; g_spu_trampoline_fn = F; return; } /* TLS write, drain hop */
```

### 4.2 Float emulation: offline benchmark (VERIFIED, synthetic)

`generated/analysis/t186/tools/bench_spu_float_t186.c` (private, main checkout) includes the real `spu_helpers.h` and is built with the lifted-SPU flags. Results: Ryzen 5 9600X, normal inputs (helper fast path), 2 passes, ns per 4-lane op. Output is in `bfl_sse41.txt` and `bfl_fma.txt` there.

| Op | Lifted helper | Native SSE | Ratio | Exact candidate (MXCSR RZ+FTZ+DAZ, range check, exact fallback) |
|---|---:|---:|---:|---:|
| `spu_fm` | 2.40–2.47 | 0.23 (`mulps`) | 10.5× | 1.90 (SSE4.1), 1.55 (FMA build) |
| `spu_fa` | 2.79–2.88 | 0.23 (`addps`) | 12× | not built |
| `spu_fma` | 4.28–4.49 | 0.31 (mul+add, not fused, not exact) | 14× | 1.95 (FMA3, needs `-mfma`) |
| `spu_fma` dependent chain | 7.4–7.8 | 2.2–2.4 | 3.3× | |
| `spu_and` (reference) | 0.23 | | | |

- **Why the helpers are expensive:** each op widens to two f64x2 halves (exact), truncates, validates all 4 lanes, and branches to a scalar fix-up when a lane is out of range (`runtime/spu/spu_helpers.h:1028-1130`). That is the cost of bit-exact SPU semantics: round toward zero, denormals flushed, exponent 255 treated as a number, zero results as +0.
- **The candidate** matched the helpers on 192,512 test vectors. It took four iterations to get there:
  - The first test was too weak: an edge lane forced the whole vector to the exact fallback.
  - A strengthened test then exposed two real differences: a −0 sign, and SPU values beyond FLT_MAX where round-toward-zero saturates.
  - Both are fixed in the candidate.
  - This is sampling, not a proof.
- **Limit:** the range check that keeps the candidate exact costs most of its time, so the per-op gain is 1.3–2.2×, not 10×.
- **Unknown:** the frame-level effect, because the dynamic float-op share of solver/collide/Wws time is unmeasured. The solver has 1,726 static fa/fm/fma/fs/fnms sites, against about 3,270 instructions in one group alone.

## 5. Memory-system analysis

VERIFIED in code unless labelled.

**Address translation, bounds, endianness, alignment.** Cheap by design (flat base, one bswap). The cost is in the gates around each access (section 3), not in translation.

**MFC engine lookup, `mfc_for()`.** `runtime/spu/spu_channels.c:390-407` takes `AcquireSRWLockShared(&s_mfc_claim_lock)` and walks a global list on every MFC channel access. That includes plain field writes such as `MFC_LSA` (`spu_dma.h:1619-1623`).
- A GETLLAR is about 4–5 channel ops; a DMA is about 8–9.
- So about 30k `mfc_for` per solver run and about 30k per collide run, from 5 concurrent threads (ESTIMATE from T183 counts).
- The engine is a fixed property of the context, so the lock protects nothing on this path.

**Lock-line lock.** One process-wide TTAS spinlock (`spu_coherency.c:38-54`) covers:
- every GETLLAR (two 128 B copies under the lock);
- every PUTLLC (`memcmp` + `memcpy` + notify walk);
- PPU `stwcx` to lines an SPU has ever reserved;
- SPURS task-set bookkeeping (`cellSpursCreateTask` takes it at least 4 times; see the memory agent's map, section 6).
Unrelated lines contend.

**Sticky reservation bitmap.** `g_spu_coh_bitmap` (`spu_coherency.c:78,106`) is only ever set; there is no clear in the tree. Every later PPU store, SPU PUT or `vm_memcpy` to a once-reserved line takes the global lock and walks all reserving contexts (`spu_coherency.c:231-261`). PUTs copy the whole span under that lock (`spu_dma.h:699-706`).

**Shared counters.**
- `g_spu_putllc_count++`, a plain shared global written by every thread (`spu_channels.c:778`);
- `g_spu_lr_raise++`;
- with `PS3_SPU_TASK_STATS` on, about 3 `fetch_add` per MFC op on one shared image entry. This inflates the arm S/P MFC figures themselves.

**PPU reservations.** `ppu_stwcx32` (`ppu_loader.cpp:1024-1110`):
- a sharded spinlock, plus the global lock-line lock if the line was ever SPU-reserved;
- `lock cmpxchg`;
- a walk of up to 128 PPU contexts.
`reserve_addr` shares a cache line with `cr`/`lr`/`ctr` (false sharing; HYPOTHESIS on cost).

**DMA.**
- Synchronous `memcpy`, so there is no waiting.
- The repeat guard (`spu_dma.h:1252-1290`) sleeps after 256 identical transfers. HYPOTHESIS: small exposure.

**Does the memory architecture limit multicore scaling?** Yes, for SPU work (VERIFIED as design, synthetic as cost):
- every SPU thread's MFC traffic serializes on two global cache lines;
- the solver's spin-poller holds one of them in a tight loop.
PPU-side memory is not serialized.

## 6. Synchronization analysis

### 6.1 Solver GETLLAR sites
Eight unique sites in the solver; source line numbers are in the T183 build copy.

| Site | Shape | Class |
|---|---|---|
| `0x174D4`/`0x17518`, `0x1778C`, `0x17954`, `0x17C88`, `0x17E60`, `0x17F38` | GETLLAR → modify → PUTLLC → retry on failure | Legitimate atomic RMW |
| `0x17638` | Counter take; blocks on `RdEventStat` (LR event) when zero | Legitimate RMW with event wait |
| **`0x1781C`** | GETLLAR, compare a line halfword with the thread's ticket, branch back to itself; no PUTLLC or event wait in the loop | **Spin-poll** (ticket-lock wait between `0x1778C` take and `0x17954` release; HYPOTHESIS on meaning) |

**Classification of the 6,323 GETLLAR per run** (HYPOTHESIS): mostly the `0x1781C` poll. The RMW sites re-issue only on PUTLLC failure (17.4 %), so GETLLAR minus PUTLLC per run would confirm it; T185's `PS3_SPU_LLAR_PROFILE` is measuring spin episodes.

If the hypothesis holds:
- the "97 % on-CPU" includes real busy-waiting;
- each iteration does about 6 out-of-line channel calls, 6 SRW lock pairs and one global lock-line acquisition (two 128 B copies);
- the lock holder's releasing PUTLLC at `0x17954` must win the same global lock against up to 4 spinners.

### 6.2 Is the waiting correct?
- The spin itself is guest semantics: it is the original Havok code. **Its cost is host-made:**
  - on the PS3, GETLLAR of a line is a local cache operation and does not block other SPUs' PUTLLC on other lines;
  - here every GETLLAR serializes against every atomic in the process.
- No evidence of incorrect event signalling or redundant task execution. Task counts per frame are stable (5/5/5/10, T184).
- `SPU_CH_BLOCK` is off, so SPU channel waits are spins. That is legitimate, but costs a core.
- **Do not change semantics:** the correction is to make GETLLAR and PUTLLC as cheap and parallel as on hardware (section 15), not to skip polls.

### 6.3 Lock primitives: offline benchmark
VERIFIED, synthetic. `generated/analysis/t186/tools/bench_spu_locks_t186.c` uses the same primitives as the runtime, not the runtime code; back-to-back ops, worst-case contention; 2 reps.

| Pattern | 1 thread | 5 threads |
|---|---:|---:|
| Private work only | 0.7 ns/op | 1.7–1.8 |
| + global SRW shared acquire/release (`mfc_for`) | 8.9 | **146–158** |
| + global TTAS lock-line lock over a 256 B copy (GETLLAR) | 8.8–9.8 | **295–321** |
| + per-line lock over the same copy, each thread on its own line | 8.8–8.9 | 36 |

In real tasks the lock ops are interleaved with compute, so contention is lower than this. Bound (ESTIMATE): about 30k `mfc_for` per run at 9–150 ns is 0.3–4.5 ms per 10.5 ms solver run, and 6,323 lock-line acquisitions at 9–300 ns is 0.06–1.9 ms. The measured `mfc_ns` (1.15 ms solver, 2.32 ms collide) times only the `MFC_Cmd`/`WrTagUpdate` writes (`spu_channels.c:953-965`), so it is a lower bound.

### 6.4 Frame-thread waits
- **`sys_timer_usleep`:**
  - Implementation: a high-resolution waitable timer plus `timeBeginPeriod(1)` (`runtime/syscalls/sys_timer.c:301-329`).
  - Measured (T121): the guest asks for 250 µs and gets about 517 µs.
  - The 42 calls per frame (21.5 ms) are the guest's back-off poll inside the Havok wait, not extra work.
  - The critical-path cost is only the lateness of the last poll: about 0.3–0.6 ms per frame (ESTIMATE).
- **`cellSpursCreateTask`:** 262 µs per call, 5.2 ms per frame, serial on tid 1 (measured, T184). The work it does is mapped (lock-line lock at least 4×, `ts_lock`, `printf`, fingerprint `memcmp` of the 79–150 KB image). The split is T185's work.

## 7. SPU parallelism analysis

**Lanes and tasks.**
- 5 SPURS lanes (`cellSpurs.c:2194-2201`) plus task threads: pooled or one per run.
- Idle lanes block on a CV (`:1940`), so they don't spin.
- Each admission wakes all lanes (`WakeAllConditionVariable`, `:2139`), a thundering herd (HYPOTHESIS, small).

**Affinity and priority.** None, except ABOVE_NORMAL for guest priority <256 (`runtime/syscalls/sys_ppu_thread.c:488`).

**Oversubscription.** During the Havok waves, 5 tasks + render (32 ms of CPU per frame) + a 12 ms thread + lanes give about 8–12 runnable threads on 6 cores / 12 SMT. T183 shows 97 % on-CPU, but that cannot detect two hot threads sharing one physical core. SMT contention is unmeasured (HYPOTHESIS, 1–3 ms).

**Do the five tasks progress simultaneously?** Their CPU time matches their wall time, so they are running. But if the `0x1781C` poll dominates GETLLAR, part of that running is waiting for a ticket lock. That makes the solver wave partly serialized by a guest lock whose hold time is inflated by host lock contention (HYPOTHESIS; T185's spin-episode data decides).

**Waves are serial by guest design.** Solver (5 × 10.5 ms), then collide (5 × 10.7 ms); the tasks are created on tid 1 between them. Neither more host cores nor work stealing helps, because only faster task execution shortens the chain.

**Wws lanes.**
- Busy about 20 ms per frame each, over the emit-to-spin window.
- 66 % idle across the whole frame.
- The tid 1 spin at `0x50C818` holds a core for 11.9 ms with no pause. It is a pure guest load loop, and it competes with the lanes for SMT resources (HYPOTHESIS).

## 8. Wws rendering pipeline analysis

From prior reports: T37, T70, T84, T85, T151, T154, T162, T168.

| Module | Work | ms/frame (T154, light scene, all AOT) |
|---|---|---:|
| renderablejob (wid 1) | RSX command generation: an opcode interpreter that emits state, shader, constant and draw methods, and skips unchanged matrices. No vertex transform, no culling | 22.2 (132 in a heavy scene) |
| pvsjob (wid 1) | Visibility culling | 11.9 |
| vehiclephysics (wid 2) | Physics | 11.7 |
| others | trails, groundrush, particles, fog | about 4 |

**Outputs and redundancy.**
- renderablejob writes 16 KiB command chunks into guest main memory. The PPU links them with `CALL`, and they are linked to each other by atomically shared counters (`rs+0x24E8`, `rs+0x2560`). The host FIFO walker then decodes them (decode about 3.2 ms, T151).
- Skinning and transforms run in the translated vertex programs on the GPU (`rsx_vertex_fetch.c:45-50`).
- **Geometry is not processed twice.** The duplicated work is that the CPU re-converts and re-uploads all vertex data every frame (38.5 MB, expand 15.7 ms, T182). It is on the render thread, off the critical path.

**GPU offload (do not implement):**

| Candidate | Blocker |
|---|---|
| pvsjob, vehiclephysics | PPU reads the results; readback each frame (VERIFIED, T84) |
| renderablejob | Its output is RSX methods, which D3D12 cannot execute. ExecuteIndirect cannot switch PSOs, so the result would need a readback for CPU decode |

Common blockers for all three:
- shared guest atomics with the PPU;
- 26+ DMA reads per job of PPU-built structures;
- serial, branchy opcode streams: 20–76 jobs per frame is a poor SIMT fit;
- bit-exact SPU float semantics;
- `AGENTS.md` requires AOT translation of original code.

**Verdict:** not feasible as a translation; it would be a reimplementation (ESTIMATE, strong). The lever is faster CPU execution of these three modules. They share the SPU float, MFC and register costs of sections 4–6.

## 9. Renderer architecture analysis

VERIFIED; costs from T151/T182/T183.

- **FIFO:** decoded per word with a `gcm_io2ea` and several reads, then a nested switch. About 3.2 ms per frame.
- **Expand:** strip and fan assembly, attribute fetch, byteswap and conversion to float4, then upload. 15.7 ms per frame, with no cross-frame vertex cache (textures do have one). T162's GPU vertex fetch was bit-identical offline and cut callbacks by 31–37 %, but timed out in game while compiling, so it is off.
- **Caches:** a VS cache of 128 entries with linear scan, and a PSO cache of 256 entries with linear scan. Together with texture work they cost 0.4 + 2.5 ms.
- **Submission:** one `ExecuteCommandLists` per pass and a fence drain per `render_frame`: submit 0.3 ms, wait 0.0, present 0.2.
- **Allocations:** none per draw.
- **Avoidable synchronization:** none on the critical path. The render thread is idle about 35 ms per frame, waiting for guest commands.
- **D3D12 vs Vulkan:** no evidence that the API matters. Replacing D3D12 is not proposed.
- **Indirect effect:** the render thread's 32 ms of CPU per frame shares cores with the SPU and PPU threads. T182 B→D (expand −2.6 ms, frame unchanged) suggests this effect is small.

## 10. Comparison with other recompilation architectures

Public sources only; full URLs are in the T186 research notes and listed in section 16.

| Area | Ours | RPCS3 (JIT) | XenonRecomp / N64Recomp (static) |
|---|---|---|---|
| PPU registers | `ctx` fields; written back at every instruction and call | LLVM function-level SSA | Xenon: opt-in `non_volatile_as_local`, `cr_as_local`, `ctr/xer_as_local`. Its authors report "several ms" of frame time saved in Unleashed Recompiled. N64: `ctx` fields |
| PPU memory | Inline load behind 4 global gates; every store an extern call | Flat base + bswap, inline | Base pointer + bswap, inline |
| Indirect calls | Hash probe behind about 20 gates, about 15 ns | Table indexed by address | Xenon: perfect-hash table; N64: lookup |
| SPU registers | `ctx->gpr` in memory, heavy spills | LLVM: function/"mega" units keep values in SSA (background knowledge, not verified) | n/a |
| SPU float | Bit-exact emulation, 10–14× native | XFloat accuracy is configurable; the default is "approximate" (native-like) | n/a |
| SPU SIMD | SSE4.1 only | SSE/AVX2/AVX-512 (`SHUFB` → VPERMB) | n/a |
| Reservations | One global spinlock, sticky bitmap, list walks | Per-128 B-line version stamp with optimistic reads; several PUTLLCs at once (PR #8462); no VM mutex while waiting (#11240) | n/a |
| GETLLAR polling | Each poll pays the full locked path | Spin detection: yield, park on a notifier, skip the notify when a PUTLLC changes nothing (PRs #12523, #12544, #6728) | n/a |
| Task scheduling | 5 lanes + a thread or pooled thread per task | "Max SPURS threads" 6, preferred SPU threads | n/a |
| GPU offload | None | None | None |

**Reported 60+ FPS Pacific Rift.**
- Every public 60 FPS report found is RPCS3 with community game patches. A 60 FPS patch changes guest frame pacing, so these are not like-for-like benchmarks. Examples: Push Square, September 2022; the RPCS3 wiki notes split-screen struggles.
- No public native or static recompilation of Pacific Rift was found, at any frame rate. A Vulkan "SPU to GPU" project was not found either.
- The nearest public project, `robbe1912/motorstorm-mv-recomp` (MotorStorm 1, MIT tooling, modified ps3recomp runtime), states that no playable native race has been demonstrated.
- No unreleased source was examined.

**Upstream ps3recomp** (sp00nznet) is at v0.18.0 (October 2026). Our pin is v0.15.0. The public README does not document a register-caching or float fast path; I did not evaluate an upgrade.

**What this implies** (HYPOTHESIS): RPCS3 reaching 60 FPS with patches on comparable CPUs means the same Havok and Wws SPU code can run well over twice our speed when registers live in SSA, floats are approximate and reservations are per line. Of these, only the first and the last are available to us without giving up bit-exactness.

## 11. Category A: confirmed inefficiencies

Confirmed by code inspection and, where stated, synthetic measurement. Frame impact is not measured for any of them.

| # | Location | Current behaviour | Why inefficient | Evidence | Correction | Risk | Validation |
|---|---|---|---|---|---|---|---|
| A1 | `runtime/spu/spu_channels.c:390-407` `mfc_for`, called from `spu_wrch:962`, `spu_rdch:1572` | Global SRW shared acquire + list walk on every MFC channel access | The engine is fixed per context; 5 threads bounce one cache line | Code; synthetic 8.9 → 146–158 ns under 5-way contention | Cache the engine pointer in `spu_context` at claim time; write `MFC_LSA/EAH/EAL/Size/TagID` inline | Low: no guest-visible change; lifetime handled at claim/release | `test_spu_coherency`, LFQueue, DMA, torture tests, plus a 5-thread MFC bench |
| A2 | `runtime/spu/spu_coherency.c:38-54` `spu_lockline_lock`; GETLLAR/PUTLLC `spu_channels.c:614-895` | One process-wide lock for every reservation op, with two 128 B copies under it | Unrelated lines serialize; spinners block the lock holder's release | Code; synthetic global 295–321 ns vs per-line 36 ns | Striped per-line locks (hash of line address); GETLLAR as an optimistic version-stamped read (seqlock), as in RPCS3 `vm_reservation.h` | Medium: atomicity and LR-event semantics must hold; PPU `stwcx` and DMA PUT must take the same stripe | Coherency and LFQueue tests, a multi-thread PUTLLC linearizability stress, an RPCS3-oracle diff |
| A3 | `spu_coherency.c:78,106` | Reservation bitmap only ever set | Every later write to a once-reserved line takes the global lock and walks all contexts | Code (no clear in the tree) | Clear or reference-count on reservation loss or release, or keep a per-line reserver count | Medium: a missed notify = a lost LR event | Coherency tests with reserve/release churn |
| A4 | `runtime/spu/spu_helpers.h:1028-1130` | Bit-exact float emulation through f64 widening and lane validation | 10–14× native per op | Synthetic benchmark (section 4.2) | Exact fast path: MXCSR RZ+FTZ+DAZ native op, range check, existing exact fallback; `-mfma` build for fused ops | Medium-high: needs MXCSR set and restored around every host call from SPU threads; exactness must be proven | `spu_float_referee.py`, `test_spu_float_*`, exhaustive/edge sweeps, a Havok output-state hash diff offline |
| A5 | `tools/spu_lifter.py:1177` | Emits `spu_indirect_branch` by name | Bypasses the built `spu_indirect_branch_mt` musttail fast path; each `bi`/`bisl` goes to a ~700-line resolver | Code, generated counts (112/300/235/101) | Emit `SPU_IB_DISPATCH` | Low-medium: the MT path's coverage must be checked | `test_spu_chain`, dispatch tests, SPU-only relift of affected images |
| A6 | `tools/ppu_lifter.py`, `ppu_recomp.h:92`, `ppu_loader.cpp:2216` | Every PPU store an extern call with a 5-global gate and `/GS` | Forces `ctx` writeback and gate reloads; about 30 instructions | Code and disassembly; T152 −31 % offline on a store-heavy function | Integrate T152 inline stores and page gates | Medium: the watch, coherency and raw-SPU paths must stay correct | `scratch/ppu_conformance`, T152 tests, full suite |
| A7 | `ppu_lifter.py:1893-1911` | CR built and stored at every compare | About 12–14 instructions per compare, at 4.65 M lift-wide sites | Code and disassembly | Lift-time CR liveness: keep the compare in a local when the field is dead before the next write | Medium: mfcr/mtcrf and calls need conservative barriers | PPU conformance, full suite |
| A8 | `spu_drain.c:21`, `spu_context.h:876`; PPU `DRAIN_TRAMPOLINE` | TLS trampoline writes pay the MSVC on-demand TLS guard | `__dyn_tls_on_demand_init` check at every write (42 sites in one PPU function, 103 in one SPU group) | Disassembly | Constant-initialized TLS, or `/Zc:tlsGuards-` | Low | Rebuild and the full suite |
| A9 | `spu_channels.c:778` | Plain shared `g_spu_putllc_count++` from all SPU threads | Cache-line bounce on every PUTLLC | Code | Per-thread counter | Low | Suite |

## 12. Category B: strong hypotheses

| # | Hypothesis | Evidence | Needed |
|---|---|---|---|
| B1 | The solver's 6,323 GETLLAR per run are mostly the `0x1781C` ticket spin, so part of the 10.5 ms solver run is waiting | Code shape; RMW sites retry only on 17.4 % PUTLLC failures | T185 spin-episode profile, or GETLLAR−PUTLLC per site |
| B2 | Host MFC costs are 1.5–2× the measured `mfc_ns` (11–22 % of task time) | `mfc_ns` excludes setup channel writes and their locks | A timer around whole channel sequences |
| B3 | SPU registers in memory plus spills cost about 2× over register-resident code | 2.4 ctx operands per instruction, 6.7 KB frame; T158's hot loop was about 60 x64 instructions for 8 SPU instructions, 14 of them state stores | A relifted image with locals, timed offline |
| B4 | SMT/core sharing costs 1–3 ms in the Havok and Wws windows | 8–12 runnable threads on 6 cores; no affinity | An affinity A/B |
| B5 | `cellSpursCreateTask`'s remaining 262 µs is dominated by lock-line lock waits while solver/collide hold it | It takes the global lock at least 4×; 10 creates fall inside the Havok wait | T185's create profile |

## 13. Potential path to 60 FPS

**Model.** The frame is a serial chain:

| Segment | ms | Shortened by |
|---|---:|---|
| H: Havok wait | 25.0 | Solver/collide task speed, plus 10 creates and pickup |
| P: post-Havok | 23.0 | About 17–20 ms PPU + about 3.5–4.5 ms of creates |
| W: emit + gap + spin | about 19.6 | Wws lane speed; tid 1 waits for the lanes |
| Other | about 0.9 | |

**Rules.** Savings within a segment are not additive across overlapping causes. A segment can't drop below its slowest parallel task. SPU-side gains apply to both H and W, while PPU gains apply to P and part of W (emit/gap). All figures are ESTIMATES with wide ranges.

| Scenario | Changes | H | P | W | Frame | FPS |
|---|---|---:|---:|---:|---:|---:|
| Now | | 25.0 | 23.0 | 19.6 | 68.5 | 14.6 |
| **Conservative** (runtime only, no relift) | A1, A2, A3, A8, A9, pool default, create-cost fix (T185), affinity, usleep | 19–23 | 19–22 | 16–19 | 55–64 | 16–18 |
| **Moderate** (SPU + PPU codegen) | + A4, A5, A6, A7, SPU registers as locals in groups, AVX2/FMA build | 12–16 | 14–18 | 10–14 | 37–49 | 20–27 |
| **Aggressive** (redesign) | + function-level SPU translation with register allocation, PPU registers as locals (Xenon-style), reservation-wait parking. GPU offload excluded (section 8) | 7–10 | 10–13 | 6–9 | 24–33 | 30–42 |

**60 FPS (16.67 ms) needs every segment 3.5–4.5× faster at once**, and needs W, which depends on renderablejob's serial command streams, below 5 ms. None of the evidence supports that. The original game also targets 30 FPS on the PS3 (public reports, not verified here), so the 60 FPS RPCS3 results rely on a frame-pacing patch.

**Conclusion:** 60 FPS is not realistic without a major redesign, and is speculative even with one. 30 FPS is the credible target, and it needs at least the moderate scenario.

## 14. Ranked optimization roadmap

See `TOP_10_BOTTLENECKS.md` for the action plan. In order:
1. MFC de-serialization (A1–A3, A9).
2. Make the GETLLAR spin cheap: optimistic read; coordinate with T185.
3. Exact SPU float fast path (A4).
4. SPU registers as locals within groups, plus `SPU_IB_DISPATCH` (A5) and the TLS guard (A8).
5. PPU inline stores and page gates (A6).
6. Remaining `cellSpursCreateTask` cost (T185 owns).
7. PPU CR liveness (A7).
8. PPU registers as locals.
9. Thread placement and affinity.
10. usleep tick.

Not recommended: renderer vertex caching (off the path), Wws GPU offload (infeasible), replacing D3D12 (no evidence), more indirect-call work (T153: no gain).

## 15. Recommended first implementation experiment

**SPU MFC/atomic de-serialization, opt-in (`PS3_SPU_MFC_FAST=1`), runtime-only, no relift.**

1. Cache the MFC engine in `spu_context` when it is claimed; drop `mfc_for`'s SRW lock and list walk from `spu_wrch`/`spu_rdch`. Setup channels become field stores.
2. Replace the global `g_lockline` with a striped lock (for example 4,096 stripes by line address). PPU `stwcx`, DMA PUT to reserved lines and SPURS bookkeeping must take the same stripe.
3. Per-thread `g_spu_putllc_count`.
4. Leave the sticky bitmap (A3) for a second step, because its fix touches LR-event delivery.

**Why first:**
- It is confirmed by code and synthetic measurement.
- It shortens both H (all four Havok images) and W (all Wws lanes), and it is the host cost that turns the solver's guest spin into contention.
- It needs no relift and changes no guest-visible semantics: the same atomicity, now per line.

**Coordination with T185.** It is outside T185's create-task and GETLLAR-profiling scope, but must not be implemented in T185's worktree. T185's `PS3_SPU_LLAR_PROFILE` result sizes item 2.

**Validation:**
- offline: `test_spu_coherency`, LFQueue, DMA, torture and `test_spu_task_pool`;
- a new 5-thread GETLLAR/PUTLLC linearizability stress with flag off and on;
- `bench_spu_locks_t186.c` rerun against the real runtime;
- the full suite compared with the base failure list.

**Then one authorized A/B:** T184 arm P against P + flag. Measure H, W, per-task ms, `mfc_ns`, GETLLAR/run and FPS.

**Expected:** 1–5 ms (ESTIMATE). If H and per-task ms don't move, the cost is compute and item 3/4 come first.

## 16. Evidence and limits

**Tools (private, main checkout `generated/analysis/t186/tools/`, untracked `.c`):**
- `bench_spu_float_t186.c`, output in `bfl_sse41.txt` and `bfl_fma.txt`;
- `bench_spu_locks_t186.c`;
- `zchk_t186.c` (zero-sign check).

**Compiler.** `build/llvm/clang+llvm-23.1.3`, through `generated/analysis/t169/tools/env_t169.cmd`.

**Limits:**
- Host-instruction counts are static, from disassembly.
- Lock costs are measured on primitives, not the runtime.
- The float candidate is sampled, not proven.
- No dynamic op mix, executed-instruction count or helper-call count per frame exists. That needs an instrumented run (`PS3_SAMPLE` wiring is in T185's scope).
- LeOffice was running during the benchmarks.

**Public sources:**
- github.com/RPCS3/rpcs3: `SPURecompiler.h`, `vm_reservation.h`, `system_config.h`, PRs 6728, 8462, 11240, 12523, 12544, 16644;
- github.com/hedge-dev/XenonRecomp README;
- github.com/N64Recomp/N64Recomp README;
- github.com/sp00nznet/ps3recomp;
- github.com/robbe1912/motorstorm-mv-recomp;
- wiki.rpcs3.net MotorStorm: Pacific Rift;
- pushsquare.com, September 2022.
