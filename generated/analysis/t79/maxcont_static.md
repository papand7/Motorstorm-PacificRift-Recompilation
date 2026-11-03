# T79: maxContention the game passes to SPURS workloads (static analysis)

Read-only analysis of the lifted PPU code. Nothing was built or run.

## Shared struct P (global G = [toc+0x7278], P = [G+0])
Written in func_00436680, ppu_recomp_001.cpp:
- 596256-596261: P = malloc(0x1C) (func_00751B78); [G+0] = P; **[P+4] = 5** (li r3,5; stw r3,4(r11)).
- 596263-596269: r3 = [P+4] = 5, then func_00436338(nSpus=r3, name=[toc+0x72A0], ppuPrio=func_00438160()-1, r6=1).
- func_00436338 (ppu_recomp_009.cpp:~527720-527760): _cellSpursAttributeInitialize(attr, rev=2, sdk=0x240001, nSpus=5, spuPrio=100, ppuPrio, exitIfNoWork=0), then SetNamePrefix(len 0xC), then cellSpursInitializeWithAttribute. It returns the CellSpurs*, which is stored at [P+0] (596271).
- So P = {CellSpurs* "MotorStorm2", nSpus = 5}. A 12-line scan after all 28 `[r2+0x7278]` loads found no other store to +4.

## Per workload
| wid | Path | maxContention | Label |
|---|---|---|---|
| 0, 1, 2 (Wws_Job none/EvoDefault/EvoHigh) | func_004B0ED0 (ppu_recomp_002.cpp:132928-132955): r29 = func_007569C8 -> func_00436290 = [[toc+0x7278]+0] = P. Ctor r5 = [P+4], r6 = [P+0]. Ctor func_004B33E8 (ppu_recomp_010.cpp:17767, 17828) stores r5 unchanged at [this+4]. 17874 loads r6 = [this+4] for the stub 0x756B08 call -> func_00726428. That function copies r6 to r28 and on to SP+0x70 (ppu_recomp_003.cpp:258802, 258837/258899) for both _cellSpursWorkloadAttributeInitialize calls (0x726504, 0x7265F8). | **5** | VERIFIED |
| 3 (Multistream/LibMP3) | ppu_recomp_001.cpp:596285-596292: r10 = [G+0] = P; r4 = [P+0]; r6 = [P+4]; stub 0x755F78 -> func_00726428. | **5** | VERIFIED |
| extra (func_00C55348) | ppu_recomp_005.cpp:563394-563397: li r6,1; bl func_00726428 at 0xC554A4 | **1** | VERIFIED (constant). Whether or when this path runs is not established. |

## Other findings
- Ctor handling of r5: `cmpwi r5,1` (17786) only picks the float at [this+0x14]: 1.0f (0x3F800000) when r5 != 1, 0.5f (0x3F000000) when r5 == 1 (17830, 18225). It does not clamp or derive anything; maxContention = r5 is passed through.
- cellSpursSetMaxContention: stubs.json has no import for it, so the game never calls it.
- Discrepancy, HYPOTHESIS: the Multistream workload's CellSpurs (r4 = [P+0]) is the same 5-SPU instance created by func_00436338, not a separate 1-SPU SPURS. If a 1-SPU "Multistream" SPURS exists, it is not the r4 at 0x4369A8. Check at runtime.
- So the game requests maxContention = 5 (= nSpus) for wids 0-3. The value 1 is used only by the func_00C55348 workload.
