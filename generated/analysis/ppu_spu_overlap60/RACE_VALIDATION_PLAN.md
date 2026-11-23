# RACE_VALIDATION_PLAN (not executed; needs authorization)
1. Attribution races (main and ppucc2, 1 each, ABBA-ordered with repeats if allowed): critical-path trace starting after race entry (entry ~103 s, use 125:20), PS3_SAMPLE_MAIN=2 per-function sampler, ETW context-switch trace. Goal: where the ppucc2 2 ms landed (serial vs overlapped) and ready-to-run delays.
2. Only if an exact candidate X passes offline tests: arms main, ppucc2, main+X, ppucc2+X. ABBA, >= 3 valid runs each, run_vk.py tags from Kksr94 (ORDER must be extended in order), quiet-PC preflight and quality gate, reject contended runs.
3. Metrics: fps, p50/p95/p99 frame time, main compute/wait split (sc141, sc130), SPU job spans, scheduling, GPU time.
