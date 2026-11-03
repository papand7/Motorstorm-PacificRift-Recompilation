# T37 — MotorStorm WWS Job AOT Preparation

Branch `agent/t37-wws-aot` (worktree `ps3recomp-t37`, from T33 `0568549`), local only. No launch, merge or push.
Commits: `ad8c7f8` (SPU microstep link fix), `bb072a3` (relocatable job AOT + trace records + tests).
Private outputs: `generated/analysis/t37/` (retail_jobs.py/json, modules/, lift/, job_report.py, fuzz_retail.py).

## 1. Retail job identification — VERIFIED (static)

- 31 WWS job images in the decrypted `EBOOT.elf`. Header = `.SpuGUID` (16 B of `ila $r2`) + `.JobCheckData`
  (+0x10 entry offset, +0x14 size+0x20, +0x18 bss, +0x20 magic `0xC0DEC0DE`, +0x28 link base 0x4000); code at +0x30.
- **Names come from the retail EBOOT itself**, not from dev-build similarity: name table `0x103D86C` `{name*, EA, size}` (27),
  records `{char[0x20], ea, size}` at `0x1236458/0x1236480` (spuconstraints, spuxform), LibMP3 SPU ELFs referenced at `0x10D3D68/74`.
  All 13 dev names occur in retail; similarity corroborates 12, `squishandordervisjob` is ambiguous by similarity and settled by the name table.
- **Load path (Wws_Job PM, LS 0xA00–0x3700):** code base = `roti $r3,$r31,10` with `$r31 = mpya slot,size,base` (0x1DC8),
  stored to LS **0x1320** (0x22FC); entry = base + hdr[0x10]; `bisl $r0,$r5` at 0x3210, return point **0x3214**.
  The base is chosen at run time (a slot allocator), not fixed at 0x4000 — VERIFIED from disassembly; actual bases in play — BLOCKED (needs trace).
- **Relocation:** no relocation table in the images; no bra/brasl/lqa/stqa. But most modules build **absolute link-base addresses with `ila`**
  (`ila $r2,0x414C; bi $r2`, switch-table bases) and hold absolute pointers in data (e.g. `0x4070`). So they are *not* fully
  position-independent — VERIFIED. Whether the game runs them away from 0x4000, or the PM patches them, is HYPOTHESIS → the trace decides.
  Either way the AOT is safe: ila immediates are lifted unchanged (same as interpreter/hardware), and patched bytes would fail the hash → interpreter.
- Overlays: code slots are reused by later GETs; handled by invalidation (below).

| # | Retail name (source) | EA | Size | Entry | bss | Dev-build match (shingle sim, header fields) | Float % | Lifted fns | Hand-offs |
|---|---|---|---|---|---|---|---|---|---|
| 0 | step1module (name table) | 0x0FB2C00 | 0x1FA0 | +0x1DA0 | 0x40 | — | 10.8 | 103 |  |
| 1 | step2module (name table) | 0x0FB4C00 | 0xFA0 | +0xE10 | 0x20 | — | 0.7 | 102 |  |
| 2 | vehicledeformation (name table) | 0x0FB5C00 | 0x1BB0 | +0x1910 | 0x7860 | vehicledeformation (0.759, 4/4) | 9.6 | 87 |  |
| 3 | CullEmittersModule (name table) | 0x0FB7800 | 0x1010 | +0xD20 | 0x20 | — | 5.8 | 66 |  |
| 4 | CullEffectorsModule (name table) | 0x0FB8880 | 0xD90 | +0xB10 | 0x20 | — | 4.6 | 63 |  |
| 5 | BasicParticleFillerModule (name table) | 0x0FB9680 | 0xEA0 | +0xD10 | 0x20 | — | 4.9 | 61 |  |
| 6 | Particle3DFillerModule (name table) | 0x0FBA580 | 0x1020 | +0xE20 | 0x20 | — | 4.4 | 63 |  |
| 7 | OrientatedParticleFillerModule (name table) | 0x0FBB600 | 0x1020 | +0xE70 | 0x20 | — | 5.4 | 61 |  |
| 8 | OrientatedParticle3DFillerModule (name table) | 0x0FBC680 | 0x1020 | +0xE70 | 0x20 | — | 5.4 | 61 |  |
| 9 | OrientatedStretchedParticleFillerModule (name table) | 0x0FBD700 | 0x10A0 | +0xEA0 | 0x20 | — | 5.6 | 61 |  |
| 10 | OrientatedStretchedParticle3DFillerModule (name table) | 0x0FBE800 | 0x10A0 | +0xEB0 | 0x20 | — | 5.6 | 61 |  |
| 11 | ParticleSortModule (name table) | 0x0FBF900 | 0xA20 | +0x890 | 0x30 | — | 0.3 | 58 |  |
| 12 | ProcessEmittersModule (name table) | 0x0FC0380 | 0x8DE0 | +0x8110 | 0x20 | — | 3.1 | 313 |  |
| 13 | ProcessEffectorsModule (name table) | 0x0FC9180 | 0x1E90 | +0x1BA0 | 0x20 | — | 14.9 | 92 |  |
| 14 | spupathfinding (name table) | 0x0FCB080 | 0x1920 | +0x1780 | 0x30 | — | 1.6 | 121 |  |
| 15 | occjob (name table) | 0x0FCCA00 | 0x6730 | +0x6410 | 0x60 | occjob (0.798, 4/4) | 3.3 | 307 |  |
| 16 | pvsjob (name table) | 0x0FD3180 | 0x27A0 | +0x2490 | 0x160 | pvsjob (0.714, 4/4) | 8.6 | 124 |  |
| 17 | squishandordervisjob (name table) | 0x0FD5980 | 0x16A0 | +0x13F0 | 0x20 | ambiguous: pvsjob 0.738 / squishandordervisjob 0.725 | 0.8 | 93 |  |
| 18 | groundrushjob (name table) | 0x0FD7080 | 0x3B20 | +0x3950 | 0x820 | groundrushjob (0.882, 4/4) | 2.2 | 165 |  |
| 19 | groundrushvisibilityjob (name table) | 0x0FDAC00 | 0xD20 | +0xB20 | 0x20 | groundrushvisibilityjob (0.703, 4/4) | 0.8 | 67 |  |
| 20 | groundrushsquashjob (name table) | 0x0FDB980 | 0xF20 | +0xD70 | 0x20 | groundrushsquashjob (0.697, 4/4) | 8.7 | 61 |  |
| 21 | screenrushjob (name table) | 0x0FDC900 | 0x2920 | +0x2640 | 0x30 | — | 12.8 | 89 |  |
| 22 | renderablejob (name table) | 0x0FDF280 | 0xF6D0 | +0xEE40 | 0x153E0 | renderablejob (0.807, 4/4) | 2.8 | 1018 | 61 |
| 23 | generatefogtable (name table) | 0x0FEE980 | 0x15A0 | +0x13D0 | 0x30 | generatefogtable (0.739, 4/4) | 7.9 | 99 |  |
| 24 | octreequery (name table) | 0x0FEFF80 | 0x1320 | +0xFA0 | 0xD0 | octreequery (0.576, 4/4) | 0.8 | 88 |  |
| 25 | trailsupdate (name table) | 0x0FF1300 | 0x14A0 | +0xF90 | 0x300D0 | — | 0.8 | 119 |  |
| 26 | vehiclephysics (name table) | 0x0FF2800 | 0x8240 | +0x7DE0 | 0x160 | vehiclephysics (0.904, 4/4) | 8.1 | 400 | 7 |
| 27 | spuconstraints (spu name record) | 0x0FFAA80 | 0x1420 | +0x1210 | 0x30 | spuconstraints (0.995, 4/4) | 10.7 | 87 |  |
| 28 | spuxform (spu name record) | 0x0FFBF00 | 0xD20 | +0xB30 | 0x10 | spuxform (0.873, 4/4) | 2.8 | 72 |  |
| 29 | LibMP3 stereo job (LibMP3 SPU ELF) | 0x0FFFC80 | 0x19A10 | +0x12040 | 0x21D0 | — | 3.2 | 840 |  |
| 30 | LibMP3 surround job (LibMP3 SPU ELF) | 0x101A380 | 0xD9A0 | +0x9A50 | 0x780 | — | 5.2 | 665 |  |

Hand-offs (words the lifter cannot translate, run by the interpreter): renderablejob 61, vehiclephysics 7 — all in string/rodata tails.

## 2. Trace readiness — READY, not run (needs authorization)

`PS3_FTRACE_SPUJOB=3214:1320` (return point : code-base word) adds per job, at its return:
kind 26 span (entry, wid), 27 interpreted insns, **28** module id (FNV-1a32 of GUID) + base + size, **29** AOT image + result.
Report: `python generated/analysis/t37/job_report.py <run dir> [t_lo t_hi]` → per retail module runs, total/median/p95/max ms,
share, ns/insn, load bases, AOT state (`--selftest` passes). Remember: unset all `vm_inline_ok` triggers for clean timing.

## 3. AOT architecture — VERIFIED offline

- `tools/spu_lifter.py --reloc`: lift once at link base; every guest-observable PC (links, drain returns, ctx->pc, lqr/stqr) is
  `SPU_RA(a) = (a + ctx->reloc_delta) & 0x3FFFF`; functions keyed `| 0x80000000`; untranslatable words → interpreter hand-off;
  refuses absolute branches/lqa/stqa and `--chain-chunks`. Non-reloc output byte-identical to before.
- `tools/lift_wws_reloc.py`: header check, lift, `wws_reloc_register.c`, manifest. All 31 retail modules lift, register and compile.
- Runtime (`spu_reloc.h`, hook in `spu_indirect_branch`): at PM entry match identifier, entry offset, 16 entry bytes, then full-span hash
  on first use at a base; install into a `resident_code` slot (`link_base`); any overlapping GET drops the slot.
  UNKNOWN / MISMATCH / NO_SLOT / `PS3_SPU_WWS_AOT=0` → interpreter. No guessed code runs.
- ISA fix found on the way (`ad8c7f8`): `spu_smc_microstep` splatted brsl/bisl links into all 4 words; now preferred slot only.

## 4. Offline tests — VERIFIED

| Test | Result |
|---|---|
| `tests/test_spu_reloc_job.py` synthetic jobs (int/shuffle, float, branch, switch, LS, DMA, completion, reloc) at bases 0x4000/0x8C00/0x15C00/0x30000 | 39/39, interp vs AOT byte-identical (LS, GPRs, output); AOT interprets 0 insns; same with `-mavx2` |
| Scenarios: install, resident, replace, relocate, unknown, mismatch, overlapping GET | all pass |
| **Retail** function differential (`fuzz_retail.py`), 145 leaf functions in all 31 modules, 40 random states, bases 0x15C00 and 0x9400 | **0 mismatches** (5025 + 5062 trials compared) |
| `tools/test_spu_lifter_reloc.py`, `tools/test_spu_jobspan.py`, test_ftrace_spurs, existing SPU tests | pass / unchanged vs T33 |

Note: an earlier fuzz selection included epilogues that reload `$r0` from random stack and "returned" into random LS (hangs, spurious diffs);
selection now excludes `$r0` writers.

## 5. Benchmark (synthetic, best of 5×200 jobs) — VERIFIED, not game timing

| Job | Interp | AOT (SSE4.1, default) | AOT + AVX2 (separate config) |
|---|---|---|---|
| float+switch | 415.7 µs | 152.4 µs (2.7×) | 71.6 µs (5.8×) |
| int+switch | 344.2 µs | 43.8 µs (7.9×) | 42.8 µs |
| int | 220.2 µs | 23.0 µs (9.6×) | 23.6 µs |

First-use hash of a 0xF6D0 span ≈ 8 µs. Default unchanged; AVX2 applies to lifted job TUs only.

## 6. Blockers

1. **BLOCKED (authorization):** trace run with `PS3_FTRACE_SPUJOB=3214:1320` → per-module cost, real load bases (settles the ila/0x4000 question).
2. **BLOCKED (authorization + port change):** A/B run with the AOT TU linked; needs CMake to compile `lift/` + `wws_reloc_register.c` (`port/` untouched).
3. **Coordination (T24):** review of `ad8c7f8`, the `spu_indirect_branch` hook, `resident_code.link_base` / `reloc_delta` fields, lifter `--reloc`.
4. Real-PM validation of dispatch (only a fake PM is exercised offline).
