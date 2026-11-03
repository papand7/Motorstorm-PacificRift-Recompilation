# T189 Workstream 1: PPU inline stores in the standard pipeline

Branch `agent/t189-perf-architecture` (ps3recomp, worktree `ps3recomp-t189`, from T188 `f209ad24`); code commit `a26240c5`. Local only: not pushed or merged. No game launch.

## 1. Source

- T152 commit `dcd62dc` (`agent/t152-ppu-recompiler-performance`): one-load page gates for inline loads, opt-in inline guest stores, and the runtime gate tables plus coherence hooks.
- It was never merged; it was absent from `766d3575` and from the lift (T186).
- T189 applied it with `git cherry-pick -n dcd62dc`. The only conflict was the header template in `tools/ppu_lifter.py`, against T188's cold-call thunks. It was resolved by hand, with two deliberate changes (§2).

## 2. What is integrated

| File | Change |
|---|---|
| `runtime/ppu/ppu_loader.cpp` | T152 unchanged: `vm_ld_page[65536]`, `vm_st_page[65536]` and `vm_st_inline`, filled by `vm_page_gates_init` on the first out-of-line access after mapping.<br>Loads: a page is open only where the old per-access test admitted every address of the page.<br>Stores: pages open only with `PS3_VM_STORE_INLINE=1` and no store probe set. They stay closed for the first page and the raw-SPU windows. |
| `runtime/spu/spu_coherency.c` | T152 unchanged: `spu_coh_reserve` clears a line's store page **before** marking the line, and the fill holds the lock-line lock. Every store that needs the reservation path (lock-line lock, LR event) therefore stays out of line. |
| `tools/ppu_lifter.py` (header template) | `vm_write*_inl` with the T152 gate (`vm_st_inline` plus one table byte plus an in-page check), selected only by `PPU_INLINE_STORES`.<br>**Change 1 (T189):** the page-gate *load* test is opt-in too (`PPU_PAGE_GATES`, implied by `PPU_INLINE_STORES`). T152 had made it the default; T189 keeps the original load test by default.<br>**Change 2 (T189):** the inline stores' slow path calls the `vm_write*_cold` forwarders (inline wrappers of `vm_write*`, or `preserve_most` thunks with `PPU_COLD_CALLS`). |
| `tools/test_vm_page_gates.py`, `runtime/ppu/tests/test_vm_page_gates.cpp` | T152's test. One text check was updated for the forwarder: the slow path must call `vm_writeN_cold`, which must call `vm_writeN`. |

## 3. Feature flags

| Flag | Where | Default |
|---|---|---|
| `-DPPU_INLINE_STORES` | lifted TUs (the root port's T152 option `MSPR_PPU_INLINE_STORES` sets it) | off |
| `PS3_VM_STORE_INLINE=1` | run time; without it every store page stays closed, so stores go out of line even in a `PPU_INLINE_STORES` build | off |
| `-DPPU_PAGE_GATES` | lifted TUs: page-gate loads without inline stores | off |
| `-DPPU_NO_INLINE_STORES` | lifted TUs: force stores out of line | — |

**Default behaviour is unchanged, VERIFIED** by `generated/analysis/t189/tools/default_equiv.py`: with no flags, the lifted C bodies and the disassembly of every lifted function (4 programs, 35 functions) are byte-identical to the unmodified `766d3575` lifter and header. The runtime tables are filled in every build, but nothing reads them unless a TU opts in.

## 4. Semantics preserved

| Property | How |
|---|---|
| Endianness | `bswap` per access, as in the out-of-line writer |
| Alignment | aligned accesses use a relaxed atomic store (single-copy atomic, as on Cell); unaligned ones use `memcpy`; an access that crosses a 64 KiB page goes out of line |
| Address translation | `vm_base + ea`, only on pages the runtime opened |
| Memory ordering | relaxed host atomics, the same as the existing inline loads. Guest `sync`/`lwsync`/`eieio` stay fences. Same-address order is kept |
| Reservations | pages with a reserved line are closed before the line is marked, so `stwcx.`/coherent stores keep the lock-line path |
| Exceptions | a store to an unmapped or closed page goes out of line and behaves as before; mapped pages fault and commit exactly as the out-of-line writer's own access does |
| Probes and diagnostics | any store probe set or armable keeps the store gates closed (T152) |

## 5. Interaction with `--promote-regs`

The difftest builds every promotion variant with and without inline stores (seeds 3, 6, 9, 12) using the **real** header block. All variants are identical to the baseline: `CORRECTNESS_RESULTS.md`.

Performance: `REGISTER_PROMOTION_COMPARISON.md`. **Yes**, with inline stores promotion becomes effective on real store-heavy code: 1.04× alone, 1.41× with inline stores, on `func_0096B648`.

## 6. Generated code (synthetic `k_transform`; loop: load, rotate, xor, store)

- **Arm A (baseline):** each guest store is a `call`.
  - Around it, `ctx->gpr[3]` is reloaded and stored, and CTR is decremented in memory: `mov rcx,[rsi+0x18]; add rcx,4; mov [rsi+0x18],rcx; dec qword ptr [rsi+0x410]`.
  - Before the call: `mov [rsi+0x30], r8; mov [rsi+0x38], rdx; add rcx, 0x4000; call vm_write32`.
- **Arm D (inline stores + promotion):** the loop has no `ctx` operand.
  - `cmp byte ptr [rax+r13],0` (load page gate), `mov ebp,[rax+r12-0x4000]; bswap ebp`;
  - `rol r15d,8; xor r15d,ebp` (r6/r7 in registers);
  - `cmp dword ptr [vm_st_inline],0; movzx eax, byte ptr [rax+rdi]` (store gate), `bswap ecx; mov dword ptr [rax+r12], ecx`;
  - `add r12,4; cmp r12,0x207e80; jne loop` (CTR turned into an end pointer).
- Slow paths (`call` to the out-of-line accessors) are out of the loop's straight line.

## 7. Cost

| Item | Measurement |
|---|---|
| Static instructions | inline stores add the gate and fast path to every store site. On T152's three real functions: 18,669 → 19,480 instructions (+4.3 %). On the 24 sampled TU `000` functions: +10 % |
| Object size | real functions: 119,310 → 115,544 bytes (−3 %, fewer call relocations); TU `000` sample: −1 % |
| Compile time | ±10 % (0.73–0.96 s → 0.74–1.08 s per TU sample) |

Execution time: `PERFORMANCE_RESULTS.md`.

## 8. Limitations

- **The run-time switch is required:** a `PPU_INLINE_STORES` build without `PS3_VM_STORE_INLINE=1` pays the gate (one load and a branch) and still calls out.
- **Pages with SPU-reserved lines stay closed** for the process lifetime (T152 design). Titles whose hot PPU stores share pages with SPU lock lines keep the out-of-line path there.
- **Not tested together with T187's `PS3_SPU_MFC_FAST`** (a different branch). The two do not share code paths: inline stores never take the lock-line lock (`RUNTIME_SYNCHRONIZATION.md` §3).
