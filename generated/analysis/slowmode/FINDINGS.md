# Slow-mode races (Kksr2-67): findings

Tools (all read-only on run data): tools/table.py -> table.json, tools/classify.py -> table2.json, tools/sc.py, tools/series.py <n>..., tools/runq.py <tag>... (run-quality gate). Window = race_entry+10 s to last rsx-hb; CPU stats skip the first third of cpu.jsonl. 12 logical CPUs.

## Verdict
Slow mode is host contention during the race, not a lost wakeup in the runtime. Two distinct causes, both external to the game:
1. CPU starvation by concurrent builds (the 5-7 fps runs). VERIFIED correlation, causality PARTIAL.
2. GPU sharing with another game (bf1943.exe / bfbc1.exe) (the 11-25 fps runs, often a mid-race decline). VERIFIED correlation (gpu.csv + cpu.jsonl process list), causality PARTIAL.
Not run order, time of day, exe sha, hdd1/cache state or RDP: cache.dat is 438 MB -> 1853 MB in every run, every exe sha appears in both fast and slow runs, slow runs occur at 06:xx, 12:xx, 18:xx, 19:xx.

## Evidence
- Non-game busy cores = 12*(sys_busy delta share) - sum(game thread %)/100, from cpu.jsonl. Spearman vs fps over 63 runs: -0.68 (sys busy -0.66). Bands: <=2.5 cores -> 33-40 fps; 3-5 -> 20-30 fps; >=8.7 -> 5-7 fps.
- 5-7 fps runs: Kksr12,13,14 (7.3/6.5/11.6; sys busy 99-100 %), Kksr62,65 (5.5/5.3; sys busy 90-92 %, 9.2/8.7 non-game cores). Background process list shows clang-cl.exe/ninja/cmake (sampled 30-220 times, each <=5 % so they never show as a "top" process, but together they use ~9 cores). Their GPU util is 8-14 % (GPU idle), main-thread CPU 45-60 %, main usleep 650-700 ms/s, per call usleep 1.3-3.0 ms (clean: 0.07-0.1 ms), event-queue receive 1.1 ms/call (clean 0.12 ms), calls/s down 10-20x. This is the signature of the PPU main thread and the SPURS lane/worker threads waiting for scheduler time on every hand-off, which is why workers look idle. Kksr62 stays flat at 4-6 fps for the whole race while non-game cores stay 9-10.5 for the whole race (series.py 62): starts at race entry, not mid-race.
- GPU-sharing runs: Kksr44/45/46 (bfbc1.exe), 60/66/37/41/33 (bf1943.exe). gpu.csv shows 87-99 % GPU util and total memory climbing 3.3 -> 6.1 GB (game alone ~2.5 GB) while the game's own work is unchanged. Kksr60: 28 fps until +40 s then 11-14 fps exactly when GPU util goes 54 % -> 99 % and memory 3.3 -> 6.1 GB. Kksr45 same (6.5 -> 5.9 GB stairs, 71 -> 99 %). Mid-race declines (33, 41, 45, 60) follow another process starting a load (bf*.exe memory growth or lld-link.exe appearing in 41 at +34 s).
- My earlier hint "GPU memory 3x in slow runs" is a sampling artifact: Kksr67 (fast) also reaches 2.4-2.6 GB once the race starts. GPU util separates (8-14 % idle for CPU-starved; 70-99 % for GPU-contended; 30-45 % clean).
- Lost wakeup / fallback timers ruled out as the cause (PARTIAL): [lwc-wake] shows timeouts=0 and to_miss=0 in all windows; fallback counts are 29-72/s (poll wakes while idle, same in fast runs). In-race windows with the heavy_draws gate (200) are not logged for 61-65, so the per-wait path is unmeasured for exactly the slow runs. The 100 ms poll would show as exactly 10 fallback/s per waiter; not observed.
- Unexplained: Kksr36 (13.6 fps, sys busy 29 %, other cores 0.4, GPU 18 %, main usleep only 144 ms/s, 2 sc wait rates low). Not contention; HYPOTHESIS: content-level (different race / entry timing, draws 3302/frame is the highest of all runs) or a real stall. Open item; worth a repeat.
- Remaining mid group (Kksr5-8,10,11,16,22,47,58 at 24-29 fps): older exes or 3-5 non-game cores; consistent with the same dose-response, not separable cleanly.

## Mechanism (HYPOTHESIS, consistent with all data)
The race pipeline is many short hand-offs per frame (main ~10 event-queue/usleep waits per frame, SPU task pool wakes, SPURS coordinator). Under CPU oversubscription each hand-off pays a scheduling delay of ms; total frame time scales with hand-offs x delay. Windows timer resolution (Win11 ignoring timeBeginPeriod when the window is occluded) is a second possible amplifier: T167 added hostres_keep() (PS3_KEEP_TIMER_RES=1) only to rsx_d3d12_backend.c; grep finds no call in the Vulkan path nor in ps3recomp-vkgame/runtime, and no run enabled PS3_KEEP_TIMER_RES or RSX_TIMER_DIAG, so occlusion cannot be excluded for any run. UNTESTED.

## Offline/cheap confirmation
1. Repeat one fast config with a synthetic hog (e.g. 8-10 busy loops at normal priority, no compiler) during the race: expect 5-7 fps, usleep ms/call 1-3, GPU 10 %. And the same with 8 loops at BELOW_NORMAL priority (expect near-clean, if the game keeps normal priority).
2. Set PS3_KEEP_TIMER_RES=1 and RSX_TIMER_DIAG=1 in the next A/B batch (no guest effect, diag-only logging of Sleep(1)); also wire hostres_keep() into the Vulkan window init if it lacks it. That separates the occlusion amplifier.
3. Log [lwc-wake] stats in-race (heavy_draws=0) for one batch to remove the lost-wake doubt.

## Fix
No runtime bug found, so no code change was made (nothing edited in shared trees). Operational fix: do not compile or run another GPU game while a race batch runs; run the race wrapper at a priority above builds, or build with -j limited (<=4) / BELOW_NORMAL priority. Priority switch for the game itself was not implemented (SetPriorityClass is a stub in win32_compat but the real Windows runner path was not touched); a default-off env switch like PS3_PROC_PRIORITY=above_normal would be the natural place (HYPOTHESIS that it helps; test with confirmation 1).

## A/B robustness
tools/runq.py <tag>...: per run computes non-game busy cores from cpu.jsonl and GPU util with another bf*.exe present; REJECT when other_busy_cores >= 6 (CPU-STARVED) or an other game is present with mean GPU util >= 70 % (GPU-CONTENDED); warns at >= 4 cores. Verified on Kksr62/65 (reject), 60/44/45 (reject), 61/63/67 (ok); Kksr66 (22 fps, bf1943 present, GPU 53 %) passes with a warning, so also treat "other-game-present" as reject-or-rerun for strict A/B. Add to ab_metrics: report non_game_cores, sys_busy%, gpu_util%, and require an A/B pair to differ by < 1 non-game core and use paired order (ABBA) with the median of >= 3 clean runs. The sampler already records everything needed; no game-side change.
