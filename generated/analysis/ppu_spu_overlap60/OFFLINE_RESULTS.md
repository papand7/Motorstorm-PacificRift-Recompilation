# OFFLINE_RESULTS
- Ran `tools/overlap77.py` on D:/rt60_runs/ksr77_cpath.txt (output in overlap77_out.txt). Numbers in FRAME_DEPENDENCY_GRAPH.md. Caveat: "SPU active" counts any job.
- Not done: no code changes, no isolated experiment, no Phase 6 dependency model. Reasons: no candidate with evidence; whole-job Wws replay harness missing; per-function read/write sets missing.
- No race, build, commit or deploy.
- Limit: one trace of 825 frames; run was 41.2 fps (profiling overhead small vs about 40 in Test A).

## Sampler races (authorized 2026-11-20; run_vk.py arms K/ksr94-97, exe pins m=33253d9d main, q=60256822 ppucc2)
- Kksr94/95: INVALID for comparison with Kksr86-93 (arm env copied an old K config: no PS3_SIM_PACE, no wait counters, no FSR). Their 005346A8 difference (2.7 % vs 10.1 %) did NOT reproduce (below).
- Kksr96/97: Kksr86 env (overlap60_env.json in ab2) + PS3_SAMPLE=2, PS3_SAMPLE_MAIN=1. Both quality OK.
  - fps 36.33 vs 36.43, p50 30.4 vs 30.0 ms, main usleep 9.53 vs 10.45 ms/frame, evq 1.64 vs 1.78 (main vs ppucc2; n=1 each). The sampler itself costs ~5 fps.
  - func_005346A8 (task slice) 7.8 % vs 7.1 %: no difference. VERIFIED (n=1).
  - ~60-65 % of main-thread samples land in runtime code mis-attributed to SPU bodies (samp_lookup extent bug, see roadto60_next 7.3); the per-report top-12 truncation hides small functions. This sampler cannot split the 5.9 ms serial compute by function. BLOCKED: needs the precise main-thread profiler (ppusamp build, PS3_SAMPLE_MAIN=2) built for BOTH exes, or the sampler extent fix.
- Files: samp_ksr94..97.txt, tools/samp_sum.py.

## Exact sampler (PS3_SAMPLE_EXACT, isolated D:\motorstorm\ps3recomp-samp; tools/patch_samp_exact.py, tools/build_samp.cmd)
- Fix: attribution by the exe's .pdata (read once at startup, lock-free; chained entries resolved), so runtime code no longer lands on the lifted SPU body linked before it; PS3_SAMPLE_MAIN's stack walk then credits the lifted caller. Opt-in, default off.
- Self-test in both races (VERIFIED): 62,301 of 62,301 mapped bodies with .pdata map back to themselves, 0 bad; a runtime probe maps to no guest function.
- Races Kksr98 (main 5cee6819) / Kksr99 (ppucc2 b3123adb), Kksr86 env + sampler: 35.37 / 35.91 fps, main usleep 9.90 / 10.88, evq 1.69 / 1.78 ms/frame. Quality OK, n=1 each.
- The mis-attributed SPU buckets are gone. Main-thread samples now land on guest functions: waits 0x4B63F0 (JobBatch light-mutex spin) 15.5 / 17.2 %, 0x5346A8 (task slice) 7.4 / 9.5 %, 0xA4C590 (semaphore), 0x72E1E0 (GcKernel poll); compute A32E78, BE0BE0, 3CB350, A19EF0, B3C970, 435EB0 ...
- LIMITS (why no main-vs-ppucc2 per-function delta is claimed): (1) each 10 s report prints only its top 12, so mid-size functions drop in and out; (2) samples credited by the stack walk (waits in runtime code) are not separated from direct guest RIP samples, and the walk takes the first word on the stack that maps to lifted code, which can be a stale return address (e.g. A4C590 21 % in ppucc2 but absent from main's top list). Needed: full histogram dump at exit + a direct/stack-walk flag per sample.
