# ppucc: PPU codegen rework (MotorStorm 1.00, Vulkan) -- private analysis

Work tree: ps3recomp-opt (uncommitted). Lifted text stays private (scratch under D:/motorstorm/ppucc).

## Lifter flags (ps3recomp-opt/tools)
- `--fast-mem gated|frame|gateless` (ppu_fastmem.py): per-function vm_base copy, one volatile (possibly
  unaligned) host access + bswap per guest access, store gate = vm_st_page only. `gated` keeps every page
  gate (exact); `frame` also drops the load gate for D/DS-form loads off r1/r2/r13 (exact under the ABI);
  `gateless` = EXPERIMENT, needs a fault-backed runtime (gcm ref-poll / raw-SPU mailbox reads would be skipped).
- `--vmx-locals [all|auto]` (ppu_vmx_locals.py): vector registers as host-lane SSE locals; file synced
  around calls/returns/unrecognised statements (narrow sync for statements that only name vector regs);
  remaining float helpers called direct + vperm as pshufb. `auto` keeps the plain form where sync cost >
  4x the taken-over ops (AUTO_MAX_RATIO, tuned on real bodies). Needs -mssse3 -mfma (PORT_PPU_VMX_INLINE).
- Off: VERIFIED byte-identical to the previous lifter (96 lifts: random programs with/without VMX, trace
  hooks, nv-locals, mm-snap/elide/fp-one-nan).

## Gates
- test_ppu_fastpath.py, 12 seeds (work/gate12d.log): full state + vector state (new DIFF_VR=1 in the
  difftest fixture; reference = per-lane VMX helpers, g_vmx_fast=0), out-of-line and inline stores,
  8 variants incl. combos; DIFF_ABI=2 + DIFF_VR on ABI programs with nv-locals combos; 5 mutants all caught.
  VERIFIED 0 failures. Existing tests mm_snap, drain_elide, vmx_lanes, lift (1533 conformance), fp_one_nan,
  vcmp_record_cr6, nv_locals: PASS.
- Real TUs ppu_recomp_026/013 of the twin rewritten + compiled with game flags: 0 errors (VERIFIED).

## Measurements (tools/wl3.py = wl2 + per-exe harness floor; net = fn - floor; min-of-N, alternating)
Harness floor is ~14-30 ns/call; many "hot" functions are floor-bound under window inputs (excluded: net<30ns).
System was noisy (other agents): floor drifted 14->50 ns, cv up to 0.3; non-vector functions where two arms
have identical code differed by up to +-40% on single runs.
See work/conf2.log, work/race1.log, work/hot3.log, work/held3.log.

## Results (net of floor, functions with baseline net >= 30 ns)
| arm | flags | conf2+race1 (n=101) geomean | min | race-time-weighted (6.9% of main-thread samples) |
|---|---|---|---|---|
| F | --fast-mem frame | 1.14 | 0.87 | 1.16 |
| Z | --fast-mem frame --vmx-locals all | 1.63 | 0.91 | 1.44 |
| A | --fast-mem frame --vmx-locals auto | 1.63 | 0.90 | 1.45 |
Earlier (hot3/held3): gated 1.16/1.20; gateless 1.22-1.30 alone, 1.55-1.59 with vmx-locals (not legal yet).
Vector bodies 2-9x; scalar bodies 1.0-1.6x. Below 0.95 under A: 005EB2F0 0.90 (vmx-locals overhead, F alone 1.53),
00512728 0.94 and 002C4824 0.94 (no vector code: A == F code, i.e. noise).

## Race profile (generated/runs/20261117-004031-vk-Kksr23, windows 10-16)
ppu_self 43-49%, of which func_0050C818 13-19% is a spin-wait (`while (load(r3+0x2560) != r9)`), so real
guest compute is ~30% of main-thread time, spread over ~420 functions; wait_under_guest 42-59%.

## Build
generated/ppu-v100-ppucc (twin + --fast-mem frame --vmx-locals auto via the lifter's pass functions;
tools/relift_twin.py) -> build/motorstorm-vkgame-100-ppucc/MotorStormPacificRiftRecomp.exe
SHA-256 8ae3e635ca893304a1e62ed8db0f4583d07b75fb2454950626a0cec6248dc619 (twin config + PGO profile + ThinLTO;
LTO cache on D:). Not run.
