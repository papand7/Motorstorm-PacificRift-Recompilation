# Handoff: unfinished work and its state (2026-11-27)

Work was paused on 2026-11-27 evening. All source is committed: this repository at `main` (see `git log`), the
runtime `ps3recomp-vkgame` at branch `ps3recomp/spu-speed` in the private repository `papand7/motorstorm-ps3recomp`
(commit `90404eb8`, clone it as `ps3recomp-vkgame/` next to this repository). Detailed notes, tools and captures
live in the private `generated/analysis/<task>/` folders on the development PC (not published); each item below
names its folder.

## Working rules for whoever continues

- Only one agent/session may run the game at a time: take the folder lock `build/.game_lock` with `mkdir` (retry),
  wait until no `MotorStormPacificRiftRecomp.exe` runs, launch, `rmdir` the lock afterwards.
- Game runs need a connected Windows session (RDP connected or the console); a disconnected session makes the
  runner's preflight refuse.
- Test runner: `generated/analysis/vksync/ab2/run_vk.py` (`K_BY_TAG` arms; run
  `generated/analysis/perf60/tools/order_next.py K<tag>` before each launch). Builds: `build/ck_build.cmd` into the
  shared tree `build/motorstorm-vkgame-100-ppucc2`, then copy the exe to a slot `ab2/exe_<name>/` with a `.sha256`.
- Count fps in game frames (flips), never presents: presents repeat frames and inflate fps by up to ~45 %.
- Shadows may depend only on the sun and the casters, never on the camera or the vehicle.
- Every option must be configurable in game and in the launcher; nothing auto-set.
- Commit only on request; run `python tools/audit_public.py --staged --private-reports` before committing.

## 1. Frame generation (`RSX_FRAMEGEN`: Off / Light / On) — PARTIAL

- Built: FSR 3.1 frame generation without AMD's swapchain (On) and an own light interpolation pass (Light); needs
  the FSR 3.1 upscaler and HDR off; DLL downloaded by the launcher; setting in game and launcher.
- Measured (RTX 5060, AI race, 30 fps): 60 shown per second, game stays at 30 real; GPU per generated frame
  0.06 ms (Light) / 2-3 ms (On); +17-26 ms latency.
- Open: frame pacing evenness (median step 16.5 ms but P99 ~57 ms in fg3; later fixes fg6-fg12 not verified);
  the HUD mask never produced a mask (HUD doubles/smears on hard landings); V-Sync On, 45 fps, repeat runs, the
  Radeon 890M. Notes: `generated/analysis/framegen/RESULTS.md`; last exe slot `exe_fg12`.

## 2. LAN multiplayer (Medius stand-in) — BLOCKED on a crash

- Working: LAN page (Host / Find / Leave) and server browser (verified with two instances); local DNS answers;
  NP ticket/entitlement calls; a Medius (SCE-RT) server prototype in Python
  (`generated/analysis/lan_e2e/tools/medius_lan.py`, private) that gets the host through the RT handshake, ticket
  login, locations, stats and the EULA page; the game then creates its Matching2 party room.
- Crash: right after the room is created the main thread aborts inside the game's free() (abort 0x701E14, called
  from `func_00359BF8`, delete at 0x359E14). Not voice (same with `PS3_VOICE=0`); stand-in buffer writes checked and
  bounded. Next step: trace bb 0x359E14 (r31 and its first words) to name the deleted object. The Medius server's
  lifetime must outlast the lock wait (start it with 3600 s).
- Still to do after that: lobby with both players, the race transport (DME), then porting the server into the
  game, the "Server name" setting, LAN docs for two PCs. Notes: `generated/analysis/lan_menu/RESULTS.md`.

## 3. World-fixed shadows (`RSX_SHADOW_TILES`, default on) — PARTIAL

- Done: mirrored lookup fixed, object-matrix fit, persistence v4 (still casters never expire, movers cleared),
  map-fed static store (default on), soft edges.
- Open: the game shows denser shadow blobs under palm groups and lighter grass than ours, although casters and
  depths match. Next test: `RSX_SHADOW_TILES_DUAL` mode 16 on slot `exe_w1` (does the game's own receiver lookup sit
  offset from its casters?). Notes: `generated/analysis/shadowtiles/RESULTS.md`.

## 4. Race performance (CPU-limited, ~40 fps on the development PC) — NOT STARTED / PARTIAL

- Finding: the guest main thread spends ~14 ms per frame in the world update, mostly waiting on SPU jobs, and ~8 ms
  in render submission waiting on visibility jobs. Faster SPU jobs are the main lever (expected 15-30 %).
- Done: audio update on its own thread for 1.00, default on (-0.53 ms main thread, +1 % fps, within noise);
  CPU thread placement for hybrid CPUs (`threadplace`, default Off; needs an A/B on the Ryzen AI 9 HX 370, steps in
  `generated/analysis/cpu_placement/RESULTS.md`).
- Not started: the SPU speed-up (build on the T183-T193 reports in `generated/analysis/`); faster translated
  main-thread code; multi-threaded draw recording; asynchronous pipeline compilation against stutter.

## 5. Low-end options (Performance page and launcher preset) — BUILT, PARTLY MEASURED

- Shadow Quality, Texture Quality, Effects Density, Opponent Detail, Dynamic Resolution floor, Wreck Debris, Boost
  Blur, LOD "Lowest", 480p resolution, low-end preset in the launcher. Shadow Low measured +10 % fps / -530 MB VRAM.
- Open: the rest of the in-game measurements (queue `generated/analysis/lowend_opts/tools/queue1.sh`), the in-game
  Performance page seen in game, the preset on the HX 370. Not possible (no game setting): AI update rate, grass
  density, depth of field, physics limits other than debris.

## 6. Launcher features — DONE, small gaps

- Benchmark tab: fly-through Happy Jungle + Wildfire with per-map and combined results; AI race. Gaps: retry and
  Stop only unit-tested; a ~2 s early fly hitch; the exit timeout line fix not verified.
- Decrypt automatically (RPCS3 fetched, used on a copy, deleted). Gap: Windows 10 cannot unpack RPCS3's .7z.
- Import save (RPCS3 saves load in game). Gap: encrypted console saves need the player's own save tool folder
  (no official source ships the keys).
- HD texture pack installs its own numpy, Pillow and Real-ESRGAN. Gap: not clicked through in the UI.
- Player name for network play.

## 7. Renderer odds and ends

- `RSX_VK_REBAR` (default on): GPU-read host buffers prefer CPU-writable video memory on a heap over 1 GB;
  compiled but not run in game.
- Ideas not started: XeSS upscaler, 360p (needs render scale below 1 in the renderer), Enhanced foam water
  (not this release). DLSS dropped (licence terms do not fit this project).
