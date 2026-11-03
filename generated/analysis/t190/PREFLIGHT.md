# T190 preflight

**Result: FAIL.** The session is RDP, not console, and Godot was running. Per the brief, the run stopped before any launch. **0 of 4 launches used.** Every other check passed. BLOCKED.

| # | Check | Result | Label |
|---|---|---|---|
| 1 | T189 code commit | `ps3recomp-t190` worktree, branch `agent/t190-inline-store-ab`, at `a26240c5` (T189), clean. T187/T188/T189 branches untouched | VERIFIED |
| 2 | Executable | `build/motorstorm-t190/MotorStormPacificRiftRecomp.exe`, SHA-256 `9e77bd4b12d2ea66f6bd35d16018d07e2fbd71593a4cce30efd15892ba1f8453`, 411,701,248 B. Runner copy `generated/analysis/t190/ab/exe_r/` pinned (`exe_r.sha256`); `prepare r` verified the hash | VERIFIED |
| 3 | One exe for both arms | `run_t190.py`: P and B both map to `exe_r`, and the pin is checked at every launch | VERIFIED |
| 4 | Compile-time inline stores present | Configure printed `Inline stores: lifted sources built with PPU_INLINE_STORES` (78 `PPU_INLINE_STORES` defines in `build.ninja`). `ppu_recomp_000.cpp.obj`: 57,247 `vm_st_inline` and 47,938 `vm_st_page` references | VERIFIED |
| 5 | Runtime switch | `envcheck`: B vs P = `{'PS3_VM_STORE_INLINE': ('1', None)}`, the only difference | VERIFIED |
| 6 | Gate not vetoed in B's env | `vm_page_gates_init` ignores the switch if `PPU_WVAL`, `PPU_WWATCH`, `PT`, `PPU_RESV_STORE`, `PS3_VM_STATS`, `PS3_VM_STORE_FAST=0`, `PS3_NULL_SWEEP`, `SPU_ATOM_EA` or `PS3_TRACE` is set, or if a write watch or `ppu_vm_size` is armed. None of these is in the env: `PS3_TRACE_FILE` has no watch line, and `port-t161` sets `ppu_vm_size = 0` on Windows. B must log `[vm-gates] PS3_VM_STORE_INLINE=1: lifted stores inline on N of 57343 pages` | VERIFIED (code + env); banner pending a run |
| 7 | Locked path for reserved pages | The runtime is T189's unchanged code: `spu_coh_reserve` clears the store page before marking a line, and the fill runs under the lock-line lock. `test_vm_page_gates`: 0 failures (inline store to a reserved line raises LR; 300,000 random ops inline vs out of line) | VERIFIED |
| 8 | Warm shader cache | `ab/shader_cache` is a copy of T185's (5.2 MB, filled by T183–T185 race runs), with `RSX_SHADER_CACHE=3` | VERIFIED (present) |
| 9 | Offline correctness tests | `test_vm_page_gates` 0 failures; `test_vm_store_fast` 89/89; `test_ppu_regpromo --seeds 4` 0 failures (mutants caught). Logs in `generated/analysis/t190/logs/`. T189's full suite on the same commit: 161 pass, 43 skip, 3 known failures | VERIFIED |
| 10 | No unrelated differences | T190 P vs T184 arm P (both runners' `build_argv`): only the paths of `PS3_TRACE_FILE` (identical content) and `RSX_SHADER_CACHE_DIR` (copy). Lifted sources: the 79 files of `ppu-t173-staging`, byte-identical (hard links; `ppu_hle_nids.cpp` a copy). Only `ppu_recomp.h` differs: T189's page-gate block replaces the old `vm_inl_ok` (`make_t190_staging.py`; 98 diff lines). Log: `ab/env_vs_t184.txt` | VERIFIED |
| 11 | Session | `query session`: `>rdp-tcp#0 … Active`, console `Conn`; `TerminalServerSession` True. The runner requires `>console` | **FAIL** |
| 12 | Competing workloads | Godot (LeOffice plugin) was running: refused by the T190 runner. LeOffice itself hosts this session (allowed, as in T184/T185). No Ollama, llama-server, Epic or EA. GPU 1 %, 6,848 MiB VRAM free, 30.4 GB RAM free | **FAIL** (Godot) |

Dry run: `generated/analysis/t190/ab/dryrun_p1.txt`
(`PREFLIGHT FAIL: not a console session …; conflicting processes running: ['godot']`).

## What the user does to run it

1. Sign in at the console (not RDP).
2. Close Godot.
3. Run:

```
py -3 generated/analysis/t190/ab/run_t190.py dryrun P p1
py -3 generated/analysis/t190/ab/run_t190.py launch P p1
py -3 generated/analysis/t190/ab/run_t190.py launch B b1
py -3 generated/analysis/t190/ab/run_t190.py launch P p2
py -3 generated/analysis/t190/ab/run_t190.py launch B b2
py -3 generated/analysis/t190/tools/analyze_t190.py
```

The runner enforces the order Pp1, Bb1, Pp2, Bb2, a cap of 4 and no retries (`launches_used.jsonl`, empty now).
