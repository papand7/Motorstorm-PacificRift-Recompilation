# SPU_LATENCY_OPTIMIZATIONS (ranked, exact only)
| # | Candidate | Evidence | Modelled saving | Status |
|---|---|---|---|---|
| 1 | JobBatch hand-off latency (handler usleep(200) ~550 us; 2.2-2.4 ms/frame summed, 1.65 in vehiclephysics) | Kksr77 split VERIFIED | up to ~1 ms if halved | Fix 1 (PS3_USLEEP_SPIN_LR) showed nothing with Fix 2 on (n=2). A retry must cover both the handler poll and the main wait at 0x94CCA8, judged by wait-site time not fps. HYPOTHESIS |
| 2 | `--fast-lower`/chain for Wws reloc lifts (LS gate removal, +4-11% on Havok) | lift reading, Havok replay | PVS+renderable ~26 SPU-ms/frame, critical path <= ~0.3 ms (renderable wait is contention) | needs whole-job replay harness (none exists). BLOCKED |
| 3 | MFC lean path | bit-exact microbench | ~0.1 ms | too small |
| 4 | More Havok work | Havok wait 2.1 ms in short waits | <= 0.3 ms | deprioritised |

No SPU runtime change has evidence for >= 1.5 ms. Nothing was implemented.
