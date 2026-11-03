# T186: top 10 bottlenecks, action plan

Baseline: a 68.5 ms frame (T184 arm P). The serial chain on tid 1 is:

| Segment | ms |
|---|---:|
| H: Havok | 25.0 |
| P: post-Havok PPU | 23.0 |
| W: Wws window | about 19.6 |

Paths are in `ps3recomp-t183`. Evidence labels:
- **A**: confirmed in code, and measured in a synthetic benchmark where stated;
- **B**: strong hypothesis;
- **C**: speculation.

No impact is measured in game. Details are in `ARCHITECTURE_PERFORMANCE_AUDIT.md`.

| Pri | Optimization | Component | Evidence | Potential (ESTIMATE) | Difficulty | Risk | Validation |
|---:|---|---|---|---|---|---|---|
| 1 | MFC de-serialization: cache the engine per context (no global SRW per channel op), striped lock-line lock, per-thread PUTLLC counter | SPU/Memory | A | 1–5 ms (H and W) | Medium | Medium: per-line atomicity | Coherency, LFQueue, DMA and torture tests; new 5-thread linearizability stress; one A/B |
| 2 | Cheap GETLLAR poll: optimistic version-stamped read with no lock, for the solver's ticket spin | SPU/Memory | B | 0.5–3 ms (H) | Medium | Medium: LR events | T185 spin profile first; coherency tests |
| 3 | Exact SPU float fast path: MXCSR RZ native op + range check + existing fallback; FMA build | SPU | A (per op), B (frame) | 1.3–2.2× per float op; frame share unmeasured | Medium-high | High: bit-exactness | Float referee, edge sweeps, offline Havok state-hash diff |
| 4 | SPU codegen: registers as locals within groups, emit `SPU_IB_DISPATCH`, constant-init TLS | SPU | A (sites), B (gain) | Several ms over H and W | High (SPU relift) | Medium | Chain and dispatch tests; per-image offline timing |
| 5 | PPU inline stores and page gates (T152 work, never integrated) | PPU | A | 1–4 ms (P) | Medium (recompile lift) | Medium: watch and coherency paths | PPU conformance, full suite |
| 6 | Remaining `cellSpursCreateTask` cost, 262 µs × 20 calls/frame | PPU/SPURS | A (time) | Up to 5.2 ms (P, H) | Low-medium | Low | **T185 owns it**: wait for its create profile |
| 7 | PPU CR liveness at lift time | PPU | A | 1–3 ms (P) | Medium-high (relift) | Medium | PPU conformance |
| 8 | PPU registers as locals (Xenon-style non-volatile/CR/CTR locals) | PPU | B | Several ms (P) | High (full relift) | Medium-high | Conformance, full suite, in-game A/B |
| 9 | Thread placement: Havok tasks and Wws lanes on separate physical cores; render thread off them | Host | B | 1–3 ms | Low | Low | Affinity A/B |
| 10 | Clear the sticky reservation bitmap: stop global-lock notify walks on once-reserved lines | Memory | A | Unmeasured, probably <1 ms | Medium | Medium: lost LR events | Coherency tests with churn |

Locations:

| Pri | File:line, function |
|---:|---|
| 1 | `runtime/spu/spu_channels.c:390-407` `mfc_for`, callers `spu_wrch` `:962`, `spu_rdch` `:1572`; `runtime/spu/spu_coherency.c:38-54` `spu_lockline_lock`; `spu_channels.c:778` |
| 2 | GETLLAR `spu_channels.c:614-719`; solver site `0x1781C` |
| 3 | `runtime/spu/spu_helpers.h:1028-1130` (`spu__x4_fa`, `spu_fm`, `spu__x4_fma`) |
| 4 | `tools/spu_lifter.py:1177`, `runtime/spu/spu_context.h:174,876,938-947,1034`, `spu_drain.c:21` |
| 5 | `ppu_recomp.h:92,135-165`, `runtime/ppu/ppu_loader.cpp:2127,2216` `vm_store_fast_ok`/`vm_write32` |
| 6 | `libs/spurs/cellSpurs.c:1050-1214`, `runtime/spu/spu_workload.c:1487-1634` |
| 7 | `tools/ppu_lifter.py:1893-1911` |
| 8 | `tools/ppu_lifter.py` register emission; `runtime/ppu/ppu_context.h:53-101` |
| 9 | none today; `runtime/syscalls/sys_ppu_thread.c:488` sets priority only |
| 10 | `spu_coherency.c:78,106,231-261` |

**Do not pursue:**
- Wws GPU offload: outputs are RSX methods or are read by the PPU, and they share guest atomics.
- Renderer vertex caching: off the path; the render thread is idle about 35 ms per frame.
- Replacing D3D12: no evidence.
- More indirect-call work: T153 showed no gain.

**First experiment:** item 1, opt-in `PS3_SPU_MFC_FAST=1`, runtime-only. Offline tests, then one authorized A/B against arm P.

**Path:**
- Runtime-only fixes give about 55–64 ms (16–18 FPS).
- Adding SPU and PPU codegen gives about 37–49 ms (20–27 FPS).
- A redesign gives about 24–33 ms (30–42 FPS).
- **60 FPS is not supported by the evidence.**
