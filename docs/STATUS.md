# Status — 2026-10-21

## T137: RSX 2x MSAA (2026-10-28, offline, no build/launch)

- Worktree `ps3recomp-t137`, branch `agent/t137-rsx-msaa-fidelity`, base `816a4af` (T133 = T120 + T115 cherry-pick + T113). Commits `5d65601`, `f6f9a48`, `876a403`. Not merged or pushed.
- VERIFIED (race captures I/G): scene `0x00750000`, MRT1 `0x01650000` and zeta `0x00ED0000` are SET_SURFACE_FORMAT antialias 3 (2 samples, pitch 10240); the game reads them back as 2524x710 sample images (pixel x's samples at texels 2x, 2x+1) and resolves itself with one bilinear tap per pair (op 657, fp 0x0074B441). The ANTI_ALIASING_CONTROL value was never captured (alpha to coverage UNKNOWN).
- `RSX_MSAA=1`: 2-sample twins for antialias-3 colour/zeta, guest reads bind per-sample windows rendered from them (no copy), lazy resolve for single-sample readers, no GPU waits. Needs `RSX_GUEST_SAMPLERS=15` (unit 0 is otherwise point and the game's downsample picks one sample).
- Offline: WARP 49/49 + logic 27/27 (debug layer clean); real backend harness: the guest downsample equals the 2-sample resolve (max diff 0), edges smoothed, interior identical, feedback and zeta-as-colour reads correct, 0 debug-layer errors; suite 39/39; TU 0 errors; audit 25 inherited.
- Found: with `RSX_RT_WINDOW=1` (T120) a draw sampling its own bound target reads a never-refreshed (black) window: race ops 594-598; and the zeta-as-colour conversion encodes depth 1.0 as 0xFF0000 (fixed only under RSX_MSAA). Both are water-artifact candidates, unproven.
- Runtime A/B (arms A-D) in `generated/analysis/t137/RSX_MSAA_FIDELITY.md` section 9 needs authorization.

## T133: grainy race rendering, RSX texture sampling and FP precision (2026-10-28, offline, no build/launch)

- Worktree `ps3recomp-t133`, branch `agent/t133-rsx-image-quality`, base `169e618` (T120 on T113). Commits `4a74174` (T115 `17b16cb` mip chains, cherry-picked) and `816a4af`. Not merged or pushed.
- VERIFIED from race capture I (f006502): 3,001 of 8,645 bindings advertise 9-11 mip levels with a mip filter, but only level 0 is uploaded; unit 0 is the static point/clamp sampler, yet the guest asks for LINEAR_MIPMAP_NEAREST/WRAP/bias -0.797 there, including the mask of all 80 alpha-cutout (foliage) draws; the scene is 2x MSAA (antialias 3) rendered single-sampled; alpha test is off (cutouts are shader KIL); aniso 1x everywhere.
- Opt-in fixes: `RSX_TEX_MIPS=1` (T115) + `RSX_GUEST_SAMPLERS=15` (T110) for the faithful sampler state; `RSX_FP_PRECISION=1` clamps FX12/FX9/FP16 results (OPDEST [23:22], previously ignored). RSXI now records `aa_ctl` (0x1D7C), per-FP precision counts and the FP ucode.
- Tests: `test_t133_image_quality` 35/35 on WARP (debug layer, 0 errors); suite 38/38; TU 0 errors; audit 25 inherited BLOCKs only.
- Unverified: in-game effect; FX12/FX9 use in race FPs; alpha to coverage; surf brightness (T120 depth/MRT); 2x MSAA not implemented. Runtime A/B arms A-E in `generated/analysis/t133/RSX_IMAGE_QUALITY.md` section 14 need authorization.

## T120: right-edge streak, RT sampling windows, guest depth/stencil state (2026-10-28, offline, no build/launch)

- VERIFIED (T113 capture G, f006314): the guest samples its 1280x720 scene surfaces through the 1264x711 window it draws (AA-2 targets as 2528x711, `0x01DD0000` as 1264x711); the backend bound the whole 1280x720 resource, so passes stretched the scene and read 16 never-drawn columns (and 9 rows). First visible-path passes: op 544 (`0x00750000` -> `0x01DD0000`) and op 555 (-> backbuffer).
- Fix `235b3e6` (`ps3recomp-t120`, `agent/t120-visual-fidelity`, on `2562ba8`), opt-in `RSX_RT_WINDOW=1`: sampled through a box-copied window of the declared size (`rsx_rt_window.h`). WARP fixture reproduces the streak with the old binding and matches RSX texels with the window; offline suite 32/32 PASS. Not runtime-verified (A/B prepared, needs authorization).
- **Fix `169e618`** (on `235b3e6`), opt-in `RSX_DEPTH_STATE=1`: guest-FP pipelines take the guest depth write mask, depth compare and stencil (`rsx_depth_state.h`; `rsx_commands` now decodes 0x032C and the two-sided/back-face registers). VERIFIED from captures G/I: 36 race draws test without writing (blended shore/water) but were written; op 466 uses ALWAYS; 442 draws stencil-tag and the velocity pass `fp_0074CE81` tests NOTEQUAL 255, all ignored. The shore draws and the velocity pass read their own zeta as colour, so the backend bound the shared depth buffer instead; now that zeta stays bound. WARP + debug layer 40/40.
- VERIFIED (captures): the scene size is dynamic (1259..1265 x 708..712 per frame), so `235b3e6` would have waited for the GPU on nearly every frame; `169e618` retires resized windows instead and adds the window for zeta-as-colour reads (2524x710 of 1280x720).
- VERIFIED: post-fix race frames bind 0 fallback pipelines; 0 of 183 dumped race programs contain an unhandled opcode or skipped CAL/RET. COLOR_MASK_MRT/BLEND_ENABLE_MRT are now recorded in RSXI (`mrt_regs`); honouring them needs their captured values (HYPOTHESIS). Suite 34/34 PASS. Not runtime-verified. Report: `generated/analysis/t120/VISUAL_FIDELITY.md`.

## T113: race white-out root cause and runtime validation (2026-10-27, authorized builds + 11 launches)

- **Fix `19d6b6d` (ps3recomp-t113):** CPU-read render targets are written back to guest memory by default (`RSX_RT_READBACK=0` opts out). Exe sha256 `8264aa1a...cdca1` (19d6b6d + `RSX_VPC_WATCH_LANE`/`_MS` instrumentation).
- VERIFIED (presented race-intro frames, all runs `present_occluded=0`): with write-back off (arm A) the game's `c33.x` is pinned at 35.300 and the race renders as a white sheet. With write-back on (B, B2) `c33.x` follows the scene (settles at 1.04) and the race-intro scene is visible and correct (B2 `frame_059`, 281 s), except one camera shot (~185-235 s) that goes white again.
- VERIFIED (PT trace of `func_004C3778`): in that shot exposure sample point 0 (0.15, 0.70) of `0x07EBA600` reads exactly 0; one zero pins Emax (50.0, now VERIFIED). The presented image is not black there, so the zero comes from inside the GPU luminance/exposure chain. Resolved below.
- VERIFIED no effect: `RSX_ATTR0_CONST=1` admits 0 draws (239 827 still dropped into `0x00ED0000`); `RSX_RTPOOL_GF=1`. No black presented race frames on this exe (T106's alternating black dumps do not reproduce).
- **Fix `2562ba8` (ps3recomp-t113, `agent/t113-black-race-repair`):** guest fragment programs are read through their END (`rsx_fp_span.h`, at most 64 KiB) instead of a fixed 4096 bytes; programs within 4096 bytes are read as before; `RSX_FP_SPAN=0` restores the old read. Exe sha256 `36b1e607...a911d` (= `2562ba8` + `40d1ccf` RSXI MRT pass snapshots + `74fd084`).
- VERIFIED (RSXI captures F/G, `40d1ccf`): the zero at exposure texel (2,11) comes from scene MRT1 `0x01650000` = 0 along the sea/sand shoreline (op 502 `fp_0074B181` -> 320x180 -> ... -> 10x5 -> `0x07EBA600`). Nothing draws MRT1 there: the shore draws (ops 488-489, blended ONE/INV_SRC_ALPHA, sampling scene depth) use `fp_07200641`, 4848 bytes, whose truncated translation called `_rsx_expand_input` undeclared (fxc X3004), so its PSO was null and its draws never rendered. `DEPTH_OFF=1` (arm H) leaves the strip at 0: not a depth rejection.
- VERIFIED (arm I, fix on; control J = same exe with `RSX_FP_SPAN=0`): 185-235 s `c33.x` 0.95-1.11 (J: 35.3 from 200-220 s, frames 88-92 % white); the white shot is correctly exposed (`t113/runtime-I-20261027-182926/png/shot_195_211_224.png`); no compile failures (J: 16); the black shoreline strip is gone (pure-black px per dump max 22 vs 3893 in B2/J). Offline suite 31/31 PASS incl. new `test_fp_span`.
- PARTIAL: the recovered shore draws show as a bright surf band; its exact look against real hardware is unverified. A streaked 16-px column at the right edge remains (the 1264x711 guest viewport inside 1280x720 host targets; not addressed). The fxc build of guest FPs folds `x != x` NaN tests even with IEEE strictness (VERIFIED offline, `t113/fxc/`); not the cause here, not changed.
- Report: `generated/analysis/t113/BLACK_RACE_ROOT_CAUSE.md` §9-§10.

## T25: vertex-buffer growth fix, clean baseline and SPU job timing (2026-10-25, offline, dedicated build, no launch)

Report: `generated/analysis/t25/PERFORMANCE_FINDINGS.md`.

- **Fix (VERIFIED offline):** `ps3recomp-t25` `agent/t25-vpvb` `2361249` (on `307b08a`). `vp_vb_grow` no longer copies the frame out of the write-combined UPLOAD buffer. The old buffer is kept (`vpvb_hold`, `vp_vb_budget.h`): the overflowing frame replays from it at its own capacity, and it is released after the next `render_frame` GPU drain. In the D3D12 benchmark the 192→512 MB growth step fell from 2.97–7.29 s to 36–43 ms, with no new GPU wait. Tests: `tools/test_vpvb_hold.py` (new; a mutation fails 9 checks), `test_draw_rejection.py` updated, and 17 other backend runners pass with none skipped. It merges cleanly with every `agent/t24-*` branch.
- **`RSX_RTVIS` (VERIFIED):** setting it at all (even empty or `0`) clears `vm_inline_ok` (`ppu_loader.cpp:1596-1608`). That sends every lifted PPU load (5.7 M `vm_read32` sites) through the out-of-line diagnostic accessor. The effect is runtime-only: no relift or rebuild is needed, but the variable must be absent. So every T17/T18 FPS figure was measured without the fast path.
- **Perf branch:** `ps3recomp-t25-perf` `agent/t25-perf` `991337d` = `3b38721` + the fix + `[vm] inline guest loads on|OFF (<var>)` at startup + `PS3_FTRACE_SPURS=1`. The SPURS option only records: kinds 23 kick, 24 lane pick and 25 policy-module run, linked by a per-workload kick sequence.
  - Exe: `build\motorstorm-t25-perf-991337d\MotorStormPacificRiftRecomp.exe`, sha256 `104ff7534ff353a145fb74d4971591f57a243148b1c252d1059967a08e48ab01`.
  - The shared PPU staging hash was unchanged across the build.
- **Prepared, NOT run (needs approval):** `scratch	25un_t25_ab.ps1`.
  - Run A is the clean baseline (T18 profile without `RSX_RTVIS`). Run B is identical plus `PS3_USLEEP_SPIN=1`.
  - Each run uses a private hdd1 copy of the pinned snapshot, so the shared `generated/hdd1` is not touched. Both arms pass `-DryRun`.
  - Analysis: `generated/analysis/t25/ab_report.py`. It reproduces T18 (75.2 ms median, 13.17 FPS, 26.8 ms CV back-off, 21.2 ms pre-flip silence).
- **Runs (authorized, done):** A and B (`generated/runs/20261025-183416-perf-t25-ab1-a`, `-183635-perf-t25-ab2-b`). Both ended with `milestone_reached`, with inline loads on and the same exe.
  - Garage, 67-118 s: A 13.10 FPS (75.5/83.5/87.2 ms median/p95/p99), B 13.74 FPS (72.3/78.9/82.8 ms).
  - B costs +1.26 cores and reaches the garage 25 s later. Short sleeps are a minor factor.
  - Removing `RSX_RTVIS` gave no gain over T18. The PPU load path is not the limit.
  - Neither run grew the vertex buffer, so the fix was not exercised in-game. There were no gaps and no lifetime errors.
  - New lead (HYPOTHESIS): SPURS wid 1 waits 2.3 ms median and 11.7 ms p95 from kick to lane pick. Details: `PERFORMANCE_FINDINGS.md` §13.
- **BLOCKED:** a per-job completion watch belongs in `spu_channels.c` (PUTLLC), which `agent/t24-spu` is changing.

## T24: performance, synchronisation and upstream audit, offline (2026-10-25, no launch, no build of the game, no code change)

Report: `generated/analysis/t24/UPSTREAM_PERFORMANCE_AUDIT.md`; scripts, benchmarks and outputs: `generated/analysis/t24/perf_audit/`. The concurrent inFAMOUSreborn compatibility audit (other session): `generated/analysis/t24/INFAMOUS_AUDIT.md`.

- Upstream: `whompay/inFAMOUSreborn` `2e9405c` (read-only clone `scratch/t24/infamous`). "Renderer frame overlap" only sets `RF_TRIPLE=1`/`RF_EARLY=1` in `installer/infamous.toml`; upstream's own log calls RF_TRIPLE "no gain". MotorStorm has no render thread, but the guest never waits on the RSX in normal garage frames, so frame overlap is not on the critical path (VERIFIED from the T18 traces).
- 75 ms garage frame (VERIFIED from the T18 traces, all four runs alike):
  - main per frame: ~27–29 ms condition-variable waits (5–6 waits), a ~21 ms silent tail before the flip (the `0x10CE8F40` Present spin, INFERRED to be on main), ~24 ms other code;
  - main is CPU-busy whenever it is not waiting (host thread 0.61 cores);
  - RSX drain and encode overlap the next guest frame, which is why −14 ms of RSX prep did not change FPS. Remaining unknown: SPU job time behind the ~50 ms of waiting.
- Measurement caveat (VERIFIED): every T17/T18 perf run (and the prepared T22 wrapper) sets `RSX_RTVIS`, which disables inline guest loads (`ppu_loader.cpp:1596-1608`). The 13 FPS baseline includes diagnostic load overhead.
- Long gaps (VERIFIED; corrects T18):
  - every garage stall is main polling the RSX `ref` in `0x72E1E0` with `usleep(30)`;
  - the ON-only 1.6 s / 3.0 s gaps start at `[VPVB] ... grown: 393216 -> 1048576 verts` (ON2 99.4 s, ON3 103.4 s). OFF1 never grew; T18 misread its initial allocation line;
  - `vp_vb_grow` copies a full 96 MB parity out of the write-combined UPLOAD buffer. Offline D3D12 benchmark: 3.3–4.1 s for the copy vs 36–72 ms for create+map;
  - the trigger was the single 790-draw frame in each ON run (393,216-vertex cap reached; normal frames 305,607 in all runs). Whether that frame depends on the switches is a HYPOTHESIS.
- Sleep precision (VERIFIED, `sleep_bench.c`): the high-resolution timer `usleep` returns after ≥506 µs for any request of 1–250 µs on this machine. In-game `usleep(200/250)` costs ~565 µs. `PS3_USLEEP_SPIN=1` (existing) is exact but spins.
- Other gaps found:
  - `sys_lwcond` signal is a no-op and wait is `Sleep(1)`, with the timeout ignored (`ppu_sysprx.cpp:344-369`);
  - none of the inFAMOUS runtime switches exists in MotorStorm;
  - `SPURS_LANE_OVERCOMMIT`/`PAR_LANES` exceed hardware contention and must not be ported;
  - MotorStorm's WWS kicks go through `cellSpursReadyCountStore`, which wakes the coordinator at once.
- All of the above also holds at the primary `307b08a`.
- Ranked candidates:
  1. no-copy `vp_vb_grow`: retire the old buffer after the frame's replay;
  2. sub-ms usleep accuracy: A/B `PS3_USLEEP_SPIN=1` first;
  3. real `sys_lwcond` signal and timed wait.
- Proposed next step (approval needed): implement C1 isolated with tests, then a clean-baseline run without `RSX_RTVIS` and a `PS3_USLEEP_SPIN=1` run; add SPURS policy-module spans to ftrace.

## T23: path to the first race, offline (2026-10-25, no launch, no build, no code change)

Supporting files: `generated/analysis/t23/`.

- Baseline (VERIFIED):
  - Primary branch `motorstorm/v0.17-integration` = `307b08a`. It is not checked out in any worktree except the detached `ps3recomp-307b08a` (clean).
  - `ps3recomp-int` is on `agent/t18-c38-trace` `8f7ac89` (307b08a + c38 tracing), with one pre-existing modified file (`scratch/ppu_conformance_run.bat`).
  - Latest primary exe: `build/motorstorm-int-nm-307b08a/MotorStormPacificRiftRecomp.exe`, SHA-256 `96D9DEE10AC111A36162EE200FCA92D639169BBB356A816A0B591DABC61DBC22`. It was built from `generated/ppu-hooked-staging`, so `PS3_TRACE fn=` works on it, and it was used by run `20261025-102805-garage-capture-probe`.
  - Nothing from the T18/T22 performance branches (`ps3recomp-t17` `3b38721`) is integrated, and none is needed here.
- Where the game stands (VERIFIED from capture `generated/introskip/t16_view/f002064_bb.png`): the garage with the rider, a ◀▶ selector bubble, an info box and the ✕ ○ □ △ button bar. This matches `mainmenu.gui` (Festival / Wreckreation / Garage / Options / MotorStore), the first screen that waits for input. Its text is not drawn (see font, below). That the page is `mainmenu` is INFERRED (page changes are not logged).
- Frontend-to-race state machine (GUI scripts VERIFIED in `garage_menu/FINDINGS.md`; game-code steps VERIFIED statically here):
  1. `mainmenu` Festival Accept, gated on `GetPageOpacity() > 0.5` → `GameTypeSetFestival` `0x76AF40` (stores 1 at `+0x26D4` and `+0x26E0`) → `festivalguide`.
  2. Zone Accept → `SetSelectedZone` `0x33848` → `ticket-select-<zone>`.
  3. Ticket Accept → `SetSelectedTicket` `0x338C0`, gated on `TicketSelectable` `0x5C590` → `festivalguide-vehicleselect`.
  4. Class Accept, gated on `TicketClassSelectable` `0x359D0` → class page.
  5. Accept → `SetPlayerVehicleClassChoice` `0x145B0` → `loadscreen-popup` → `SetGoToRace(true)` `0x1EBD38` (`[+0xAE]=1`) and `ApplyConfigFromTicket` `0x83848`.
  6. Hub transition `0x3BFA0` reads the flag through `0x1E61E8`. With game type ≠ 10 (festival = 1) it calls `0x3B710` and pushes the race state; with type 10 it pushes the garage load `0x8D9F0`.
  7. Race state group: `0x727B0`, loader `0x8EA00` (loading screen `0x329660`), `0x6CC98`, `0x706B8`, `0x13FB0`. Which member is the per-frame simulation update is not identified.
  - Not known statically: the default focus on each page, and whether first-visit popups (tutorial / invitation) appear.
- Controller/HLE readiness:
  - Host: XInput, plus a keyboard fallback on port 0 (focused window only) and the `PAD_SCRIPT` / `PAD_FILE` / `PAD_PRESS_ON_OPEN` injectors.
  - The four pad tests of the primary source pass offline (`test_pad.cmd` → `test/*.log`): capability info (128-byte clear), packet ABI (`len` 8 / 20 / 24, `button[1]`), trigger GetData, sensor mode.
  - `cellPadSetSensorMode` `0xBE5BE3BA` is registered in the primary build (`ppu_hle_nids.cpp:1741`). It returns UNSUPPORTED because no host motion sensor exists. The game calls it only when the SENSOR capability is reported, which it never is, so no sensor words are read.
  - Guest pad thread `0x72ADF0`: per `FINDINGS.md`, `cellPadGetInfo` (system_info 0, port 0 status CONNECTED here) gates `cellPadGetData` on ports 0–6. In T17 it polled port 0 about every 10 ms (15 reads during a 156 ms press).
  - GUI consumption, VERIFIED at runtime earlier (`docs/INTRO_SKIP_VALIDATION.md`): one injected CROSS on port 0 was taken by the intro page's own Accept; the movie closed 62 ms after the release, then the normal path to the garage followed. Every link from host packet through guest pad thread to GUI Accept has therefore worked once. Input on the garage pages has never been sent: no earlier run used `PAD_*`.
  - `PAD_SCRIPT` verified offline (`test/test_pad_script_getdata.c`, private): 2 scripted presses give 2 rising and 2 falling CROSS edges in `len > 0` packets, about 0.63 s held, nothing early, nothing on ports 1–6.
- Earliest blocker: none is confirmed. The earliest UNVERIFIED transition is step 1, the main menu accepting a press, simply because no input has been sent after the garage appeared. No static defect was found on the path to `SetGoToRace` or the race-state push.
- Other gaps found (not shown to block anything):
  - The only unresolved import reported at runtime is `cellFontInitLibraryFreeTypeWithRevision` (`0x7A0A83C4`, stub `0xCBF23C`). It gets a faked `CELL_OK` and its library out-parameter is left unwritten. HYPOTHESIS: this explains the missing menu text; it does not gate input.
  - The sensor/tilt issue from `FINDINGS.md` defect 2 does not apply to the primary build: the SENSOR capability is not reported.
- No fix was made: no emulator defect on the progression path was established.
- Remaining unknowns:
  - default focus and first-visit popups on each page;
  - the race-state member that runs per frame;
  - race-load duration (garage loads took 14–16 s);
  - whether `track` assets load with no missing files;
  - vehicle and physics initialisation (Havok).
- Prepared launch (NOT run): `powershell -NoProfile -ExecutionPolicy Bypass -File generated\analysis\t23\run_t23_race_path.ps1`. The `-DryRun` preflight passes (`dryrun.txt`).
  - It is the T17 wrapper on the primary exe (hash checked), without ftrace, plus:
    - `PAD_SCRIPT`: CROSS every 5 s from 40 to 135 s of pad time. Pad time starts at the first `cellPadGetData`, about 9.5 s after process start, so presses fall at roughly 50–145 s of process time. Input only.
    - `PS3_TRACE` from `t23_race_path.cfg`: 26 functions (pad thread and update, GarageInput, the festival commands, `SetGoToRace`, `ApplyConfigFromTicket`, the hub transition, the race-state push, the garage and race loaders, the race state group). `limit=6`, then power-of-two visits, `max=20000`, per-function totals every 10 s, on stderr. It parses cleanly against `307b08a`'s tracer (`test/pt_cfg_check.log`).
    - One RSXI frame captured 95 s after `depth_surface_created`: the last screen reached.
  - Kept: intro skip, renderer settings, VFS/HDD roots, `--timeout 150`, `--stop-on-fatal`, `--snapshot-cache`, tree kill at 210 s, cleanup by 225 s, no retry, one instance (preflight refuses a running image or launcher). `PAD_*` and `YDKJ_*` are also scrubbed from the inherited environment.
  - Reads:
    - `[cellPad] PAD_SCRIPT … press` lines (host packet);
    - `[PT] … fn=0072B530` (guest pad update);
    - command-handler entries in order (`76AF40`, `33848`, `338C0`, `145B0`, `1EBD38`, `83848`);
    - `3B710` / `8EA00` / `329660` (race request, loader, loading screen);
    - `fnstat` entry counts of the race group (a per-frame member means the simulation is running);
    - the captured frame.
  - Limits:
    - blind timing: if the main menu's default focus is not Festival, CROSS opens another page, and the trace shows which;
    - CROSS in a race is an action button, not throttle;
    - an armed `fn=` makes every hook cost about 17 ns, which may slow frames.
- Reproduce (from the motorstorm root):
  - `cmd /c generated\analysis\t23\test_pad.cmd`
  - `cmd /c generated\analysis\t23\test_pad_script.cmd`
  - `py -3 generated/analysis/dis.py 76AF40 76AFA0` and `… 3BFA0 3C0C0`
  - the NID check script in `unregistered_imports.txt` (name → NID via SHA-1 suffix `6759659904250490566427499489741A`; that list over-reports runtime built-ins, so the runtime `[hle] unresolved NID` lines are authoritative)
  - `grep "unresolved NID" generated/runs/20261025-102805-garage-capture-probe/stderr.log`

## T22: frame-gap diagnostic preparation (2026-10-25, build only, no launch, no code change)

Source: `ps3recomp-t17`, branch `agent/perf-integration-307b08a`, HEAD `3b38721` (clean). `motorstorm/v0.17-integration` not touched. Supporting files: `generated/analysis/t22/`.

- Build (VERIFIED): `build\motorstorm-perf-t18\MotorStormPacificRiftRecomp.exe`, SHA-256 `17E9CD9FB45269B4A077B13EE63F42C3C092FA703622C54B7BEA0508C7DDC287`, 397,565,952 B.
  - Configuration: Release, clang-cl 23.1.3, MSVC 14.51 libraries, CMake 4.3.1, Ninja; `RECOMP_DIR=generated\ppu-hooked-staging`, `PORT_HLE_NIDS_GENERATE=ON`. Details: `build_meta.txt`.
  - A build of this folder was already running (started 14:29, not by this session). My overlapping reconfigure failed (`ninja restat: Permission denied`, `build_exe_collided.log`). After that build finished, `build_exe.cmd` rebuilt 27 SPU objects, relinked, exit 0.
  - 39,106 warnings, all from the generated SPU C and its headers. Warnings for the instrumented runtime files were in the earlier build's log, which is not available.
- Switches (VERIFIED in source, and as strings in the exe):
  - `PS3_FTRACE=<start s>:<seconds>:<path>`:
    - window relative to the first hook (about boot), times in µs;
    - default `CAP` 4M spans (128 MB, allocated only when recording);
    - written when the first span after the window arrives (the runner's `taskkill /F` skips atexit).
  - `PS3_FTRACE_SYNC=1`: LABEL instants (kind 20), VBLANK instants (kind 21) and every FIFO drain, at about 300 drains/s from the `port/main.cpp` 4 ms loop plus 60 Hz beats. Records no RSX `ref` value.
  - `PS3_FTRACE_USLEEP_REG=31`: kind 22, `a` = lr, `b` = r31 at syscall 141 entry, once per merged usleep run. Runs merge when they share a thread and lr and are within `MERGE_US` (300 µs) of each other, so a later wait on a different gate inside one run is not recorded.
  - `PPU_SPINBT=0x10CE8F40`: one host backtrace the first time any thread makes 200,000 consecutive read32 calls to that address. RVAs only; the exe has no map or PDB.
    - Resolver (VERIFIED by self-test): `spinbt_resolve.py`, which walks the exe's `function_table` (53,278 entries).
    - The backtrace names the call chain, not the thread. The thread follows from the chain's entry function.
    - Out-of-line loads are already forced by `RSX_RTVIS` in T17, so this adds no cost.
  - The header logic passes `tests/test_ftrace_sync.c` (6 checks; `test/test_ftrace_sync.log`). Wiring inside the exe is verified only by reading the source.
- Static checks (VERIFIED):
  - At the `sc` in `LockFreeMutex::Lock` (`0x4B64B4`), r29 = r31 = the lock address. lr `0x94CCA8` = gate `+0xC`; lr `0x94CCBC` = guard `+8`.
  - `JobBatchInternal::Wait` (`0x4AACA0`) reaches the CV through the pointer at `batch+0x20`, and no register at the sleep holds the batch. A gate address therefore cannot be matched to a batch from the trace alone.
  - Correction to T21: `SystemTimeSleep` (`0x438960`) is a leaf with an inline `sc`, so r31 at the `0x536xxx` sleeps is well defined: the ResourceSystem pointer at `0x536A78`/`0x536CB8`, the saved `+0x91` byte at `0x536B30`. It carries no resource identity.
  - Developer signatures: `LoadInternal(AsyncPtr&, const char*)`, `(AsyncPtr&, const ResourceIdentifier&)`, `(AsyncPtr&, const char*, ResourceTypeId, bool)`. Mapping the retail copies to these is INFERRED from their RequestInternal calls.
  - RTTI: `ResourceSystem` has no vtable. File access goes through `evo::resourcesystem::fileaccess`, whose only subclass is `blockingfileaccess`. Its typeinfo `0x1041C4C` is referenced only twice, from that pair.
    - Retail vtable `0x1041C18` matches the developer build slot for slot (`rv_vtable.py`): D1, D0, Update, Completed, `ReadAsynchronous` (`0x97FCF8`), FileName, `SeekSynchronous`, Cleanup, OpenFile.
    - `ReadAsynchronous` calls `SeekSynchronous` and then a read on the calling thread.
  - `cellFsRead` is HLE (`libs/filesystem/cellFs.c:527`), not an lv2 syscall, so ftrace never shows file I/O.
- New offline results from T17 data (`gap_timeline.py` → `gap_timeline_t17.txt`, `t22_analyze.py` → `t22_analyze_on_t17.txt`):
  - Same structure in all three gaps (VERIFIED):
    - 0–60 ms: a normal frame's main-thread work (event receives, CV back-off);
    - then the `0x536A30` (menu `.ams`) loop: gap 1 from 74.5 to 327.6 ms, 16 sleeps 3–26 ms apart (one gap of 111 ms); gap 2 a single sleep at 76 ms; gap 3 from 85.5 ms;
    - then 231 ms (gap 1) / 237 ms (gap 2) with no main span at all (no usleep, no syscall ≥ 200 µs);
    - then the `0x536C68` and `0x536AB8` loops in the last 25–45 ms before the next flip.
  - Hence `Update` (the time between 1 µs sleeps) takes milliseconds per call, and the largest share of each gap is a silent stretch with no polling. INFERRED: since a `LoadInternal` copy calls RequestInternal before its first sleep, the silent stretch is RequestInternal or the caller's code before it.
  - Present spinner (question C, answered at 1 s resolution): HOTREAD lines on `0x10CE8F40` stay at 14.5–17.8 per frame, including the gap seconds (15.4, 15.3). Its drop in the gaps is fully explained by fewer frames.
  - Gap timing on this machine (`hb_gaps.py` → `hb_gaps.txt`):
    - `depth_surface_created` heartbeat time: 37.4, 38.5, 38.6 and 44.2 s across the four runs here (rtrb-watch, capture-probe, c38-trace, T17);
    - flip-rate dips at +7.3, +14.0, +16.3 and +21.7 s after it (capture-probe), and the T17 gaps at +16.4 to +19.5 s.
    - A fixed 45:30 window would miss a dip at +7.3 s whenever `depth_surface_created` comes before 37.7 s (c38-trace: 37.4 s).
- Prepared launch (NOT run): `powershell -NoProfile -ExecutionPolicy Bypass -File generated\analysis\t22\run_t22_diag.ps1`.
  - It is the T17 wrapper with only the exe and SHA-256, the run name `perf-t22-sync`, the output folder `generated\analysis\t22\runtime-<ts>` and these changed:
    - `PS3_FTRACE=40:40:{run_dir}\ftrace.txt`;
    - `PS3_FTRACE_SYNC=1`;
    - `PS3_FTRACE_USLEEP_REG=31`;
    - `PPU_SPINBT=0x10CE8F40`.
  - Window 40–80 s = `depth_surface_created` + 3 to +36 s across the observed range: every dip seen here, and it ends before the RSXI capture (depth + 85 s). The start time is absolute: dips at +7 to +22 s stay inside the window only while `depth_surface_created` falls between about 33 and 58 s.
  - Kept: intro skip, renderer settings, RSXI capture, VFS/HDD roots under this machine's root, `--timeout 150`, `--stop-on-fatal`, the wrapper's tree kill at 210 s and final cleanup by 225 s, environment scrub, no retry.
  - `-DryRun`: preflight OK, no launch (`dryrun.txt`).
  - Outputs: `generated\runs\<ts>-perf-t22-sync\{ftrace.txt, stderr.log, milestones.json, manifest.json, rsxi\}`, plus `host.csv` and `wrapper.log` in the runtime folder.
  - Analysis: `t22_analyze.py <run>`, `gap_timeline.py <run>\ftrace.txt`, `spinbt_resolve.py <exe> <run>\stderr.log`.
- What this launch can answer:
  - A, partly: the `LoadInternal` sleep sites per gap and their timing (repeating T17 on a new run). It cannot show calls that never sleep, or the silent stretch.
  - B: the r31 gate addresses of main's CV waits per gap and per normal frame, and whether they repeat. The owning batch or subsystem cannot be shown.
  - C: the Present spin's call chain, hence its thread, and its rate per frame.
  - D: whether LABEL and VBLANK instants and drains continue through the gaps.
- What it cannot answer: the resource identity; time in `Update` and RequestInternal; file I/O vs decompression vs allocation vs guest compute; cache state.
- Follow-up (PROPOSED, separate approval; existing tracer, configuration only, no code change):
  - `run_t22_diag.ps1 -WithResourceTrace` adds `PS3_TRACE` from `t22_resource_trace.cfg`:
    - `tid=1,3-9` (main and the FIOS threads);
    - `fn=536A30,536AB8,536C68,5346A8,5318F8,530F10,52D240`;
    - `hle=*`, `hle_min_us=100`;
    - `regs=r3-r6` plus 8 words at `[r5]`;
    - `limit=1000000`, `max=400000`;
    - `out={run_dir}\pt_trace.txt`.
  - It parses cleanly against the `ps3recomp-t17` tracer (`test/pt_cfg_check.log`: mask ENTER|RET|HLE, 7 fns, 8 tids, no config error). The hooked build defines `ppu_trace_hook_level = 1`.
  - Gives:
    - entry/exit time and duration of each `LoadInternal`, `Update` and `RequestInternal` call, with caller lr and thread;
    - the `Update` iteration count and its `r3` result (still pending or done);
    - sleep time = `LoadInternal` minus `Update` minus `RequestInternal`;
    - imports of 100 µs or more (`cellFs*` etc.) inside those frames;
    - the first 32 bytes at `r5`: the path for `0x536A30` (INFERRED argument), the identifier for `0x536C68`.
  - Separates slow loading (a long `RequestInternal`/`Update`, or long `cellFs` calls inside them) from excessive polling (many short `Update` calls with sleeps between).
  - Limits:
    - "cached or fresh" can be inferred only from the presence or absence of file imports;
    - longer paths are truncated;
    - asynchronous FIOS reads appear only on the FIOS threads;
    - with `fn=` armed, every ENTER/RET hook costs about 17 ns (`docs/TRACING.md`), so gap lengths may grow. The c38-trace run with six armed functions still reached `depth_surface_created` at 39.0 s; garage-frame overhead is unmeasured.
- Reproduce (from the motorstorm root):
  - `cmd /c generated\analysis\t22\build_exe.cmd`
  - `cmd /c generated\analysis\t22\test_ftrace_sync.cmd`
  - `py -3 generated/analysis/t22/spinbt_resolve.py build/motorstorm-perf-t18/MotorStormPacificRiftRecomp.exe --selftest`
  - `py -3 generated/analysis/t22/hb_gaps.py generated/runs/<run>…`
  - `py -3 generated/analysis/t22/gap_timeline.py generated/runs/20261025-132231-perf-t17-ftrace/ftrace.txt`
  - `py -3 generated/analysis/t22/t22_analyze.py generated/runs/20261025-132231-perf-t17-ftrace`
  - `py -3 generated/analysis/dis.py 4B63F0 4B64E0`, `… 4AACA0 4AACE4`, `… 536A30 536CF4`, `… 438960 438980`, `… 97FCF8 97FDA0`
  - `py -3 generated/analysis/t21/rtti.py resourcesystem`
  - `py -3 generated/analysis/t22/rv_vtable.py N3evo14resourcesystem18blockingfileaccessE`
  - Tracer config check: build and run with `generated\analysis\t22\test_pt_cfg.cmd "<cfg joined with ;>"`.

## T21: guest frame submission and synchronisation, offline (2026-10-25, no launch, no code change)

Inputs:
- The existing trace of run `generated/runs/20261025-132231-perf-t17-ftrace`: `ftrace.txt`, 30–120 s, 53,774 spans, 0 dropped; plus its `stderr.log`.
- Static analysis of the retail EBOOT, with names taken from the developer build `c38/rv/resourceviewer.elf` (symbols plus matching code).
- Scripts and outputs: `generated/analysis/t21/`.

- Lock objects and call graph (VERIFIED, static):
  - `0x4B63F0` = `evo::synchronisation::LockFreeMutex::Lock`:
    - `lwarx`/`stwcx.` 0→1 on `[r3]`;
    - while the word is held, 125×8 plain reads, then `SystemTimeSleep(250 µs)` (sys_timer_usleep with r3 = `0xFA`), then retry.
    - The lock address is kept in r31 during the sleep.
  - `0x4B63E0` = `LockFreeMutex::Unlock` (`lwsync`, store 0).
  - `0x94CBD8` / `0x94CC80` are not plain lock users. They are `ConditionVariableLightImpl::SetCondition(bool)` and `::Wait()`: RTTI `N3evo15synchronisation26ConditionVariableLightImplE`, retail vtable `0x103F9F8` slots 3 and 2, reached only through virtual calls.
  - Object layout: `+8` is a guard mutex and `+0xC` is the gate.
    - `SetCondition(false)` takes the gate and keeps it.
    - `SetCondition(true)` releases it.
    - `Wait` = Lock(`+0xC`), Lock(`+8`), Unlock both.
  - So the "held lock" at return address `0x94CCA8` has no owning thread. `+0xC = 1` means "condition not yet signalled", and the party that matters is whoever must call `SetCondition(true)`.
  - Known producer/consumer pair, `JobBatchInternal` (retail vtable `0x103F718`; developer build symbols):
    - `Start` → `cv->SetCondition(false)`;
    - `Wait` (retail `0x4AACA0`) → `batch+0x20` → `cv->Wait()`;
    - `JobManagerBase::HandleBatchCompletions` → `SignalCompletion` → `SetCondition(true)`.
  - That handler runs on the `JobBatchHandler` thread. Retail `0x4AF670` matches developer `JobBatchHandlerThreadProc` instruction for instruction: `loop { HandleBatchCompletions (0x4AC940); HandleBatchSubmissions (0x4AE908); SystemTimeSleep(200 µs) }`.
  - This is the source of the T17 usleep lr `0x4AF6D0`. Job-batch completion is therefore delivered by polling, with ≥200 µs latency plus host sleep granularity.
  - NOT established: which condition variable the main thread waits on at `0x94CCA8`. Other `ConditionVariable` users exist. That it is a job-batch wait is a HYPOTHESIS.
  - Spinner at lr `0x5226E8`:
    - Location: inside retail `0x50C818`, the first call of `DisplayATG::Present` (retail `0x5226A8` = `evo::renderer::DisplayATG` vtable slot 5; developer `DisplayATG::Present(Timer const&)`, whose first call is `RenderSystemATG::ResetRenderCommandLists`).
    - The loop: `while (rs+0x2560 != rs+0x44C)`, where `+0x44C` is the number of render-command jobs issued (incremented in `0x50D868`). That function also passes the address `rs+0x2560` into the job parameter block, so `+0x2560` is the completion count written back by the job (INFERRED).
    - `rs = 0x10CE69E0`. The spin word `0x10CE8F40` is the same in runs rtrb2, capture-probe and T17, and its values 2–11 are counts.
    - The spinner's HOTREAD rate halves exactly in the gap seconds (59.8–61.9 s: 108/138 per heartbeat vs 190–230 otherwise). So it is tied to frame presentation.
    - Which thread runs it is NOT established. The earlier fios-mediathread guess has no support.
- Frame submission (VERIFIED from code unless marked):
  1. Frame work is distributed as job batches: `Start` closes the batch condition, the SPU jobs run, `JobBatchHandler` polls them complete, and `Wait` returns.
  2. `DisplayATG::Present`:
     - `0x50C818` waits until every issued render-command job has completed, then resets the command lists;
     - `Timer::Step`;
     - `GcKernel::Present` (developer names: `SyncPreviousFrameInternal`, then Ice `KickAndDisplayRenderTarget` → flip).
  3. Frame throttle: `SyncPreviousFrameInternal` polls the RSX control `ref` against the previous frame's target, with `sys_timer_usleep(30)` (retail sites `0x513C90`–`0x513D48` in `0x512728`).
  4. Event queues: main's only event waits are `sys_event_queue_receive` (syscall 130) at lr `0xA48ED4` and `0xA49E3C`, 3.2% of main. The source `0xFFFFFFFF53505501` is an SPU event, not vblank (INFERRED from the log).
  5. Vblank and labels: no guest wait on either was found.
  - Over 70–118 s the T17 trace has no frame-throttle usleep on any thread, no RSX semaphore wait over 100 ms and no GPU wait. Main has 7 Ice-side usleeps at `0x72E5C0`. So the RSX is never the gate.
  - Per normal frame (82 ms), main spends 32.6% in the condition-variable back-off and 3.2% in event receive.
- The 350–630 ms gaps: 3 in the garage after 46 s, at 60.54 s (603 ms), 61.30 s (358 ms) and 63.07 s (636 ms). Per-thread analysis: `t21/gap_threads.py` → `gap_threads_t17.txt`.
  - VERIFIED from the trace:
    - main's condition-variable back-off falls to 3.6 / 8.7 / 4.6% of the gap (32.6% normally);
    - main makes no long syscall (event receive 0.3%);
    - the RSX drains 4.7–7.5% of the gap (35.9% normally);
    - `JobBatchHandler`, `workerThread`, Bink and the audio threads look exactly as in normal frames.
    - So main is executing, not waiting.
  - Present only in the gaps (0% of normal frames): main usleeps at lr `0x536A78` (gaps 1 and 3), `0x536B30` and `0x536CB8` (all three).
    - Each is the `SystemTimeSleep(1)` of a `ResourceSystem::LoadInternal` copy: `RequestInternal`, then `do { sleep(1) } while (ResourceSystem::Update())`. Retail `Update` = `0x5346A8`.
    - The developer build matches exactly, including the save/set/restore of the `+0x91` byte. The region references `ResourceInfoBlock`, `ResourceCollection`, `.evo` and `BIG `.
    - Callers: `0x536A30` is called only from `0x5C05E0`, which loads `gui/animations/menu_*.ams`. `0x536AB8` has 21 callers, including the post-effects setup `0x4BC390` (`ToneMapping`, `RadialBloom`, …). `0x536C68` has 5 callers.
  - Ranking:
    1. SUPPORTED: synchronous resource loading on the main thread. The main thread pumps `ResourceSystem::Update` itself until the load completes, so it issues no frame meanwhile. The sleeps are only 1–2% of the gap; the rest is main running guest code (`Update`/resource construction, or HLE file I/O, which the trace does not show). Which resources were loaded is not recorded. The GUI animation loader is the only caller of the site seen in gaps 1 and 3.
    2. Host slowness inside that load (CPU/IO): plausible; it would turn a short hitch into a 0.6 s one. Unmeasured (no main-thread CPU spans). Host CPU fell to 26% at about 60 s, a weak sign.
    3. Rejected for the gaps, each by the trace:
       - lock contention: back-off share falls;
       - waiting for a worker or SPU job: no wait, `JobBatchHandler` unchanged;
       - guest event synchronisation: event receive 0.3%;
       - RSX backpressure: RSX idle, no semaphore, throttle or GPU waits;
       - deliberate pacing: no timed wait in the gap.
  - Normal-frame pacing (not the gap question; HYPOTHESIS): roughly a third of main is spent waiting on a condition that is signalled by a 200 µs polling thread, and the Present spin waits for SPU render jobs. SPU job throughput and completion latency are the main candidates for the 82 ms frame.
- No emulator defect is shown. Nothing was changed.
- Proposed smallest diagnostic (NOT run; needs authorization). No code change is needed: these switches already exist at `ps3recomp-t17` `3b38721` (`agent/perf-integration-307b08a`), but not on `v0.17-integration`.
  - Build: `build\motorstorm-perf-t18` is configured for `ps3recomp-t17` but not built. Build it (about 25 min) and record its SHA-256.
  - Launch: one launch with the T17 wrapper `scratch\t17\run_t17_profile.ps1`, same env, plus:
    - `PS3_FTRACE=45:30:{run_dir}\ftrace.txt`: the window covers 45–75 s, including the 60–64 s gaps;
    - `PS3_FTRACE_SYNC=1`: label writes and vblank beats;
    - `PS3_FTRACE_USLEEP_REG=31`: r31 at each usleep. At `0x94CCA8` that is the condition-variable gate address, so it shows which condition main waits on and whether it changes across frames. Verified at `0x4B64B4`, where the `sc` is inline and r31 holds the lock address. At the `0x536xxx` sleeps r31 is the ResourceSystem pointer or a saved byte, not a resource (corrected in T22);
    - `PPU_SPINBT=0x10CE8F40`: a one-shot host backtrace that names the thread and callers of the Present spin.
  - Limits: 150 s, the existing stop conditions, no retries.
  - Read:
    - main's usleep lr/r31 per gap;
    - whether vblank/label instants continue through the gaps;
    - the SPINBT entry function.
  - If the gaps remain unexplained, a second step needs a code change (ask first): a ftrace span around `ResourceSystem::Update` (`0x5346A8`), plus the requested resource id (r4 at `0x536AB8`/`0x536C68`).
- Reproduce (from the motorstorm root):
  - `py -3 generated/analysis/t21/gap_threads.py generated/runs/20261025-132231-perf-t17-ftrace/ftrace.txt 300`
  - `py -3 generated/analysis/dis.py 4B63E0 4B64E0`, `… 94CBD8 94CCF0`, `… 4AF670 4AF6F8`, `… 50C818 50C8E8`, `… 536A30 536D40`
  - `py -3 generated/analysis/t21/rtti.py ConditionVariable` (and `JobBatch`, `JobManager`)
  - `py -3 generated/analysis/t21/opd_owner.py 5226A8`
  - `py -3 generated/analysis/t21/toc_strings.py 52D1C0 536EB0` (and `5C05E0 5C3100`, `4BC390 4C0300`)
  - developer build: `py -3 generated/analysis/t20_dis_rv.py 475EB0 475FC8` (CV), `… 2545C0 254650` (`JobBatchInternal::Wait`), `… 254CB0 254E30` (`SignalCompletion`), `… 25A678 25A700` (handler loop), `… 200828 2008E0` (`LoadInternal`), `… 2FE3F8 2FE540` (`SyncPreviousFrameInternal`); `py -3 generated/analysis/t21/rv_calls.py 1E2EE0 1E3318` (`DisplayATG::Present` calls)

## T20: c38 material binding and native defaults, offline (2026-10-25, no launch, no code change)

- New private inputs and helpers:
  - The PSARC member `/resourceviewer_atg.self` is a debug-signed (key revision `0x8000`, plaintext) developer build of the same engine. Its full ELF is embedded verbatim at SELF offset `0x980` and includes `.symtab` and DWARF. Extracted to `generated/analysis/c38/rv/` (`resourceviewer.elf`, SHA-256 `1bccfa2a…2ac22`; `symbols.txt`). Private game input, not for publication.
  - Scripts:
    - `generated/analysis/t20_sho_scan.py` scans every shader object in the PSARC; output in `c38/t20_sho_scan_c38.txt` and `_c35.txt`.
    - `t20_name_scan.py` searches for names and hashes.
    - `t20_rv_elf.py` and `t20_dis_rv.py` rebuild and disassemble the developer build.
    - `t20_rv_regscan.py` → `c38/t20_rv_regscan.txt`.
- Native defaults (VERIFIED, static):
  - Shader-object format: a VP object (`SHO\x08`) has a parameter table of 12-byte entries `{hash = ~crc32(name), class, size, count, u16 register, 0xFFFF}` and an embedded-constant block in the Ice `VertexProgram` layout: `u16 count @+0x16`, `u32 reg[count] @+0x18`, then `float4[count]` at the next 16-byte boundary. This is the layout read by Ice `CommandContext::SelectVertexProgram` (developer build `0x311290`, retail `0x734E90`) and by SPU site `0xD78`. The table entry for c38 is `0x8587F24B 02 01 0001 0026 FFFF`. The effect metadata (`EVOS`) declares `vsAmbientVisibilityModifier`, type float, semantic `"C38"`, flag 0.
  - No explicit default: across all 23,732 VP objects in the PSARC there are 32,966 embedded constants (21,976 programs have some), all at registers 451–467, none at c38 (`t20_sho_scan_ice.py`). No shipped program embeds a c38 constant, so loading a program does not write it.
  - Correction (round 2): the first scan (`t20_sho_scan.py`) read these registers at a 24-byte stride, which is the size of the FIFO command, not of the block. That is where its "61 below 256" came from. The c38 result is the same with the correct layout.
  - Persistence: RSX transform constants are global state and are not tied to a program. The host matches this: `rsx_state.vertex_constants` is one array, copied per draw. c38 therefore holds whatever constant RAM contains (inherited state). On the host that is 0. On hardware it is the RSX state after `cellGcmInit`, which is not known.
  - c38 is used game-wide: 10,956 VP parameter entries in 1,607 members (1,280 `split_vehicles`, 103 `packed_vehicles`, 125 `characters`, 51 `worlds` including race tracks, 47 `env`, `global.rpk`). Outside effect metadata, the name occurs only as heap residue in `/data/timetrial/DOE.DAT`. No data or config file names it.
- Material parameter binding (VERIFIED; names come from the developer build's symbols, layouts and behaviour from matching code in both builds):
  - Retail `0x4F9DF0` ≈ `Material::ApplyStaticParam`.
    - Parameter record of `0x44` bytes: `+4` holds a type nibble and a 12-bit register (`(w>>16)&0xFFF`); `+8` is a type byte (11 = sampler, skipped); the value is at `+0x30`. Uploads through `0x7351E0`.
    - Called from the static display-list builder (loop at `0x4FA2B0`).
  - Retail `0x4F9B68` ≈ `Material::SetParameterValuefc`. It writes `(n+3)>>2` registers via `0x735360`, or patches a display list via `0x732DD8`/`0x72D4A0` when the nibble is non-zero.
  - T18 saw neither setter receive register 38.
- Callback parameters (VERIFIED):
  - `Material::RegisterParamCallback(name, user, fn)` fills a 32-entry registry of `0x50`-byte entries `{ref, fn, user, name[64]}`.
  - `Material::Init` lower-cases each parameter's semantic. A semantic ending in `_callback` becomes a callback parameter, looked up by name; others are matched against 16 auto-parameter semantics.
  - The retail build registers four callbacks: `VEHICLE_WETNESS_CALLBACK` (`0x14C880`), `VEHICLE_DIRT_CALLBACK` (`0x14D148`), `TRAIL_BUFFER_CALLBACK` (`0x39DA48`), and `ao_callback` (`0x457098`, registered at `0x45B3F0`).
- The ambient-visibility producer (VERIFIED): retail `0x457098` is identical to the developer build's `SceneObjectList::AmbientVisibilityModifierCallback(ParamContext&)`. It sets `ParamContext+0x64` to `1.0f` when the current instance index is -1, and otherwise to the per-instance smoothed value `SceneObjectInstance+0x3C` (written by `AmbientVisibilityModifierSetSmoothed`).
  - The only asset semantic that reaches it is `AO_CALLBACK`, on the legacy parameter `ambientOcclusionModifier` in 20 members (BasicTextured/Paint effects).
  - All 1,607 members that declare `vsAmbientVisibilityModifier` give it semantic `C38`, so `ao_callback` is not bound to c38 (VERIFIED for every effect declaration).
  - The dirt and wetness callbacks are orphaned in the same way (no asset uses their semantics); their globals c36/c37 have literal writers instead (retail `0x14D438`, developer build `VehicleViewer::SetDirtAndWetnessConstants`).
- No literal writer in the developer build either (VERIFIED): `t20_rv_regscan` finds literal-register writes for c32, c33, c34, c36, c37, c40–c43, c55, c56, c58 and c59 (same set as retail, minus c35), and none for c38. The other sites take the register from parameter handles (`ApplyStaticParam`, `SetParameterValuefc`, `BindCallbackParams`, `DynamicParameterSet`, `SetMatrixArrayParameter`).
- Material fixed values (VERIFIED, all assets; `t20_mat_scan.py`, `t20_mat_bytes.py`):
  - Format: a material instance is resource type 7: `EVOSBIG 0007 <id48> 0002 0001 <u8> <u16 count>`, then records `[u8 type][u32 len][name][value]`. Types: `05`/`06`/`07`/`08` = float1–4, `0b` = sampler. Values are keyed by parameter name. Type 6 is the effect declaration: parameter name, semantic and flag only, with no value field.
  - Example record (`track_garage.rpk`, material `0x20221A1A3833`): `05 0000001F directionalLightAmbientModifier 00000000`, then `05 00000015 primaryNormalStrength 3F800000` (1.0).
  - Counts:
    - 95,614 materials in every `.rpk` member: 85,335 parsed with no error, 10,279 empty, 0 header anomalies; 639,859 value records.
    - No record is named `vsAmbientVisibilityModifier` or carries its hash `0x8587F24B`. The only ambient-related name is `directionalLightAmbientModifier` (61,245 records).
    - Byte-level check over the full bytes of every material (33.5 MB, including the part after the first sampler, where field parsing stops): 0 occurrences of the name (case-insensitive), of `AmbientVisibility`, or of the hash.
    - The name occurs only in 23,215 type-6 effect declarations.
  - So no asset supplies a fixed value for c38.
- SPU upload path (`renderablejob`; listing `generated/analysis/c38/renderablejob_dis.txt`):
  - VERIFIED: the only RSX constant-upload headers are 5 `ilhu 0x14 / iohl 0x1EFC` sites (LOAD + 1 vec4, at LS `0xD78`, `0x2100`, `0x31D0`, `0x34F0`, `0x9DF0`). No other `0x1EFC`/`0x1F00` immediate exists. Every site takes the register word from data, never from a literal.
  - VERIFIED, fixed-value loop (`0x9D8C`–`0x9F40`, upload `0x9DF0`):
    - count = byte `MaterialSPU+0x2C0`;
    - register = `u16 [+0x130+2i] & 0xFFFF`;
    - value = quad `[+0x10*i]`;
    - suppression: skipped when all four floats equal a shadow copy at `ctx+15680+reg*16`.
    The `MaterialSPU` is built on the PPU (`BuildMaterialSPU`, retail `0x4FAE04`) from the material's static parameters, the same `0x44`-byte records `ApplyStaticParam` uses.
  - VERIFIED, indirect loop (`0x7CC0`–`0x7F20`):
    - count = byte `+0x2C1`;
    - per entry it DMA-reads 16 bytes from the EA at `[+0x100+4i]` (a PPU-side value written by a callback or dynamic setter);
    - the register/type descriptor at `+0x150+8i` is dispatched through a 21-case jump table.
  - Per-site producers, reviewer round 2 (call graph from `t20_spu_cg.py`/`t20_spu_callers.py`; file offsets, LS = file + `0x4000`):
    - `0xD78`, VERIFIED: the SPU copy of Ice `SelectVertexProgram`. It writes program start and input/output masks, then one LOAD per embedded constant of the bound program, with register `u32 [+0x18+4i]` and value `float4` from the aligned block. The data is the SHO's own constant block, all at c451–c467 and never c38 (above).
    - `0x31D0` (helper `0x3150`) and `0x2100` (helper `0x2040`), VERIFIED on the SPU side: both are reached only from command opcode 10 of the command-list interpreter (`0xA970`, table `0xA9AC`, subtable `0xAC5C`). The register is word `+0xC` of the record.
      - Subtypes 5–8: 1 register inline at `+0x18`. Subtype 10: 4 registers inline. Both go through `0x3150`, which uses the shadow.
      - Subtype 12: `count = +0x10` registers DMA'd from the EA at `+0x18`, through `0x2040`, which neither checks nor updates the shadow.
      - Subtype 11 goes to `0x15E0` and is not a constant upload.
    - Opcode 10 is `RenderCommandMaterialParamSet` (VERIFIED in the developer build): the executor's case 10 calls `ParamSet::Set`; type 11 is `StateSet` (its constructor stores 11); the ptypes 5–12 and the `+0x10`/`+0x18` layout match the SPU record.
      - Its only constructor reads it from an asset stream: `[u8 10][u32 +0xC][u32 ptype][u64 material id][values]` (`RenderCommandList::Read`, case 10).
      - On the PPU, `+0xC` is a 1-based dynamic-parameter handle, used as `DynamicParameterSet(handle)` → material `+0x90` table. That table is filled only by `Material::DynamicParameterRegister(const char*)`.
      - Its 87 call sites in the developer build pass 44 literal names (`t20_rv_dynreg.py`: `clearCol`, `ambOccVol`, `prim2dTexture`, …), none c38.
      - The retail EBOOT contains neither `vsAmbientVisibilityModifier`, nor its hash (either byte order), nor a `C38`/`c%d` string.
      - INFERRED: where the PPU turns the handle into the register the SPU uses was not located.
      - INCONCLUSIVE: an asset scan for serialized ParamSet records (`t20_paramset_scan.py`) found no recognisable records, only integer noise, so the assets show neither c38 nor any other register.
      - Net: c38 could reach this path only through a name the binaries do not contain, or through a raw register number in an asset format not identified (PARTIAL).
    - `0x34F0` (helper `0x3400`), VERIFIED: its callers are only the indirect-material loop's cases (`0x7CC0`–`0x83B0`, which branch back to `0x7EDC`) and two helpers called only from there (`0x3710`, `0x38B0`, the matrix/auto-parameter cases). The register comes from the `MaterialSPU +0x150` descriptor, so it is the same set as the indirect loop and does not include c38.
  - Shadow cache (VERIFIED static, `renderablejob_dis.txt`):
    - Location: `ctx` is the fixed LS address `0x17800` (`ila` at `0xDEB0`/`0xE170`). The shadow is `ctx+0x3D40`, 16 bytes per register (LS `0x1B540` onward).
    - Only 4 instructions reference it:
      - three compare-and-update sites: the static loop `0x9DF0`, `0x3150`, `0x3400`. Each skips the upload when all 4 floats match and otherwise stores the new value;
      - one invalidation (`0xE88`–`0xED8`): after each VP bind it fills the entries of a u16 register list with sentinel `0xC7C34FF3` (about −99999.9). This is the only use of that constant.
    - Not reset: the job-start init (`0x50F0`, called with `ctx`) writes the neighbouring fields (`ctx+12848`…`15680`, `24704`…`24954`) but nothing in `0x3D40`–`0x5A80`. No DMA targets it, and it is never read from RSX (an SPU cannot). It therefore persists in LS between jobs.
    - Start-up contents: on hardware, whatever that LS held before (unknown). On the host, zero: the job manager's LS context is allocated zeroed per (workload, SPU) and kept (`ps3recomp-int/runtime/spu/spurs_policy.c` around line 162).
    - PARTIAL: whether the original wwsjob manager maps a buffer over LS `0x17800`–`0x1DA00` is not traced.
    - Can it suppress an upload before RSX has the value? Yes, structurally: a stale or zero entry equal to the requested value drops that upload. For c38 it cannot matter, because no c38 upload request exists to drop.
    - HYPOTHESIS, not shown to be a defect: the host and hardware could differ for other registers whose first requested value equals the hardware's leftover LS contents; on the host that means all-zero values. Not a c38 explanation.
- Host: no evidence of skipping, filtering or misdecoding. The host never receives a register-38 binding, and every stage it does receive is carried faithfully (T18, 33-check harness). No synthetic test or correction is justified, and none was made.
- Assessment:
  - VERIFIED: no c38 writer has been identified in the retail PPU code (literal sites, T19), in program-embedded constants, in material values, or in the developer build. `ao_callback`, the only ambient-visibility producer, is bound only to `AO_CALLBACK` parameters, never to c38.
  - Also VERIFIED: no c38 write was observed at runtime (T18, all FIFO paths, about 40 s up to the garage).
  - Not proven: that nothing ever writes c38. Still open: the PPU handle→register step for opcode-10 commands, asset-side ParamSet records (format not confirmed in retail data), and code paths T18 did not reach.
  - Against "zero is the intended look" (INFERRED): the callback's neutral default is `1.0f`, and per-object smoothed values are computed. The `C38` binding looks detached from its producer, which looks like a shipped omission, not a deliberate zero.
  - HYPOTHESIS: hardware also renders with c38 at its post-init RSX value.
- Still unknown:
  - RSX transform-constant contents after `cellGcmInit` on real hardware. RPCS3 zero-initialises, so only a hardware capture can settle this.
  - The handle→register step for opcode-10 ParamSet commands, and their retail asset encoding.
  - The LS state at hardware start-up under the shadow cache (not reset by the job).
- Next step, if wanted: a hardware reference capture of VP `0x9158278F` constants in the garage. Or offline, locate the retail code that builds opcode-10 SPU records. Neither is prepared. No emulator mismatch was found, so the no-fix decision stands.
- Reproduce (from the motorstorm root, Python via `py -3`; reads `original/game/PS3_GAME/USRDIR/MS2.PSARC`, writes only under `generated/analysis/`):
  - `py -3 generated/analysis/t20_sho_scan.py 38 > generated/analysis/c38/t20_sho_scan_c38.txt`
  - `py -3 generated/analysis/t20_name_scan.py vsAmbientVisibilityModifier`
  - `py -3 generated/analysis/t20_mat_scan.py > generated/analysis/c38/t20_mat_scan.txt`
  - `py -3 generated/analysis/t20_mat_bytes.py > generated/analysis/c38/t20_mat_bytes.txt`
  - `py -3 generated/analysis/t20_extract_member.py /resourceviewer_atg.self generated/analysis/c38/rv/resourceviewer_atg.self` (SHA-256 `08740fd0…7f16`; from Git Bash set `MSYS_NO_PATHCONV=1`), then `py -3 generated/analysis/t20_rv_elf.py` (the ELF embedded at `0x980`, SHA-256 `1bccfa2a…2ac22`). then `py -3 generated/analysis/t20_rv_syms.py` (writes `symbols.txt`).
  - `py -3 generated/analysis/t20_rv_regscan.py > generated/analysis/c38/t20_rv_regscan.txt`
  - `py -3 generated/analysis/t20_dis_rv.py C6B10 C6BE8` (callback)
  - `py -3 generated/analysis/dis.py 457098 4570DC` (retail callback)
  - `py -3 generated/analysis/dis.py 45B3D0 45B400` (retail registration)
  - SPU loops: `renderablejob_dis.txt` lines 10070–10200 (static) and 7980–8135 (indirect).
  - Round 2:
    - `py -3 generated/analysis/t20_sho_scan_ice.py 38 > generated/analysis/c38/t20_sho_scan_ice_c38.txt`
    - `py -3 generated/analysis/t20_dis_rv.py 311290 3113B0` (Ice SelectVertexProgram)
    - `t20_dis_rv.py 178B48 178C40` (executor table)
    - `t20_dis_rv.py 1DE3B0 1DE4E0` (ParamSet::Set)
    - `t20_dis_rv.py 1E0830 1E0A00` (ParamSet stream ctor)
    - `t20_dis_rv.py 17A4A0 17A670` (RenderCommandList::Read)
    - `py -3 generated/analysis/t20_rv_dynreg.py` (DynamicParameterRegister names)
    - `py -3 generated/analysis/t20_vpspu_scan.py generated/decrypted/EBOOT.elf` (→ `0x734E90`)
    - `py -3 generated/analysis/t20_spu_cg.py E568` and `t20_spu_callers.py 2040 3150 3400 3710 38B0` (SPU call graph)
    - `py -3 generated/analysis/t20_paramset_scan.py > generated/analysis/c38/t20_paramset_scan.txt`
    - SPU listing `renderablejob_dis.txt`: opcode-10 table at file `0xAC30`–`0xADB4`; shadow refs (`il 15680`) at listing lines 937, 3183, 3447 and 10163; job-start init `0x50F0`.
    - Developer SPU image `c38/rv/renderablejob_dev.bin`: same 5 sites, same opcode-10 subtable (`0xB94C`).

## T19: native source of c38, offline (2026-10-25, no launch, no code change)

- Inputs: the T18 run `20261025-114539-garage-c38-trace` (above) and the original EBOOT. Private helpers: `generated/analysis/t19_xref.py` (TOC/data xrefs) and `t19_helper_sites.py` → `generated/analysis/c38/t19_helper_sites.txt` (every call to the 4 constant helpers and `0x734E10`); SPU listing `generated/analysis/c38/renderablejob_dis.txt`.
- VERIFIED, how engine globals are bound: the effect headers pin the `vs*` globals to fixed registers (semantic `Cnn`). None of their names (`vsAmbientVisibilityModifier`, `vsCoarseExposure`, `vsShadowSplitScale`, …) or their hashes (`~crc32`, crc32, upper/lower case; as data or as `lis`/`ori` immediates) occur in the EBOOT. The engine therefore supplies them by register number only.
- VERIFIED, globals c32–c43 and c56 have literal-register writers:

  | Register | Content | Writer |
  |---|---|---|
  | c32 | eye position | `RenderSystemATG::SetVertexConstants` via sites `0x50EE64…` |
  | c33 | exposure | `0x4C3748`/`0x4C3AE4` |
  | c34, c40–c43, c56 | light direction, environment-lighting terms, fog range | GroundRush per-frame lighting `0x444760` (sites `0x448B80`–`0x448C84`) |
  | c35 | fog-light lerp: `.x` from a virtual provider at `this+0x74`, `.yzw` from TOC `0x3FD8` | `ms2GameView` `0x337300` |
  | c36, c37 | dirtiness, wetness (from `this+0x10/0x14 × this+0xE8`) | `0x14D438` (vtable entry `0x1080398`) |

- VERIFIED: c35–c37 are 0 in the garage dump. c35 is uploaded as 0 by the guest (T18, 3 calls). Whether c36/c37 were written as 0 or never written was not traced.
- VERIFIED, no c38 writer exists:
  - No literal 38 reaches any helper (40 call sites listed).
  - The record-driven sites (effect parameter setters `0x4F9B68`/`0x4F9DF0` in `0x4F9AC8`, `0x4FBD10`, `0x4FF588`) take the register from the parameter handle; T18 shows none received register 38 in the run.
  - SPU `renderablejob` (5 `0x00141EFC` header sites at LS `0xD78`, `0x2100`, `0x31D0`, `0x34F0`, `0x9DF0`) takes registers from DMA'd lists, not literals. The T18 FIFO watch (all paths) saw no c38 upload, and neither did the Oct 24 `085300` run.
- VERIFIED, c45–c55 and c57 are set without literal writers: c46.w = `0x696E6700` ("ing"), and c57.yzw hold pointer-like words. These look like padding copied from memory structs by the table-driven parameter setters (float2/float3 parameter + 16-byte copy). INFERRED: c38 would use this same path if anything supplied a value.
- VERIFIED, no other ambient source maps to c38:
  - GroundRush (`0x444760`) binds named ground-shader parameters by string (TOC `0x76FC`–`0x7758`: `averageAmbientLightColour`, `averageUpAmbientLightColour`, `envDirLightColour`, `directionalLightAmbientModifier`, `ambientOcclusionGlobalScaler`, `skyBrightnessModifier`, …). None maps to c38.
  - `AmbientVisibilityOverlay` (RTTI `0xE19090`, vtable `0x103BA50`) is a debug overlay whose update method is an empty `blr` in this build.
- c38's meaning: `vsAmbientVisibilityModifier`, a global scale on the per-vertex ambient visibility (`o[1].z = v3.w * c38.x` in VP `0x9158278F`). VERIFIED from the shader and parameter table. Its intended value is unknown.
- Earliest missing point: the guest. No guest code or SPU job ever issues an upload for register 38. FIFO, handler, host array, constant buffer and shader mapping all carry the zero faithfully (T18, 33-check harness). There is no host-side defect, so no corrective patch and no new test.
- Per scene/material/object/draw: not applicable, since nothing updates it. Deliberate zero-initialisation followed by replacement: no evidence of either; nothing initialises it, and RSX constant memory simply starts at 0.
- SPU dependency: possible only through the `renderablejob` lists. Runtime shows no c38 entry reaching the FIFO; an SPU job failing silently before emitting is not excluded.
- UNRESOLVED: whether hardware also leaves c38 = 0 (a zero there would mean the garage look is native). Deciding this needs either a reference capture (RPCS3 or hardware) of VP `0x9158278F` constants in the garage, or a bounded run that logs the `renderablejob` parameter lists and the effect binder's skipped parameters for register 38. Neither has been prepared or run.

## T18 run: c38 is never uploaded (2026-10-25, one authorized launch)

- Run `generated/runs/20261025-114539-garage-c38-trace`. Exe SHA-256 `D833E9BC…E438`, verified in full by the wrapper. The wrapper took 44 s and exited 2. Termination: stop line `[fc-watchdog] frame clock no progress for 3016 ms in stage=beat` at about 40 s, no 210 s kill, cleanup clean. RSXI captured 1 of the 4 planned frames (`f001819`). The stall's cause is not established; tracer load is possible.
- Tracer validity: PASSED. All four tracers armed (`[PT] ev=config … fn=6 when=7`, no config error; `[tcw] armed`; `[vpct] armed`; RSXI armed). The c35 control fired: `0x735140` was called 3 times with r4=0x23 from `ms2GameView`, lr `0x337910`. Garage draws reading c38 were reached: frame 1819, 178 draws of `vs=0x9158278F`/`0x0E74E41D`, reads=direct.
- VERIFIED, c35: the guest itself uploads zero (f1–f4 = 0 on all 3 calls).
- c38, by stage:
  - Guest helpers (VERIFIED for the whole run): no call targeted c38. `when_pass` was 0 for `0x735140` (r4=38), `0x7351E0`, and Material setters `0x4F9B68`/`0x4F9DF0` (118 and 4351 calls); `0x735270` was never called.
  - `0x735360` (PARTIAL): no logged call covered c38 (20002 logged, all from `SetVertexConstants` sites `0x50EE64`–`0x50EEDC`, covering c0–c15, c20–c23 and c32). The event limit was reached at about 21 s; the later calls are only counted, and that counter includes blocks that end below c38.
  - FIFO (VERIFIED, all paths including SPU and `0x734E10`): no `0x1EFC` block covered c38 (`[tcw]` 4 samples, `covering=0`, no hit).
  - Host handler: no write (`writes=0`).
  - D3D12 constant buffer: all 572 traced draws show host = buffer = `00000000×4`, `match=yes`, `last_write=never`. Dumps 1–4 (frame 1819, draws 205–208, `vs=0x9158278F`): 235 non-zero registers, c35–c39 zero, c40 = (0.02, 0.01, 0, 0).
- Conclusion: c38 is zero because nothing ever writes it. The host does not lose a value. It is not yet known whether the original game would upload it.
- Next step (offline): find where the garage VP parameter table is resolved (`vsAmbientVisibilityModifier`, register 0x26), and what the game does when a parameter has no binding.

## T18: vertex constant c38 root-cause instrumentation (offline, 2026-10-25, no launch)

**Phase 1, static path of c38 (this tree, ps3recomp-int `8f7ac89` on `307b08a`):**
1. Guest PPU (VERIFIED, from the Oct 24 offline work and re-read here): c38 is `vsAmbientVisibilityModifier`, declared in the garage VP parameter tables (`SHO`, register 0x26) with no material value. Apart from `0x734E10` (libgcm-style SetVertexProgram uploading a program's embedded constants, used by post-process at `0x5C5914`; not traced), every PPU constant upload ends in one of four helpers, r3 = CellGcmContext, r4 = destination register: `0x735140` (1 vec4 from f1–f4, header `0x00141EFC`), `0x7351E0` (1 vec4 from [r5]), `0x735270` (4 vec4 from [r5], `0x00441EFC`), `0x735360` (r5 vec4 from [r6], `0x00841EFC` blocks). `RenderSystemATG::SetVertexConstants` (`0x50BAA0`) reaches `0x735360` through stub `0x757098`. The Material setters `0x4F9B68`/`0x4F9DF0` take the register from the record halfword at +4 (low 12 bits). No literal 38 is passed to any helper; the SPU `renderablejob` builds `0x00141EFC` headers with registers from DMA'd lists.
2. RSX commands: `SET_TRANSFORM_CONSTANT_LOAD` (0x1EFC) sets the base; the 32-dword window 0x1F00–0x1F7C writes slot = LOAD + reg/4, lane = reg%4 (`rsx_commands.c`); LOAD does not auto-advance; 0x1FD8/0x1FF0/0x1FF8 are separate registers.
3. FIFO decoding: the `cellGcmSys.c` walker sends subchannel 0 (and 1 unless `GCM_SUBCH1_2D`) words to `rsx_process_method`, incrementing (`method + i*4`) or non-incrementing; JUMP/CALL/RET are followed. `rsx_commands.c:966` is the only other caller.
4. Host storage: `rsx_state.vertex_constants[512][4]`, written only by that handler.
5. D3D12 buffer: `vp_record_cb` copies all 512 registers per draw at record time (`memcpy(dst, st->vertex_constants, 8192)`), then may rewrite c0–c15 (fallback projection, off with `VP_NOFIXPROJ=1`); register r is at byte r*16 of cbuffer b0.
6. Shader mapping: the VP decompiler emits `vp_c[const_src & 511]` (const field `(d1>>12)&0x3FF`), `float4 vp_c[512]` at `register(b0)`, so c38 → `vp_c[38]` → bytes 0x260–0x26F. `vp_9158278F` line 47: `o[1].z = v3.w * vp_c[38].x`.
- Already measured (Oct 24 runs, earlier exes on this branch): no FIFO header addressed c38 for a whole run (`RSX_TCONST_FIFO_WATCH`, run `085300`), and the handler never wrote any lane of c38 (`RSX_VPC_WATCH_ANY`, run `071154`). The host stages are therefore VERIFIED as not losing a c38 upload that reaches the FIFO; the open question is whether any guest path tries to upload it.
- Not established: whether a PPU helper or Material setter is ever called for register 38 (no runtime evidence yet), and the SPU `renderablejob` lists (only visible as FIFO words).

**Phase 2, instrumentation (`8f7ac89`, branch `agent/t18-c38-trace`, local, not pushed or merged):**
- `RSX_VPC_TRACE=<slot>` (`libs/video/rsx_vpc_trace.h`), off by default, read-only:
  - `[vpct] write`: each handler write of the slot, global write sequence number, BEGIN/END epoch, LOAD, method, lane, raw bits.
  - `[vpct] draw`: each draw whose VP reads the slot: frame, draw, VS hash, FP, read mode (direct/relative), host value and buffer value (raw bits) at `cb_off=0x260`, `match=yes/NO`, last write (`seq`) or `never`.
  - `[vpct] frame`: per-frame draws / non-zero buffer values; `[vpct] dump`: every non-zero register of the first N draws (`RSX_VPC_TRACE_DUMPS`, `RSX_VPC_TRACE_VS` filter). Line budget `RSX_VPC_TRACE_MAX` (default 256, max 8192).
- PPU tracer (`runtime/ppu/ppu_trace.cpp`): `when=FN:SPEC[>>S][&M]=LO[..HI]` limits a function's events to matching calls (e.g. helper r4 = 38, or the record field `[r4+4]>>16&0xFFF=38`); `fnstat` adds `when_pass`; `regs=` accepts `fN` (float argument as single-precision bits). Works with the current hooked lift (`generated/ppu-hooked-staging`), no relift.
- Gap: draws through the non-cached VP path (`vs_idx < 0`) are not traced; vertex attribute formats are still not recorded.

**Phase 3, tests:**
- `libs/video/tests/test_rsx_vpc_trace.c` (33 checks, clang 23 against `rsx_commands.c`): c38 upload and persistence across other uploads, a draw and a program change; 32-dword block from c32; x-only write; LOAD+reg/4 (LOAD 37 reg 4, LOAD 31 reg 31, LOAD 36 reg 9); window-end registers and LOAD 550 not touching c38; NaN payload/denormal/−0 bit-exact; buffer offset 38*16; host/buffer mismatch flagged; frame summaries, budget, dumps, VS filter, read-mode detection (`vp_c[380]`/`vp_c[3]` not matched).
- `test_ppu_trace.cpp` `test_when`: register, range, OR'ed conditions, pointer field with shift/mask, quiet exits, sampling over passes, `fN`, 4 malformed conditions refused.
- Windows suite (`generated/introskip/rtrb_suite.bat`, rerun with skip lines recorded: `scratch/t18/suite_skip_t18.log`): 110/110 scripts exit 0, but 72 of them skip their compiled harness (no POSIX/`cc` toolchain), among them `test_vpc_trace.py` (only its 6 source checks run there), `test_vpc_watch.py` and most RSX/D3D12 harnesses. `test_ppu_trace.py` prints no skip. `test_rt_readback` 275 checks.
- Direct run, separately: `test_vpc_trace.py` with `CC=` the bundled clang 23.1.3 under vcvars (`scratch/t18/vpc_clang_t18.log`): 0 failures, the 33-check C harness plus the armed-line and write-line checks. Public audit of the staged files: no findings (25 inherited findings elsewhere).

**Phase 4, prepared diagnostic (not run; needs authorization):**
- Exe `build/motorstorm-int-nm-8f7ac89/MotorStormPacificRiftRecomp.exe`, SHA-256 `D833E9BC73072A61919F884DDEE6B78F351AC14968891C80075A5779E369E438`; build log `generated/introskip/build_int_nm_8f7ac89.log` (incremental from a copy of the `307b08a` tree, exit 0, 43 steps, linked 2026-10-25 11:39, contains the `[vpct]` and `when_pass` strings). A first attempt rewrote only `CMakeCache.txt`; `build.ninja` and 8 other files still named the old tree, so CMake regenerated `build/motorstorm-int-nm-307b08a` (build files and `generated_spu` rewritten, a leftover `generated_spu.stage-s9a_4vmo`). It was stopped; that tree's exe is unchanged (SHA-256 `96D9DEE1…`, T16), but the tree is PARTIALLY MODIFIED (build files regenerated against the current sources, `generated_spu` partly rewritten) and must not be used for a trusted rebuild of `307b08a` until it is repaired or recreated. Left as is. Copying a tree needs the folder name replaced in every text file except `.log`.
- Command: `powershell -NoProfile -ExecutionPolicy Bypass -File generated\introskip\run_garage_c38_trace.ps1`. Guest trace config `generated/introskip/c38_trace.cfg` (parsed offline by the real tracer: 6 functions, 7 conditions, no errors).
- Limits: fast_startup `--timeout 150` (hard kill 165 s), wrapper tree kill at 210 s, gives up at 225 s; stop on RSXI capture complete or frame-clock watchdog; `--stop-on-fatal`. The wrapper also keeps the process handle so the exit code is readable (the T16 wrapper bug).
- Expected output (stderr.log): `[vpct] armed: c[38] …`, `[tcw] armed` + 4 `sample` lines, `[PT] ev=config … fn=6 when=7`; then either `[PT] ev=enter` lines for a helper/setter with r4 = 38 (guest tries c38: value in f1–f4 or `m[r5+…]`) or none, with `ev=fnstat … when_pass=0` for the c38 conditions and a non-zero count for the c35 control; `[tcw] hit` / `[vpct] write` lines only if c38 reaches the FIFO; `[vpct] draw … last_write=never` and `[vpct] dump` for `vs=0x9158278F`/`0x0E74E41D`; RSXI frames with all 512 VP constants.
- Interpretation: a match (`[PT] ev=enter` for a c38 condition, or `[vpct] write`) shows the guest tries to upload c38 and gives the value. `when_pass=0` for the c38 conditions only means no matching upload was observed in the executed part of this run. It counts as a negative result only if all three hold: tracing was active (`[PT] ev=config … when=7` with no `config-error`, `[vpct] armed`, `[tcw] armed`); the c35 control reached `when_pass>0` (the helper hooks fire); and garage draws reading c38 were reached (`[vpct] draw … vs=0x9158278F` or `0x0E74E41D` lines). If any of these is missing, the result is INCONCLUSIVE.
- Risk: with the tracer armed every lifted function entry costs about 11 ns (test measurement), so the garage may be reached later than in T16 (~50 s); the guest-side result is still valid for the part of the run that executes.

## T13: exposure readback selection logging (offline, 2026-10-25, no launch)

- Commit `86c9e07` (ps3recomp-int, on `2e301bd`). Adds stable reason codes for both the selection decision (`why`) and the pre-table/queue skips (`no_rt`, `ea_unmapped`, `fmt_mismatch`, `table_full`, `res_mismatch`, `no_slot`, `no_mem`, `staging`), plus per-surface last write and last sample frames.
- `RSX_RT_READBACK_WATCH=<hex>[,...]` (up to 4 offsets, bounded by `RSX_RT_READBACK_WATCH_MAX`, default 256) prints one `[rtrb] watch` line each time a watched surface's stage changes. The stages are untracked, not written, a why code, a pre-table skip or a queue skip, so "never considered" is distinct from "rejected". Each line gives ea, res, gen, fmt, dimensions, pitch, bytes, write/sample frame, orphan streak, applied gen and pending. Result lines report the non-zero word count. The watch and target lines have separate log budgets, and every 600 batches a `[rtrb] decisions` line prints the counts. All of this is off by default.
- VERIFIED (run `20261024-223035-garage-rtrb2`): all 252 guest exposure reads returned 0. The decision for `0x06A1E400` is missing from the log because the shared 160-line budget ran out by flip ~315. Copies of `0x02903600` were queued, submitted and applied. The RT pool evicted nothing.
- UNDETERMINED: whether the exposure surface fails at selection, at the queue, or in the GPU data. The watch log is there to answer this.
- Tests: the readback test now has 233 checks (MSVC, and WSL gcc/clang with ASan/UBSan), with 0 failures. Windows suite 109/109. Public tree audit passed.
- Stalls in rtrb2 (frames 1679–1937, 13 heartbeat gaps of 2.7–6.1 s, 7 frame-clock watchdog reports) are kept for the performance investigation. Nothing links them to readback.
- Proposed run: `generated/introskip/rtrb3_diag_cmd.txt` (not launched).

## T11: readback format decoder fix (offline, 2026-10-24)

- Commit `1fd750a` (ps3recomp-int). `ps3_rtrb_fmt_linear` now decodes type from bits [11:8] and antialias from bits [15:12]. It gates both the readback and the pitched initial upload. Exe `e55d70f9…` is in `build/motorstorm-int-rtrb-e55d70f9/`.
- VERIFIED: the test now has 199 checks (MSVC, and WSL gcc/clang with ASan/UBSan). Real register values: `0x14B` and `0x148` are accepted, `0x3148` is excluded. The Windows suite passes 109/109.
- Slowdown in run `204223`, HYPOTHESIS that it comes from the host: the same command and env as `194334` apart from the flag. The flag queued 0 copies and printed 25 log lines. The three busiest threads used about 2x the CPU per second, and kernel time rose from about 0.7 to 1.5 s/s, while the run produced about 3x fewer frames. The sampler's per-thread readings jumped around, with single-thread values above 1 core per second. Every stall stack is in vertex fetch.
- Proposed repeat: `generated/introskip/rtrb2_diag_cmd.txt` (not launched).

## T10 run: garage-rtrb (2026-10-24)

Run `generated/runs/20261024-204223-garage-rtrb`, exe `db479495…`, commit `496485b`, one launch. Stopped at the 150 s wall-clock timeout; no GPU watchdog, no fatal.

- VERIFIED: `[rtrb] on` printed. All 25 colour targets, including the exposure surface `0x06A1E400` (16x16 FP16, fmt `0x14B`), were rejected with reason `format`. Zero copies were queued, submitted or applied.
- VERIFIED (cause): `rt_readback.h` decodes `SET_SURFACE_FORMAT` with the antialias and type fields swapped. The real layout is type in [11:8] (1 = pitch, 2 = swizzle) and antialias in [15:12]; `rt_vis_trace.h` already uses this. `0x14B` is a pitched, non-AA surface; `0x3148` (the 1280x720 display buffers) is AA mode 3. The synthetic tests share the same wrong constant (`0x100B`), so they passed.
- VERIFIED: all 252 logged guest exposure reads returned 0 (227 COMPLETE, 15 RECORDED, 10 BEFORE_WRITE; 237 one flip after the write). The garage stays black.
- PARTIAL: the garage phase ran at about 3.3 fps, against 9 fps in run `194334-garage-rtvis`, with 8 frame-clock watchdog reports, all in vertex fetch (`rsx_fetch_attrib`, `vp_record_*`), none in rtrb code. Cause unresolved.
- Next: fix the field order in `ps3_rtrb_conv_of` and in the tests, then repeat the run.

## T10: render-target readback hardening (offline, 2026-10-24)

- **Source and exe:** ps3recomp-int `496485b` (on top of `5b1988f`). Exe `db479495bef8f49f9c76207a6bc64737803940351748a5b50999b9a36a14a4ad` in `build/motorstorm-int-rtrb-db479495`. Not launched.
- **State per copy:**

  ```
  recorded -> queued (staging copy appended to the list) -> submitted (dedicated fence signalled)
           -> completed (fence reached) -> applied | merged | dropped
  ```

  The drop reasons are `replaced`, `stale`, `unmapped` and `aborted`. Only `applied` or `merged` is guest-visible.
- **CPU-write race (resolved; VERIFIED in tests):** guest words are merged one aligned 32-bit compare-and-swap at a time, from the surface's shadow (the guest bytes as last known) to the GPU value. A CPU write before or during the application keeps its word (`merged`, counted in `cpu_words`). Remaining limit: a CPU store of the value the word already held can't be told apart from no store.
- **Partially applied surface (constrained):** a concurrent reader sees every 32-bit word entirely old or entirely new, never a torn word. A consistent whole-surface snapshot is not guaranteed; that would need read interception or blocking the guest. On hardware, ROP writes also land progressively.
- **Selection (unchanged heuristic):** a surface is copied if it is unsampled for 2 generations and at most 64 KiB. No stronger generic signal was found:
  - The exposure surface is in local memory, so the memory location doesn't distinguish it.
  - The lock is the game's own code (no HLE call).
  - The game uses no label or semaphore before the read.
  - Detecting CPU access would need read or page interception.

  Each decision is now logged once per change with its reason (`selected`, `young`, `sampled`, `too_big`, `format`, `pitch`, `align`, `no_resource`).
- **Format and pitch:**
  - Swizzled (type 2) and multisampled (antialias ≠ 0) surfaces are now never copied; the raw `SET_SURFACE_FORMAT` is checked.
  - FP16 and FP32 are byte-swapped bit-exactly; tests cover ±0, ±inf, NaN payloads and subnormals.
  - Under `RSX_RT_READBACK` only, a linear target's initial upload reads guest rows at the surface pitch instead of tightly packed. Without the flag it is byte-identical to before.
  - MRT targets B–D have no recorded pitch and are never copied.
- **Fence:** the dedicated fence is signalled after `ExecuteCommandLists`, because `render_frame()` calls `wait_for_gpu()` and that signals the frame fence before the list exists. Device removal (completed value `UINT64_MAX`) and backend shutdown drop all pending copies and stop the worker before guest memory is torn down.
- **Labels and semaphores (unchanged, review only):** `NV4097_SET_SEMAPHORE_OFFSET` / `BACK_END_WRITE_SEMAPHORE_RELEASE` (0x1D6C/0x1D70, `rsx_commands.c`) are written when the drain reaches them, before the GPU has executed the preceding draws and before any readback is applied. On hardware a back-end release follows the ROP flush. A title that waits on such a label and then reads a target can still see stale data. Left as is: changing it alters guest-visible sync without RSX evidence.
- **Tests:** `tests/test_rt_readback.c` passes 191 checks under MSVC (`vcvars64`; the C test ran, not skipped), and under WSL gcc and clang with ASan/UBSan/LSan. The Windows suite passes 109/109.
- **Proposed run (awaiting approval):** `generated/introskip/rtrb_diag_cmd.txt`. It is the rtvis command with the new exe, `--name garage-rtrb`, `RSX_RT_READBACK=1` and `RSX_RT_READBACK_LOG=160`.

## Generic RSX render-target readback (offline, 2026-10-24)

- **Coherency model (VERIFIED from the backend source):** an offscreen target is a D3D12 resource keyed by its raw RSX offset (`off_rt_find`). Its guest bytes are uploaded once when the resource is created and never written back, so guest memory and the target diverge from the first draw. A GPU write goes through four stages: recorded (the drain builds a draw record), submitted (`ExecuteCommandLists` in `render_frame`), completed (a fence passed) and applied (bytes written to guest memory). Only applied is guest-visible. A completed frame is not visible until something copies it back.
- **No HLE lock hook:** MotorStorm's lock (`func_005083E8`) is lifted guest code that returns the surface address without waiting. No firmware call marks a CPU access, so the lock path offers no generic sync point.
- **The 45 pre-submission reads (VERIFIED from code):** the drain counts a flip when it reaches the FIFO flip marker and sets `s_flip_pending`. `render_frame` (submission) then runs later on the present/ticker thread. A PPU read that lands in that gap sees the write recorded but not submitted. On hardware the RSX has executed every command before the flip by the time it processes the flip; here, recording is not execution.
- **Implementation (ps3recomp-int `5b1988f`, opt-in `RSX_RT_READBACK=1`, experimental):** the core is `include/ps3emu/rt_readback.h`, wired into `rsx_d3d12_backend.c`.
  - Which surfaces are copied: a colour surface the GPU writes but never samples for `RSX_RT_READBACK_MIN_ORPHAN` consecutive generations (default 2), and no larger than `RSX_RT_READBACK_MAX_BYTES` (default 65536). No address or shader rule.
  - The copy goes into a READBACK staging buffer at the end of the batch, in the same command list. Rows use a 256-aligned staging pitch and are written to guest memory at the guest pitch. Supported formats: A8R8G8B8, FP16×4, FP32×4 and FP32; any other format, or an unknown pitch (MRT B–D), is never copied.
  - A dedicated fence is signalled right after `ExecuteCommandLists`. The frame `fence_values` can't be used because `wait_for_gpu` bumps and signals them mid-frame, before the list exists.
  - A worker thread wakes on that fence and applies the copies. The guest, drain and render threads gain no wait, and nothing is submitted early.
  - Copies apply in fence order, then write order, so the last writer wins on overlapping surfaces.
  - A copy is dropped when its surface was replaced (new identity, size, pitch or format) or evicted, when a newer generation is already applied, when the guest bytes changed since it was queued (a CPU write; older pending copies are dropped too), when the device was removed (fence `UINT64_MAX`), or when the list failed to close.
- **Tests:** `tests/test_rt_readback.c` passes 138 checks under MSVC, and under WSL gcc and clang with ASan/UBSan. It covers write→read, one-frame-delayed reads, reads before submission, after submission and after completion, multiple writes, replacement and eviction, aliasing, pitch and formats, unrelated and sampled surfaces, the CPU-write guard and slot exhaustion. `tools/test_rt_readback.py` and the Windows suite pass (109/109), and a CI step was added.
- **Exe:** `e17da4f75289c7172d4e119811636513cea4cf40c331f0dbb33b03f39e768398` in `build/motorstorm-int-rtrb-e17da4f7`. Not launched.
- **Expected behaviour (HYPOTHESIS):** about 1745/1800 reads would see frame N−1 (the hardware latency) and the 45 early reads frame N−2. No generic rule justifies submitting earlier for them: the guest issues no sync between the flip and its read.
- **Open:**
  - The guard compares and then writes, so a PPU write in between is lost, and a reader can see a half-applied copy.
  - Hardware ROP flush rules are not modelled. Back-end labels and semaphores still become guest-visible at drain time, before the GPU work they follow.
  - The selection rule is a heuristic: a dead small target is copied needlessly, and a CPU-read target the GPU also samples is never copied.
  - Target creation still uploads at a tight pitch (`w*bpp`), not the guest pitch.

## Exposure readback: RTVIS diagnostic run (run `20261024-194334-garage-rtvis`, 2026-10-24)

- **Run:** exe `1f7d5947…` (ps3recomp-int `1bc3b93`), command `generated/introskip/rtvis_diag_cmd.txt`, one launch, no retries, no RSXI. Stopped on the 1800-read summary after 86.6 s; no fatal line, no GPU watchdog, hard deadline not fired. Cache snapshot `generated/cache-snapshots/20261024-194334`.
- **Lock (VERIFIED):** all 64 `[icw]` lines: site `0x004C380C` → target `func_005083E8`; object `0x173F42E0`, vtable `0x010414A8`, type `[+0x68]=0` (the no-wait path), lock flag `[+0x30]` 0→1 (back to 0 at every next call, so slot 7 unlocks), `*out = 0xC6A1E400`, return `0x80` (pitch). The static candidate is the runtime target.
- **Order (VERIFIED, host order of the drain/PPU events):** steady state is, per frame, `W(op 603) → S → C → R×5 → W …`. Op 603 is written once per frame (48× op 603, plus op 602/607 once each at the start). The 5 reads (offsets +578, +1322, +1362, +1426, +1514, the G half of 5 texels) all happen with **exactly one drained flip** between the newest write and the read (1790 of 1790 post-write reads), never zero. So the read in frame N consumes op 603 of frame N−1.
- **GPU completion before the read:** 1745/1800 reads COMPLETE (the previous frame's fence had completed), 45 RECORDED (the previous frame's write was recorded but the backend had not presented/submitted it yet), 10 BEFORE_WRITE (first frames), 0 SUBMITTED. All values read 0x0000: the backend never makes the data guest-visible.
- **What it shows:** the game reads the previous frame's exposure result and does not wait for it. The 45 RECORDED reads happened before the backend had presented the frame that wrote it, so the guest read regardless of flip completion. HYPOTHESIS: on hardware the RSX has long finished frame N−1's op 603 by then, and the game tolerates one frame of latency without synchronisation.
- **Instrumentation defect:** the `follows_read`/`precedes_read` field is invalid. MotorStorm's `put` stays in a small ring (`0x10068–0x13068`) that calls into two alternating command buffers (`0x0002C4B0` / `0x0022C4B0`), and the "guest current" pointer read as io `0x4`. Lap:offset comparison does not order those, so the 356/2 counts mean nothing. The flip distance is the valid ordering evidence.
- **Not implemented:** the measured ordering (W(N−1) → flip(N−1) → R(N), no guest wait) fixes the latency but not the mechanism. A copy-back once frame N−1's fence completes would have served 1745/1800 reads. The other 45 would need the backend to submit before the guest's next read, and no guest event marks that point. How to select CPU-read targets generically (rather than every offscreen target each frame) is also open.

## Exposure readback synchronization: static call graph + diagnostics, run prepared (2026-10-24, no launch)

- **TOC correction (VERIFIED):** the EBOOT's function descriptors use TOCs `0x0109FBF0` (8040 OPDs), `0x010CE894` (3935) and `0x010AFBE4` (2450). The values `0x010A0EF0` and `0x010CEB94` recorded earlier occur nowhere in the ELF. `vtslot.py`/`opdref.py` scans need the corrected set; `generated/introskip/expo/tocs.py` lists them.
- **Call graph (static):**
  - `func_0034CDE8` → stub `0x00754F78` (TOC `0x0109FBF0`→`0x010AFBE4`) → `func_004C3778`, from exactly two sites (`0x0034CF30`, `0x0034F954`), both in the function's prologue, after `func_00448B38` (shader-parameter setup, no wait) and `[r24]->vt[0x34]` (returns the exposure object). VERIFIED: no other `b`/`bl` reaches `0x004C3778` or its stub, and no OPD names it.
  - The run-time stack in the 18:04 run named `func_00448B38` ← `func_00502F88`; the static graph says the call follows `func_00448B38` inside `func_0034CDE8`. PARTIAL: the next run's `[icw]` line settles it.
  - `func_004C3778`: `obj=[this+0x34]`; `ps3_indirect_call` through `[[obj]+0x24]` (slot 9) with `r4=sp+0x70`, `r5..r7=0` (call site LR `0x004C380C`); reads `base + y*128 + x*8 + 2` for each sample point in `[this+0x1A0..]`; then `[[obj]+0x1C]` (slot 7, presumably unlock).
  - Slot 9 candidate `func_005083E8` (vtable `0x010414A8`, OPD `0x0108BEF0`, the only reference to it): sets `[this+0x30]=1`, `[this+0x34]=r5`, takes `s=[this+0x88]`; type `[this+0x68]` 0: `*out=[s+0x10]`, returns `[s+0x40]&0xFFFFF`, no wait; types 1/2: `func_007571A8` → `func_007320A0` (allocation/conversion helpers `func_00728DB8`, `func_0072C950`, …, no label poll found). Slot 7 of that vtable is `func_004F7710`. Of all 224 slot-9 implementations (every vtable, all three TOCs), it is the only one that stores both `[this+0x30]` and `[this+0x34]=r5` (PARTIAL: the run-time target and type are still unobserved).
  - **Frame order (HYPOTHESIS, strong):** the read happens at the top of the post-process function, before it records its own passes, so the guest reads the previous invocation's op 603 unless something earlier in the frame issued it. The `W … follows_read` field below decides it.
- **Diagnostics added (ps3recomp-int, off by default):**
  - `RSX_RTVIS=<local off>[,<len>][,max=<n>]` (`include/ps3emu/rt_vis_trace.h`, glue in `cellGcmSys.c`): `W` (draw/clear recorded into the range, FIFO lap:offset, drained flips, RSXI op number), `S` (command list submitted, covering fence), `C` (fence observed complete, non-blocking `GetCompletedValue`), `R` (guest load: value, class BEFORE_WRITE/RECORDED/SUBMITTED/COMPLETE, flips since the write, guest put/current, drain get). Each `W` reports whether it `follows`/`precedes` the last read in guest FIFO order. Summary every 600 reads. Turns inline loads off (like `PPU_RWATCH`).
  - `PPU_ICALL_WATCH=<hex,…>` (+`_MEM`, `_MAX`; `include/ps3emu/icall_watch.h`, hook in `ps3_indirect_call`): matches call site (LR) or target; logs thread, target, r3..r7, chosen words before/after, return value, and the `RSX_RTVIS` state.
  - Neither writes guest memory, waits, or changes registers. The trace prints from the drain and PPU threads (bounded), so it perturbs timing slightly.
- **Tests:** `tools/test_rt_vis_trace.py` (343 checks: mapping, FP16 BE, pitch 128 and 512, bounds, sequence, FIFO wrap, fences, bounded output, enable/disable) and `tools/test_icall_watch.py` (1029 checks); pass under MSVC and WSL gcc/clang. Windows suite 108/108; WSL 105/108 (only the 3 inherited `ppu_hle.cpp` link failures). Commit `1bc3b93` (ps3recomp-int, not pushed).
- **Exe:** `1f7d5947c71312495d42065e285a73f6712c055bf80ae1208a7865b9ee751839` (source = `1bc3b93`) in `build/motorstorm-int-rtvis-1f7d5947`.
- **Prepared run (not executed):** `generated/introskip/rtvis_diag_cmd.txt`. No RSXI capture (its per-frame GPU wait would add the very sync under test). Stops on the 1800-read summary line, a fatal line, the GPU watchdog, or 150 s.
- **No backend correction.** The visibility point is still unmeasured.

## Exposure readback: static investigation, stopped before a code change (2026-10-24, no launch)

- **Transfer mechanism (VERIFIED):** there is no transfer command. Op 603 sets the colour surface to local offset `0x06A1E400` (format `0x14B`: linear, FP16×4, pitch 128) and the RSX ROP writes there directly. The PPU reads the same bytes through the local-memory mapping at `0xC6A1E400`. No NV0039, NV3062 or NV308A transfer in the run's `[xfer]` log targets the region (subchannel 3 writes only shader uploads at `0x0074xxxx`; subchannel 5 writes only small offsets). The run logged no back-end label (`0x1D70`) or NV406E release.
- **Layout and byte order (VERIFIED):** `func_004C3778` reads `base + y*128 + x*8 + 2` as one big-endian half and converts it with `func_00756E08`. That is component 1 (G) of RGBA16F. Op 603's FP (`fp_0074C781`) writes luminance (`dot(rgb, 0.2126/0.7153/0.0722)`, then clamped) to `h0.y`. So the guest layout is R,G,B,A, with each FP16 big-endian, 8 bytes per pixel.
- **CPU access path (PARTIAL):** before reading, `func_004C3778` calls vtable slot 9 (`+0x24`) of the texture at `[this+0x34]`, which returns the base address in `[sp+0x70]`.
  - The static candidate is `func_005083E8` (vtable `0x010414A8`, slot 9). It stores `[this+0x30]=1` and `[this+0x34]=level`, then writes `*out = [surface+0x10]`.
  - Its type-0 path (`[this+0x68]==0`) has no label poll, fence or finish. Types 1 and 2 go through the cross-TOC library `func_007571A8` → `func_007320A0`, which hasn't been traced.
  - Neither the runtime target nor the type value is confirmed.
- **CPU visibility point (BLOCKED):** the RSX FIFO drains on the ticker thread, asynchronously to the PPU. Nothing establishes whether the read in frame N follows this frame's op 603 or the previous one, or which RSX event the game relies on.
- **Root cause in the backend (VERIFIED):** the D3D12 RT pool in `rsx_d3d12_backend.c` is the only copy of rendered surfaces, and nothing writes an RT back to guest local memory for CPU reads. The only surface-to-guest path in the tree is `rsx_draw_engine.c`'s `eng_surface_to_guest`, which isn't on MotorStorm's RSXI path. It handles only R8G8B8A8, and only when the GPU later samples the surface.
- **Not implemented, as instructed:** neither a sync-point copy-back (unproven trigger) nor a page-fault-driven write-back. The fault-driven version needs a VEH shared with `vm_commit_veh`, cross-thread readback requests to the ticker, and exclusion of the backend's own `vm_base` reads, so it is neither small nor verifiable offline.
- **Next experiment (needs launch approval):** one bounded run with a write watch on the exposure texture object's `+0x30` lock flag (guest stack identifies the lock target and `[+0x68]`), plus a log line at each `func_004C3778` read with the ticker's last drained op index or FIFO EA. That decides whether the read follows op 603 in the same frame and which point the write-back must precede.
- **Helpers:** `generated/introskip/expo/vtslot.py` (vtable slot scan; OPDs with any of the game's 3 TOCs) and `fnbody.py` (extracts lifted bodies).

## Garage validation run: aliasing fix + exposure readback (run `20261024-180419-garage-alias-exposure`, 2026-10-24)

- **Run:**
  - Exe `6587eeecf643cb607fb4b27dd9a59769c26f0089d7b05fcccff16ae28da53d39` (ps3recomp-int `4ca0627`, suite 106/106), copied to `build/motorstorm-int-alias-6587eeec`.
  - Same command as `restart_present_cmd.txt` (intro skip, `VP_NOFIXPROJ=1`), plus `PPU_RWATCH=C6A1E400,0x800` and `PPU_WWATCH=C6A1E400` (`PPU_WWATCH_LEN=0x800`). Command in `generated/introskip/alias_exposure_cmd.txt`.
  - Stopped at `garage_capture_complete` after 71 s. RSXI frames f001729–f001879, stride 30.
- **Velocity (VERIFIED):**
  - Op 596 (`0x01650000`): before, noise with mean (126,127,107) and 541,782 distinct colours. Now uniform 0 in every captured frame.
  - The runtime constant is `float4(0, 1.65262e-24, 0, 6.17512e-25)` read with `.xxxx`, so c.x = 0.0. The program scales the velocity by 0 and packs it; 0 is the correct output.
- **Final image (VERIFIED):**
  - The backbuffer now shows the garage dome and the rider sharply; before, op 613's noise-driven blur smeared them. See `bb_before_after.png` (top before, bottom after).
  - 9.4 % of pixels changed. The scene target `0x00750000` and the UI are unchanged, with no new artefacts. The image is still dark.
- **Exposure readback (VERIFIED):**
  - Op 603 renders `0x06A1E400` on the host: 16×16 FP16 (DXGI 10), pitch 128, slot 25, 43 % non-zero.
  - The PPU reads 5 FP16 values from it every frame (offsets 0x242, 0x52A, 0x552, 0x592, 0x5EA), in `func_004C3778` called from `func_00448B38` ← `func_00502F88`. Every value read is 0x0000.
  - No PPU store and no NV0039/NV3089 transfer touches the 2 KB. The guest bytes are never written, so the game consumes zeros that were never initialised.
  - Missing sync: the backend never copies a render target back to guest local memory after the GPU writes it. Op 603's result must reach `0xC6A1E400` before the PPU read in the next frame.

## Garage final compositing: offline diagnosis (run `20261024-142859-garage-restart-present`, f001764, 2026-10-24)

- No launch. Inputs: RSXI events, BMP snapshots and decompiled FPs of f001764 (steady state).
- **Op 613 inputs (FP `0x02193941`, writes the backbuffer).** Output = grade(lerp(scene, motion blur(u4), w) ⊕ u5 + u6.rgb) × u6.a, where w = sat(100·|u1.xy|).

  | unit | guest address, descriptor | backend resource | last writer | contents (BMP RGB) |
  |---|---|---|---|---|
  | 0 | `0x06A8F400` 320×180 A8R8G8B8 | 320×180 RGBA8 | op 601 | flat (128,128,0), alpha ≈ 0, so the offset is 0 (neutral) |
  | 1 | `0x01650000` 2558×719 Y16_X16_FLOAT, pitch 10240 | 1280×720 RGBA8 | op 596 (FP `0x0074CE81`) | noise, mean (126,127,107) |
  | 2 | `0x01DD0000` 1279×719 A8R8G8B8 | 1280×720 RGBA8 | op 602 | scene copy, mean (5.0,2.1,0.3) |
  | 3 | `0x02190000` 32×32 | upload | — | jitter noise |
  | 4 | `0x022D0000` 640×360 A8R8G8B8 | 640×360 RGBA8 | op 604 | half-res scene, mean (5.0,2.1,0.3) |
  | 5 | `0x079D0000` 640×360 | 640×360 RGBA8 | op 518 | all zero, including alpha |
  | 6 | `0x022B5D80` 80×45 FP16 | 80×45 FP16 | op 612 (605 clear → 606 bright pass + vignette in alpha → 607–612 blur) | RGB 0, alpha nonzero |

- **VERIFIED: what `0x01650000` is.**
  - Its surface format `0x3148` is A8R8G8B8, linear, with antialias field 3: 2 samples stored side by side.
  - So the guest surface is 2560×720 at pitch 10240. The 2558×719 descriptors (both `0xA5` and `0xBF`) read that raw sample plane.
  - The `0xBF` read treats the ARGB8 bytes as packed FP16 pairs. Op 596 produces them by writing `h0.xy` and then running `UP4UB` on `r0.x`.
  - The backend ignores the AA layout and binds the 1280×720 RGBA8 target with UNORM channels.
- **VERIFIED: scene information is not lost in the post chain.**
  - The scene target is already dark before any post-processing: op 513/522 mean (5.1,2.1,0.3), p99 (43,21,10).
  - Ops 602 and 604 carry it on unchanged.
  - Op 613 then smears it. The recorded u1 noise gives w = 1 and random blur offsets up to about 1/8 of the screen.
  - The backbuffer, HUD excluded, correlates −0.06 with grade(scene), so the spatial detail is lost at op 613.
- **VERIFIED and fixed: render targets smaller than 16 texels were allocated at window size.**
  - `current_rt_off` dropped any clip under 16. The luminance-reduction targets got 1280×720 host resources:
    - op 527 (`0x022C0500`, 20×11);
    - op 528 (`0x022C1600`, 10×5);
    - op 597 (`0x06AC7800`, 8×8).
  - Ops 528 and 603 then sampled them as 20×11 and 10×5 textures over the whole resource. 99.99 % of what they read was never written; the snapshots are garbage, mean (95,45,71).
  - Op 603 computes the exposure value (`0x06A1E400`, 16×16) from that garbage; its snapshot is magenta noise.
  - Fix (ps3recomp-int `1db116a`, exe `0f5c64c3…59a3`): `ps3emu/rt_clip.h` keeps clips from 1 to 2048 (0 or out-of-range still means window size). Test: `tools/test_rt_clip.py` + `libs/video/tests/test_rt_clip.c`. Suite 105/105.
- **Not established (HYPOTHESIS):**
  - **Why the scene is dark.** No GPU draw reads `0x06A1E400` or `0x06AC7800`, so the game reads them on the PPU. The backend never writes render targets back to guest memory, so the PPU sees stale data whatever this fix does. This matches the earlier "exposure readback" suspicion.
  - **Op 596's constant.** `MUL h0.xy, r0, c.x` uses c.x = 1.65e-24 in the capture. That value is not in `global.rpk`, so the engine patches it at run time. Unchecked.
- **Fixed: fp16/fp32 register aliasing (VERIFIED).**
  - On NV40, H[2k].xy = R[k].x, H[2k].zw = R[k].y, H[2k+1].xy = R[k].z and H[2k+1].zw = R[k].w, packed as PK2H. The decompiler kept `h[]` and `r[]` apart, so reading one view after writing the other gave 0.
  - Guest bytes: the velocity program FP `0x04D7D4C1` is in `MS2.PSARC:/global.rpk` at 0x50126 (also at 0x4D567 with a TEX tail). It is DIV h0.xy, DIV h0.zw, ADD h0.xy, `UP4UB h0, R0.x` (w1 `1C9DC800`, half bit clear). The program reads R0 and only ever wrote H0, so it wrote 0 instead of the packed velocity. Op 596 (`0x0074CE81`) has the same `h0.xy` → `UP4UB r0.x` tail.
  - Fix (ps3recomp-int, see `git log`): a pre-scan marks the fp32 components that one view writes and the other reads, counting exports as reads. After every write to such a component, the decompiler copies it into the other view (`_rsx_pk2h` / `_rsx_up2h`). Programs that never cross views are unchanged.
  - Test: `tools/test_fp_alias.py` + `libs/video/tests/test_fp_alias.c`, with the guest words verbatim; it fails 5 checks on the old decompiler. The emitted HLSL compiles with fxc `ps_5_0`. Suite 106/106.
- **Smallest missing diagnostic:** guest memory at `0x06A1E400` after the flip, to show whether the PPU reads stale exposure data.

## Garage A/B: primitive restart, `RSXI_EVENT=present` (run `20261024-142859-garage-restart-present`, 2026-10-24)

- **Run:** one launch of `restart_present_cmd.txt`, exe `b3fc735d…af43` (`8932e3f`).
  - Stopped by `milestone_reached` at 01:24 (`garage_capture_complete`). The hard deadline did not fire, there were no retries and no leftover processes.
  - Frames captured: f001734, f001764, f001794, f001824, f001854, f001884. Frames 1764–1884 are identical in occlusion data (steady state).
  - Baseline frames: f001752–f001872 of `20261024-134448`.
  - Draws were matched by (rt, fp, vs hash, index offset, first, count, prim); every op 190–253 maps to the same op number. Script: `generated/introskip/cmp_restart.py`.
- **VERIFIED: restart is enabled for the captured draws.**
  - Every indexed draw in ops 190–253 records `restart {enable 1, value 0xFFFF, active 1}`.
  - The u16 index streams contain 65535 markers (for example op 206 `first=[122,125,126,127,65535,…]`).
- **VERIFIED: occlusion, steady state (baseline f001752 → new f001764):**

  | | baseline | new |
  |---|---|---|
  | samples passed, ops 190–253 | 3,984,429 | 814,906 |
  | draws passing, of 62 | 18 | 56 |
  | op 206 | 1,227,224 | 123,170 (−90 %) |
  | op 218 | 817,558 | 21 |
  | op 219 | 919,601 | 39 |
  | ops 222–253 | 0 every draw | almost every draw passes (2–2,087 samples each) |

- **VERIFIED: the scene target (`0x00750000`, op 513) now holds recognizable 3D garage geometry.**
  - It shows the geodesic dome frame, panels, a floor edge and a standing driver model. The driver is the "dark moving shape" and is real geometry, not an artifact.
  - The baseline target was a flat brown fill with wedges. The oversized wedges are gone.
  - The scene is very dark: mean RGB (5.1, 2.1, 0.3), maximum (101, 51, 42).
- **VERIFIED: the final backbuffer is still almost black.** It shows the HUD bars and a faint silhouette of the scene, mean about 20.
- **First remaining discrepancy (VERIFIED as a mismatch; that it causes the darkness is a HYPOTHESIS):** the final composite, op 613, FP `0x02193941`.
  - Unit 1 samples `0x01650000` as a 2558×719 texture, format `0xBF` (linear Y16_X16_FLOAT), pitch 10240, and reads `.xy`.
  - The backend binds the 1280×720 RGBA8 render target (DXGI 28) as is, with no reinterpretation. The baseline is the same.
  - Unit 0 (`0x06A8F400`, written by op 601) is a flat (128,128,0). The other post-process targets (`0x01650000` after op 596, `0x06AC7800`) contain noise-like data.
- **Transient (not in the captured frames):** at guest frame 1755 the per-frame vertex buffer filled up. 21 display draws were dropped before it grew from 393216 to 589824 vertices; there were no more drops after that.
- **Next step:** offline, trace the composite's inputs, units 0–6 of op 613 and the draws that wrote them (ops 595–612). Establish which input makes the result dark, starting with the Y16_X16_FLOAT reinterpretation of `0x01650000`.

## Garage A/B: primitive restart + game camera (run `20261024-141832-garage-restart-noproj`, 2026-10-24)

- **Run:** one launch of `generated/introskip/restart_noproj_cmd.txt`.
  - Exe SHA-256 `b3fc735d…af43`, ps3recomp-int `8932e3f`, `VP_NOFIXPROJ=1`, `VP_FIXPROJ` unset.
  - Stopped by the 210 s timeout. The hard deadline did not fire, there were no retries and no leftover processes, and no fatal errors.
  - The target `garage_capture_complete` was **not reached**.
- **VERIFIED: the game enables primitive restart with index 0xFFFF.**
  - stderr line 626 shows `enable=0`, the initial write. Line 627, at early boot and long before the garage handoff at line ~5919, shows `enable=1 value=0xFFFF`.
  - All 7 later logged writes are `enable=1 value=0xFFFF`. The log stops after 8 writes, so a later disable is not ruled out, but none was seen.
- **BLOCKED: no RSXI frames were captured, so there is no per-draw restart state, occlusion data or scene image.**
  - RSXI reached `wait_event` at frame 1720 but never reached `main`.
  - `RSXI_EVENT=no_present` waits for an offscreen-only replay. In the baseline that replay came at frame 1722; in this run none came (`replayed_no_present` stayed at 1, against 2 in the baseline).
- **PARTIAL (indirect sign that restart is applied):**
  - In the baseline the per-frame VP vertex buffer grew from 393216 to 589824 vertices exactly at frame 1722, the frame RSXI captured.
  - In this run it never grew, so per-frame triangle expansion stayed under 393216 vertices.
  - HYPOTHESIS: the baseline's offscreen-only replay at frame 1722 was a by-product of the oversized frame, so this trigger depends on the bug.
- **Next step:** repeat the same A/B with a capture trigger that does not depend on presenting, for example `RSXI_EVENT=present` or a frame range after the handoff. This is a command-line change only, with no code change.
- **Follow-up analysis (offline, no launch):**
  - **VERIFIED: the game reached the garage and kept rendering after the handoff.** Guest flips rose steadily from about 1720 to 2984 at 8.0–8.8 presents/s. Every present succeeded, with no watchdog or device errors.
  - **VERIFIED: draw rate matches the baseline.** About 75–80 draw groups per flip, against 70–75 in the baseline. The baseline also ran slower here, at 4.8 presents/s.
  - **The timeout is not a progression or performance regression.** The run kept going only because `garage_capture_complete` needs a finished RSXI "main" frame, and the `no_present` trigger never opened one.
  - **Prepared:** `generated/introskip/restart_present_cmd.txt`. It is the same command with only `RSXI_EVENT=present` and `--name garage-restart-present` changed. No source change is needed.
    - The milestone pattern for `garage_capture_complete` does not depend on the trigger.
    - `test_xfer_diag` covers "present: the first replay that will call Present".

## Garage: primitive restart (offline, 2026-10-24, no launch)

- **VERIFIED (from the semantics already used in `rsx_dispatch.c`, which follow RPCS3):**
  - `0x1DAC` = `SET_RESTART_INDEX_ENABLE`, `0x1DB0` = `SET_RESTART_INDEX`.
  - When the enable is non-zero, an index equal to the value ends the current strip or fan without drawing a connecting triangle.
  - For 16-bit index arrays, a value wider than 16 bits disables restart rather than being truncated.
- **VERIFIED: the D3D12 path ignored both methods.**
  - The decoder (`rsx_commands.c`/`rsx_state`) dropped them, so `upload_strip_vp_indexed` fetched 65535 as an ordinary vertex.
  - Only the replay and live-draw harnesses (`rsx_dispatch`) honoured restart.
- **PARTIAL: the game turns restart on.**
  - Lifted game function `func_0050D4B8`, which is reached only through a pointer, calls `func_00734430(ctx, 0xFFFF)`. That emits header `0x41DB0` with data 0xFFFF.
  - It then calls the generic method writer `func_00736260(ctx, 0x1DAC, 1)`, which emits header `0x41DAC` with data 1.
  - No write of 0 to `0x1DAC` was found.
  - Whether the function actually runs before ops 203–253 isn't in any capture: nothing recorded either register.
- **Fix (commit `8932e3f`, ps3recomp-int):**
  - `rsx_state` keeps both registers.
  - `upload_strip_vp_indexed` ends the strip or fan at the guest's value only while restart is active. The next strip starts with even winding, and a fan gets a new centre.
  - Continuity across batches is unchanged when there is no restart.
  - RSXI geometry records now carry `index.restart {enable, value, active}`, and non-finite samples are written as `null`.
  - A one-time `[RSX] restart index enable=… value=…` line goes to stderr.
- **Tests:**
  - `test_prim_stream` covers: restart disabled; u16; u32; custom values; a wide value with u16 indices; 12 restarts on and next to 256-index seams; a restart at the end of a batch; strips and fans; winding parity; degenerate triangles; continuity across a seam.
  - The C harness passes under WSL.
  - Windows suite 104/104.
  - Under WSL, `test_loaded_image_memory`, `test_sail_boot_callback` and `test_sysmodule_unload_module_ex` fail with `ppu_hle.cpp` link errors. Their files are untouched by this change.
- **Exe:** `build/motorstorm-int-restart-b3fc735d/`, SHA-256 `b3fc735d0eaa566412b5a9a8e9da8420c8f531f9bde3fbadb93813d8bf12af43`.
- **Proposed A/B run:** `generated/introskip/restart_noproj_cmd.txt`. It is `geom203_noproj_cmd.txt` with only the exe path and run name changed, so `VP_NOFIXPROJ=1` stays set.
  - Compare against `20261024-134448-garage-geom203-noproj`: the `[RSX] restart index` line, `index.restart` for ops 203–253, samples passed for 206 and 215–253, and the scene target after op 513.

## Garage A/B: the game's own camera, `VP_NOFIXPROJ=1` (run `20261024-134448-garage-geom203-noproj`, 2026-10-24)

One launch: same exe `6a68dbef…` (`d2ca9dc`) and the same command as `20261024-122122-garage-geom203`, plus `VP_NOFIXPROJ=1`.
- Stopped by `milestone_reached` (`garage_capture_complete`) at 86 s.
- No hard deadline, no retries, no leftover process.
- Cache snapshot: `cache-snapshots/20261024-134448`.
- Compared frame: f001752 against the earlier f001755. The draw list is the same: 619 draws, with the main scene target `0x00750000` covering ops 203–253.

- **VERIFIED: the substitution is gone.**
  - `[VPFB]` lines: 6 in the earlier run, 0 now.
  - The captured c0–c3 are the game's own values: c0 = (−0.60048, −0.141812, −0.863489, −0.863474), c3 = (−0.646611, −3.72679, −3.33445, −3.13439).
  - c4 onward was never overwritten (the fallback writes only 16 floats, i.e. c0–c3).
- **VERIFIED: occlusion for ops 190–253 changed.**
  - Op 203: 0 → 360434. Op 204: 0 → 0.
  - Op 205: 105509 → 213819. Op 206: 3906 → 1227224 (more than the 921600 pixels on screen).
  - Draws that pass: 43 → 18. Total samples passed: 11.3 M → 4.0 M.
  - From op 220 on, every draw passes 0 samples.
- **VERIFIED: still no recognisable garage.**
  - The main scene target (after op 513) is a nearly flat yellow-brown fill crossed by large wedges, with 18 distinct colours at 160×90.
  - The earlier run showed a thin textured horizon band.
  - The final backbuffer has a brown tint behind the HUD, but no geometry.
- **VERIFIED: the game's matrix produces valid clip coordinates.**
  - The vertex program computes `clip = x·c0 + y·c1 + z·c2 + c3`.
  - In the 16-vertex samples, ops 211, 215, 223, 233, 245, 247, 248, 251 and 253 have 12–16 vertices inside the frustum, with NDC z between 0.997 and 0.999.
  - Even so, every one of these ops from 215 on passes 0 samples. They have depth test and write on, function 3, cull 1 and colour mask 15.
- **PARTIAL: depth rejection caused by triangles through the restart index.**
  - Every strip in 203–253 except 204, 209 and 211 has index 65535 in its first 8 indices.
  - Vertex 65535 reads as (0,0,0,1). Under this camera it lands at clip = c3, with w = −3.13, so it is behind the eye.
  - Triangles joining it to visible vertices are clipped at the near plane and cover the whole screen. That matches op 206 passing 1.23 M samples with depth write on.
  - Those triangles then fill the depth buffer with near values, so the real geometry fails depth function 3 (≤).
  - Under the substitute camera, the same vertex projects to w = 0, which is why these triangles weren't visible before.
- **Next:** generic primitive-restart support in the D3D12 indexed strip and fan expanders. It must honour the guest's restart enable and index (`0x1DAC`/`0x1DB0`) and have offline tests. After that, one more A/B run with `VP_NOFIXPROJ=1`.
  - The camera fallback is a real defect, but its permanent fix waits until garage geometry is visible.

## Garage draw 203: the backend replaces the game's camera matrix (run `20261024-122122-garage-geom203`, 2026-10-24)

One launch of exe `6a68dbef…` (`d2ca9dc`).
- Stopped by `milestone_reached` (`garage_capture_complete`) at 73 s.
- No hard deadline, no GPU watchdog, no retries, no leftover process.
- Six frames captured: f001695 to f001845. There is no f001765 this time; op 203/204 have the same signature in every frame. Figures below are from f001755.

- **VERIFIED: one primitive stream.**
  - Op 203: `first` 0, count 256, `stream: new`.
  - Op 204: `first` 256, count 238, same `begin_epoch` 25138, `stream: same_begin_end_contiguous`.
  - Ops 205/206 have the same structure. The `prim_stream.h` correction (`11e068f`) applies.
- **VERIFIED: index and vertex inputs decode cleanly.**
  - Indices: u16, local memory, offset `0x05E9B600`.
  - Position (a0): F32×3, stride 20.
  - No non-finite inputs and no w ≤ 0.
  - Range: x −5547..6201, y −568..3305, z −4088..5997.
- **VERIFIED: index 65535 appears inside these strips** (e.g. `0,1,2,65535,3,…`; 352 of 619 draws have it in their first 8 indices).
  - The D3D12 strip expander treats it as a real vertex. Vertex 65535 decodes to (0,0,0,1), giving spurious triangles to the origin.
  - It looks like a primitive-restart marker. `rsx_dispatch` tracks `SET_RESTART_INDEX(_ENABLE)` (0x1DAC/0x1DB0), but the D3D12 path's `rsx_state` does not.
  - The guest's restart-enable value is not captured.
- **Occlusion:**
  - op 203: 0 samples; op 204: 0; op 205: 105509; op 206: 3906.
  - 43 of the 62 queried ops pass samples.
- **VERIFIED, first discrepancy: the garbage-projection fallback in `vp_record_cb` fired for ops 203–595 (378 of 619 draws).**
  - The game's real `vp_c[0].x` is −0.60048. That is a valid value for a combined view-projection matrix, but the heuristic requires 0 < c0.x < 8.
  - The backend therefore overwrote c0–c15 with a fixed camera (1.358 / 2.414 / 0.0101). The captured constants show these values, and the log shows `[VPFB] fallback proj on draw slot 203 (c00=-0.60048)`.
  - Every scene draw is therefore projected through a camera the game never set. The 0 samples for op 203/204 come from that substitute camera.
- **Not yet observable:** whether the strip fix improves the image. The substitute projection hides it.
- **Next:** a generic correction. The fallback must not fire on a valid matrix whose c0.x is negative. Today it can only be suppressed with the existing `VP_NOFIXPROJ=1`. After that comes primitive-restart support in the D3D12 indexed expanders, with offline tests.
- `nan` positions in the `geom.input.sample` arrays make the line invalid JSON. Parse with NaN tolerance, or fix the writer to emit `null`.

## Garage draw 203: geometry capture instrumentation (offline, 2026-10-24, no launch)

VERIFIED offline; not yet run. ps3recomp-int `d2ca9dc`. Exe `build/motorstorm-int-geom-6a68dbef/`, SHA-256 `6a68dbeffc3279feb982fde59cedfc72c260fdfefed1f17db18813c603b2fffa`.

- `RSXI_GEOM=<n>` adds a `geom` block to each RSXI draw event:
  - `first`, `begin_epoch` and `stream`: `new`, `same_begin_end` or `same_begin_end_contiguous`, relative to the previous record;
  - `index`: type, loc, offset, min, max, and the first 8 indices;
  - `a0`: offset, stride, size, type, and `raw_first` (the guest bytes at the first vertex);
  - `input`: the decoded VP position inputs that went to D3D12 (vertices, lo/hi, nonfinite, w_le0, degenerate_tris, and the first n positions).
- `RSXI_OCC=<lo>-<hi>`: occlusion events (`samples_passed`) for ops lo..hi, up to 64 per frame.
- Both are off by default.
- Tests:
  - `tools/test_rsxi_geom.py` source checks pass;
  - geometry harness passes (WSL);
  - WARP occlusion harness: outside 0, zero-area 0, quarter 1024, full 4096; target identical with and without queries;
  - suite 104/104.
- Not covered: clip-space positions. Those need the VP; the capture provides the VP HLSL, the constants (`RSXI_VP_CONSTS=512`) and the input positions for offline replay.
- Prepared single run: `generated/introskip/geom203_cmd.txt`. This is the tcw45 command with the c45 watches replaced by `RSXI_GEOM=16 RSXI_OCC=190-253`. It needs authorization.

## Garage draw 203: strip batches lost their seam triangles (offline, 2026-10-24, no launch)

- VERIFIED (capture `20261024-101502-garage-tcw45`, f001765): op 203 (vp `0xCEED7030`, fp `0x04D7D301`) is guest TRIANGLE_STRIP count 256, and op 204 has identical state with count 238.
  - Of the 619 draws, 545 have exactly count 256, the most one `DRAW_INDEX_ARRAY` word can encode. libgcm splits larger strips into 256-index batches inside one BEGIN/END.
  - Native ops 203 and 204 drew 762 and 708 vertices, i.e. 254 + 236 triangles.
- VERIFIED (code): both D3D12 strip expanders (`upload_strip_vp`, `upload_strip_vp_indexed`) expanded every batch as a new strip.
  - Each extra batch of one strip lost its 2 seam triangles; a later fan batch would also lose the fan centre.
  - The backend already concatenates TRIANGLES batches for the same hardware rule.
- FIXED, ps3recomp-int `11e068f` (local, not pushed): new `include/ps3emu/prim_stream.h`.
  - It carries the last two vertices, the fan centre and the parity across batches of the same BEGIN/END, primitive and indexed/non-indexed source.
  - `tools/test_prim_stream.py`: a 256+238 strip gives 492 triangles, equal to the unsplit strip. Strips and fans in batches of 1..7 also match the unsplit primitive.
  - `test_draw_rejection` updated. Suite 103/103 (Windows), C harnesses PASS under WSL.
  - `build/motorstorm-int` rebuilt, SHA-256 `a0f547dc58099c72a226b1b578e9bb9ab7e7b9121246ba4928c17406a2b4a00d`. Not run.
- PARTIAL: the fix restores about 2 triangles per 256 indices (cracks), so it does not explain the 21.8 % coverage.
  - That op 203 and op 204 share one BEGIN/END is HYPOTHESIS: `begin_epoch` and the guest `first` index are not exported to RSXI.
- BLOCKED: the capture has no vertex/index data, so op 203's clip-space positions and expected coverage cannot be reconstructed offline.
  - Depth state cannot be what removes op 203: zeta 0x00ED0000 was cleared at op 201, it has no earlier draw, depth func 3 (LEQUAL), write off.
  - Needed instrumentation (RSXI, per draw):
    1. guest `first`, `begin_epoch`, index type/offset;
    2. the attribute-0 format/stride/offset and the first N decoded positions;
    3. CPU-side clip-space positions through the decompiled VP's `vp_c` (bounding box, w sign);
    4. a D3D12 occlusion query giving samples passed.

## Constant-table hypothesis: c45–c54 is a particle-shader table; constant investigation stopped (offline, 2026-10-24, no launch)

- VERIFIED: SHO entries are 12 bytes (name hash BE, type 02, cols, rows u16, register u16, `ffff`), sorted by ascending name hash. Parser: `generated/analysis/c38_sho.py`.
- VERIFIED: c45's hash `0x1643E2F2` occurs only in `ParticleEffectShaders.rpk` (28×), not in `track_garage`, the garage sky/env, vehicle or `global` rpks.
- VERIFIED: the table at 0x279DB in that file lists, in hash order:
  - c53 (float4), c45 (float3×4 → c45–c48), c33, c49 (float3×4 → c49–c52), c35, c54 (float4), c56, c32 (float3), c4, c16, c34, c0, c57 (float1).
  - It contains every register of the observed group: 45–47, 49–51, 53, 54.
  - c53 has the smallest hash, so it comes first and c45 second. This matches the observed LOAD-before = 53 on all 155 c45 uploads.
  - c48 and c52 are the 4th rows of float3×4 arrays (zero data is indistinguishable from not uploaded).
  - The non-float `w` words in c46/c47 (float3 rows) and in c57 lanes y–w (float1) are what row-wise vec4 copies from a packed value buffer would produce.
  - So the suspicious c57 lanes are explained and are not evidence of corruption.
- PARTIAL: the match rests on one transition (53→45) plus register membership. Other transitions were not traced.
- VERIFIED: c38 (`0x8587F24B`) is not in this particle table (0 occurrences in `ParticleEffectShaders.rpk`).
  - c38 is in the per-shader tables of the garage geometry VPs (e.g. `Track0a_Garage_Sky1_driver.rpk` 0x2F2C15, hash order c256, c33, c35, c56, c38, c32, c4, c16, c0, c467, c57).
  - No captured VP reads c45–c54, so the particle draws that own them are not in the captured frames.
- NOT ESTABLISHED: any filter that drops c38. The particle path cannot show one because its table has no c38.
- Per the stop rule, the constant investigation stops here.
- Next (rasterization), frame f001765:
  - ops 1–200 are a depth-only shadow pass (cmask 0, zeta 0x06FF0000), so color snapshots cannot judge them.
  - The earliest geometry draw into the scene target is op 203: vp `0xCEED7030`, fp `0x04D7D301`, rt 0x00750000 + MRT 0x01650000, depth test on / write off, cull 1, 256 indices.
  - The first opaque, c38-reading draw is op 205 (`0x9158278F`/`0x04D81101`).
  - After the whole geometry pass only 21.8 % of 0x00750000 is non-zero (`nonzero_fraction`, alpha included).

## c45 upload path traced (run `20261024-101502-garage-tcw45`, 2026-10-24)

- Run: one launch with `generated/introskip/tcw45_cmd.txt` (the only changes from `tcw_cmd.txt` are the run name and the watch slot/max), exe `593265ac…` (SHA re-verified).
  - Stopped on `milestone_reached` (garage_capture_complete) at 01:10; wall time 70.1 s.
  - No watchdog stop, no fatal error, 0 retries, no process left running.
  - Extracts are in `tcw.txt` and `vpc.txt` in the run directory.
- PROVEN: c45 receives 155 FIFO uploads. Not capped (155 of the 4096-line limit).
  - All 155 have the same shape: subch 0, inc, method 0x1EFC, count=5 (LOAD + 1 vec4), LOAD 53→45, dst c45..c45, rx=4, applied=4.
  - No upload is a block that starts below c45, and none goes to another subchannel.
  - `[vpc-watch]` shows exactly 155×4 lane writes, so received and applied values agree and no other path writes c45.
- PROVEN, first upload: `get=0x0001AE00`, block #166069. It is inside the first RSXI-captured frame f001735, between op 200 and op 203.
  - It sets c45 = (0.0715695, −0.0416058, 1, 0).
  - In the same gap, c46, c47, c49–c51, c53 and c54 also become non-zero. c48 and c52 stay 0.
  - The first draw after the gap is op 203: vp `0xCEED7030`, fp `0x04D7D301`, rt `0x00750000`.
  - Every later upload is at `get=0x0001AD18` or `0x0021AD18` (alternating, the same position in each double-buffered frame stream). Only the next upload changes the value, to (0.114293, −0.0437671, 1, 0); the remaining 153 rewrite the same value.
- PROVEN: no garage VP captured in this run reads c45–c54.
  - Static reads in c30–c63 are limited to 32, 33, 35–38, 42, 56, 57, 59.
  - The only relative reads are `vp_c[64+a0]` (VPs `0x81429E77`, `0xEF8280B7`, `0xF2ECC442`).
  - So there is no "first draw consuming c45" to compare against. c45 changes once (frame 1735 → 1765) and is then constant.
- PROVEN: LOAD-before = 53 on every c45 upload, so the constant upload immediately before c45 started at c53. The group is therefore not uploaded in ascending order.
  - c46/c47 carry non-float `w` words (1.8e25, 2.1e-44), and c54 = (−0.1, c53.x, c53.y, 0) is c53 shifted by one lane.
  - These patterns are consistent with words copied from a packed source table, not from vec4-aligned PPU temporaries (HYPOTHESIS).
- Compared with c32 (FIFO sample from this run, early boot, at `get=0x0021440C`; per-draw values from RSXI):
  - Both use the same form (subch 0, inc, single vec4, count=5). That form is common to the PPU helpers `0x735140`/`0x7351E0`, Material `0x4F9DF0` and renderablejob's 0x00141EFC header, so it does not identify the producer.
  - c32 has 4–5 distinct values per frame. c45 has one.
  - FIFO order relative to c32 within a garage frame is not available: RSXI `cmd_offset` is 0, and c32 was not FIFO-traced in the garage.
- Candidates still open: renderablejob lists, the Material setter `0x4F9DF0`, or `RenderSystemATG::SetVertexConstants`. The c32 camera function (`0x50EE60`) is excluded for c45 because it has no literal 45.
- c38: still 0 in all 6 captured frames. Its readers are `0x0E74E41D`, `0x9158278F`, `0x94C50138` and `0x81429E77`; the first is f001735 op 205 (`0x9158278F`/fp `0x04D81101`), right after the c45–c54 group. c57 (read by those same VPs) is non-zero but its lanes y–w look like garbage words. The c45 trace does not explain why c38 is missing.

## Garage lighting: engine-managed vertex globals traced (offline, 2026-10-24, no launch)

- VERIFIED (correction): the earlier literal-index scan used a short look-back window. Redone with backward r4 tracking over every call to the four upload helpers and their stubs (`generated/analysis/c38_regscan.py`, output `c38/regscan.txt`), it finds one more literal: c32 `vsEyePositionWS` is written by `li r4,32` at `0x50ECFC` → block upload at `0x50EE60` (count 1, value from camera+0xE0), in the same camera-setup function as c0/c12/c16/c20/c58/c55. This matches the run-085300 FIFO sample (c59, c32, c0..c3, c12..c15). Full literal set: 0,12,16,20,32–37,40–44,55,56,58,59,64. Still no 38, and none of 45–54 or 57.
- VERIFIED: the only other PPU builders of 0x1EFC headers are `0x734E10` (libgcm-style SetVertexProgram that uploads a program's embedded constants, used by post-process at `0x5C5914`) and the record-driven setters of `evo::renderer::Material` (vtable 0x1041478): `0x4F9B68` (block), `0x4F9DF0` (one vec4, value inline at record+0x30), `0x4FAE60` (matrix with transpose/inverse modes); register = record halfword +4 & 0xFFF. `Material::ApplySemantics` (`0x4FCAF8`) walks 20-byte records with a 23-way semantic switch (id = record+0x10 >> 27).
- VERIFIED: name binding is exact-string. `0x4F8920` → `0x514F58` compares the effect parameter's std::string name (88-byte entries) with strcmp and returns its type. The environment (`MotorstormEnvironment`, `0x4467D8`…) and shadow code (`0x6013C0`…) bind only unprefixed names (`envDirLightColour`, `ambientOcclusionGlobalScaler`, `shadowDistFadeMul`, …). No `vs*` global name appears in the EBOOT, so no `vs*` global is bound by name. `ambientOcclusionGlobalScaler` does not occur in any extracted rpk.
- VERIFIED: c38 and the working c45/c57 are identical in data. Every rpk occurrence of their hashes is a SHO table entry (c38 22×, c45 28×, c57 31×). No material-instance values exist, and their effect descriptors have the same shape (`C38`/`C45`/`C57`, flag 0, no semantic). Of the 27 SPU modules, only `renderablejob` builds 0x1EFC headers, and its register indices come from DMA'd lists, with no immediates.
- UNRESOLVED (stop condition): the producer of c45–c54/c57 is data-driven (renderablejob lists, Material value records, or `RenderSystemATG::SetVertexConstants` via vtable). It cannot be resolved statically, so whether that path carries register 38 is unknown. The earliest verified discrepancy is still "no c38 header reaches the FIFO" (run 085300). There is no reference to compare it against.
- Minimum runtime trace: one bounded run with only `RSX_TCONST_FIFO_WATCH=45` (existing knob, no code change). The header shape for c45 identifies the producer: count=5 singles mean renderablejob or `0x4F9DF0`; a 4-row block means `0x4FB3A0`/`0x4F9B68` or SetVertexConstants. The FIFO offset relative to the c32 upload shows whether it is in the PPU camera stream. Then trace that producer for register 38.

## Garage lighting: c38 is `vsAmbientVisibilityModifier` (offline, 2026-10-24, no launch)

- VERIFIED: VP `0x0E74E41D` is in `/env/Track0a_Garage_Sky1_driver.rpk` at 0x700862 (backend FNV hash over byte-swapped words, 28 instrs). Raw ucode instr 4 = `o[1].w = v3.w * c[38].x` (const field `(d1>>12)&0x3FF` = 38); instr 6 reads c35.
- VERIFIED: its `SHO` parameter table (12-byte entries: name hash, type, register) gives hash `0x8587F24B` float1 at reg 0x26. Name hash = `~crc32(name)`; resolved against rpk strings: c38 `vsAmbientVisibilityModifier`, c35 `vsFogLightIntensityLerp`, c33 `vsCoarseExposure`, c32 `vsEyePositionWS`, c56 `vsReciprocalFogRange`, c57 `vsShadowDistFadeMul`, c467 `tint`, c256 `vsModelToWorldMatrix`, c0/c4/c16 matrices; v3 = `colour_ambientVisibility`, v2 `normalMS`, v8 `texCoord`, v0 `posMS`. Effect descriptors (`global.rpk`, `track_garage.rpk`, vehicles) declare it as an engine global at fixed register `C38` with no semantic/material value.
- VERIFIED (EBOOT): the PPU constant-upload helpers are `0x735140` (1 vec4 from f1–f4), `0x7351E0` (1 vec4 from memory), `0x735270` (4 vec4), `0x735360` (block), all reached via TOC stubs; plus `RenderSystemATG` vtable slot 0xB0 (`0x50BAA0`). Literal register indices passed to them: 0,12,16,20,33,34,35,36,37,40–44,55,56,58,59,64. None is 38. No `li r4,38` reaches an upload. Neither the name nor its hash (any crc/case variant) occurs in the EBOOT.
- VERIFIED: c35 is written only by `ms2GameView` vtable slot 0x40 (`0x337300`, `0x33790C`/`0x337B94`) and is also 0 in all captured garage frames; c33 changes every frame (exposure runs).
- VERIFIED: SPU module `renderablejob` (EBOOT module table at 0x103D974: EA 0xFDF280, size 0xF6D0) builds 0x00141EFC single-vec4 constant headers (5 sites). c45–c51 (shadow-split globals) are set in the capture but have no PPU literal writer, so globals are also uploaded table-driven (renderablejob or the PPU per-parameter setter `0x4F9AC8`/`0x4FBD10`, register from the record).
- UNRESOLVED: whether any guest system supplies a value for `vsAmbientVisibilityModifier` to that table path. Static evidence cannot tell intentional 0 from missing initialization. Needed: (1) a reference capture (RPCS3 or hardware) of c38 in the garage for VP `0x0E74E41D`; or (2) a bounded run tracing the table-driven path (renderablejob/PPU setter) for register 38 and the source of c45–c51.
- Private scripts: `generated/analysis/c38scan.c`, `c38_psarc_grep.py`, `c38_vtclass.py`; extracts and lists under `generated/analysis/c38/`. No code change, no commit.

## Garage lighting: the guest never submits c38 (run `20261024-085300-garage-tcw`, 2026-10-24)

- One launch, exe `593265ac…` (SHA verified, ps3recomp-int `99a9b83`), `generated/introskip/tcw_cmd.txt`, log `generated/introskip/run_tcw.log`. `milestone_reached` (garage_capture_complete 01:26); no hard deadline, no watchdog stop, 0 retries, no leftover process.
- PROVEN: `[tcw] armed` (stderr line 370, before the intro opens) and 4 `sample` lines (subch 0, inc, LOAD 59/32/0/12, rx = applied) show the walker saw uploads; 0 `hit` lines, so no received FIFO header in the whole run addresses c38, on any subchannel or form. 0 `[vpc-watch]` lines, 0 resync lines.
- First c38-dependent draw: frame f001715 op 216, vp `0x0E74E41D` / fp `0x04D82F81`, c38 = (0,0,0,0) (69 such draws per captured frame). Neighbours c32–c34, c40–c41, c43, c45–c47 are set; c35–c39, c42, c44, c48 are not.
- Cause UNKNOWN. HYPOTHESES: c38 is meant to persist from an initialization skipped by `PS3_DEV_SKIP_INTRO=1`; or the PPU-side emitter skips it (parameter absent/unbound, or a condition on game state). Not assumed.
- Next, offline: find the PPU code that emits the per-draw constant headers for this vp (the c32/c33/c34/c40 uploads) and its parameter table; establish whether c38 is a named parameter, and what code path would write it.

## Garage lighting: FIFO-level c38 watch ready (2026-10-24, no launch)

- ps3recomp-int `99a9b83`: `RSX_TCONST_FIFO_WATCH=<slot>` in the `cellGcmSys.c` FIFO walker (helper `libs/video/rsx_tconst_watch.h`) logs received constant-upload headers (any subchannel, inc/NI) with words received vs routed to the 3D handler and whether the slot changed. `test_rsx_tconst_watch` 13/13 PASS; `test_rsx_transform_constants` PASS.
- Exe `build/motorstorm-int-tcw-593265ac/` SHA-256 `593265ace44c3e8a21fe390e444ac862e07d862aae9eec3378b0c91f18504372`; build log `generated/introskip/build_tcw.log`.
- Prepared run: `generated/introskip/tcw_cmd.txt` (intro skip, `--name garage-tcw`, both watches on c38). Not launched.
- Reading: `[tcw] armed` + `sample` lines prove receipt; no `hit` = no received FIFO header addresses c38; `hit ... applied=0` or `same` = received but lost or rewritten unchanged.

## Garage lighting: c38 upload path checked offline (2026-10-24, no launch)

- BLOCKED on evidence: the RSXI captures record per-draw constant banks only (`"unavailable": ["cmd_offset"]`), no FIFO words, so they cannot show whether the guest submits c38.
- VERIFIED (code): live walker `gcm` drain in `cellGcmSys.c` sends every subchannel-0/1 method word to `rsx_process_method` (incrementing `method+i*4`, NI same method); the 0x1F00 window gives slot = LOAD + reg/4, matching RPCS3's 32-register binding; the D3D12 backend copies all 512 constants per draw into `vp_c[]`, and the HLSL reads `vp_c[38].x`.
- VERIFIED (run 071154): no FIFO resync or bad-branch lines (the only path that skips words); subchannels 3/5 carry transfer methods only.
- Test: `test_rsx_transform_constants` extended (c38-spanning blocks, bit-exact, 32+16 split): 14/14 PASS. Commit ps3recomp-int `01b2a18`. No runtime change, exe unchanged.
- HYPOTHESIS: `PS3_DEV_SKIP_INTRO=1` skips guest work that may leave c38 set (constants persist across programs on hardware).
- Smallest next trace: in the walker, log every header whose method is 0x1EFC..0x1F7C on any subchannel (get offset, subch, inc/NI, count, current LOAD) when the block covers the `RSX_VPC_WATCH` slot.

## Garage lighting: c38 is never written (run `20261024-071154-garage-vpc`, 2026-10-24)

- Exe `build/motorstorm-int-vpcany-c70ba2bd/` (SHA-256 `c70ba2bd4032a33b4b15a602b49101384578f5c6cf94abdc150c3f50400cb5a1`), command `generated/introskip/vpc_cmd.txt`, log `generated/introskip/run_vpc.log`.
- Termination: `milestone_reached` (garage_capture_complete at 01:31); no hard deadline, no GPU watchdog, 0 retries.
- VERIFIED: with `RSX_VPC_WATCH=38 RSX_VPC_WATCH_ANY=1` armed from process start, zero `[vpc-watch]` lines: no lane of c38 is written by any `SET_TRANSFORM_CONSTANT` the backend processes during the whole run. `rsx_commands.c` is the only writer of `vertex_constants`.
- So col0.w = v3.w * c38.x = 0 and the ambient term of FP `0x04D82F81` is zero.
- HYPOTHESIS (next): either the guest never sends c38 (e.g. a parameter left at its default by a skipped path), or the FIFO carries it in a form the parser drops (a constant block longer than 32 dwords, a LOAD advance, or a jump/call segment). Next step, offline-first: trace `SET_TRANSFORM_CONSTANT_LOAD` and block lengths around the VP `0x0E74E41D` draws.

## Garage lighting: why the scene stays dark (offline, run `20261024-001141-garage-cmp`)

- VERIFIED: the final backbuffer shows the garage menu UI (button bar, panels) over a near-black scene.
- VERIFIED: fp `0x04D82F81` colour = direct + ambient. Direct = albedo x col0 x N.L x c40 (0.02, 0.01, 0) x (1 - fog) x shadow x c33.x (31.68): dim and red/green only. Ambient = albedo x col0 x lerp(tex15 env, 1, tc6.x) x col0.w; vp `0x0E74E41D` sets col0.w = v3.w (0.047) x c38.x.
- VERIFIED: c38 and c35 are zero in every draw of this vp. All other inputs it reads (c256-259 identity, c466, c467 = 1, c56, c57) are set. The w-lane watch saw no c38 write. HYPOTHESIS: c38.x is written to a lane the watch did not cover, set later (fade-in), or never sent because of an upstream fault.
- Op 527 snapshot (20x11 target) is uninitialised memory, not meaningful.
- Instrumentation: ps3recomp-int `RSX_VPC_WATCH_ANY=1` (all lanes), test_vpc_watch 0 failures, Win suite 102/102. Exe `build/motorstorm-int-vpcany-c70ba2bd/` (SHA-256 `c70ba2bd4032a33b4b15a602b49101384578f5c6cf94abdc150c3f50400cb5a1`); command `generated/introskip/vpc_cmd.txt`. Not yet run.

## Garage lighting: packed normals (run `20261023-234904-garage-shadow`)

- Run: exe `b98570d1` (ps3recomp-int `ec32fef`, includes shadow fix `c7bab5f`), `generated/introskip/shadow_cmd.txt`. It reached `garage_capture_complete` at 01:19 with a clean exit and no process left.
- VERIFIED: fp `0x04D82F81` draws feed attribute 2 (normal) as type 6 CMP, size 1, stride 28 (`[VTXTYPE] UNHANDLED type=6 attr=2`). DRAWWATCH-VB shows a2 = (-5.97e-15, 0, 0, 1), a packed word read as float32, so N·L = 0. a3 (colour) = (1, 1, 1, 0.047), so the colour is fine.
- VERIFIED: `RSX_VPC_WATCH=38` printed nothing; c38 is never written in the run (ambient is still multiplied by 0; HYPOTHESIS: by design or set elsewhere).
- Fix (ps3recomp-int `8aed096`): `rsx_fetch_attrib` decodes CMP through `rsx_vertex_decode_element`. `test_vertex_fetch_cmp.c`: 0 failures, 46 with the old fetch. Suites 102/102 Win and 99/102 WSL (the 3 inherited failures).
- Exe `build/motorstorm-int-cmp-8fe62998/`, SHA-256 `8fe6299876b426ed7a80cefd4ccc5981743b36deca9058d173c7147c91c80492`.
- Run `20261024-001141-garage-cmp` (this exe, same command, `generated/introskip/cmp_cmd.txt`): `garage_capture_complete` at 01:16, clean exit. VERIFIED: normals now unit length (a2 = (0.068, 0.718, -0.691)); no `[VTXTYPE]` line. Scene target `0x00750000` after op 513: RGB-nonzero pixels went from 48,773 (5.3%) to 99,426-115,597 (10.8-12.5%), but it is still very dark (mean RGB < 1.6/255; image x16 in `generated/introskip/geom/scene513_cmp_x16.png`). c38 is still never written. PARTIAL: geometry now shades, but faintly; ambient (x c38 = 0) and the small direct coefficients remain to be explained.
- Side observation (PARTIAL): some watched vertices have a0 ≈ (-7e-34, 9e-44, 0), probably padding or degenerate strip-restart entries; not investigated.

## Missing garage geometry: offline analysis of `20261023-231122-garage-depth` frame f001771 (2026-10-23, no launch)

- **VERIFIED (rasterized, not rejected):** scene ops 203–513 draw into `0x00750000` (MRT `0x01650000`, zeta `0x00ED0000`, depth LEQUAL with writes, cull BACK/CW). The sky ops 448–513 (fp `0x06FEE041`) are depth-tested after the geometry and show only in a horizon band, cut off where geometry sits in front, so the geometry wrote depth. In the op-513 snapshot RGB is non-zero on only 48,773 pixels (the sky band). `nonzero_fraction` is 0.1771 over all channels, which leaves about 50% of pixels with only alpha set. That matches the geometry programs, which export alpha = 1.
- **VERIFIED (failure mode):** the first depth-writing geometry draw is op 205 (fp `0x04D81101`, vs `0x9158278F`, indexed strip). The bulk geometry is ops 216–268 (fp `0x04D82F81`, vs `0x0E74E41D`). Every one of these draws writes RGB = 0. It is a shading failure, not geometry rejection.
- **PROVEN generic defect, fixed:** these programs light the scene with a depth-compare shadow lookup on unit 13 (shadow atlas `0x06FF0000`, drawn with depth LEQUAL, zfunc 6 = GEQUAL). The RSX evaluates `texel FUNC reference`; RPCS3's `VKDraw.cpp` passes `get_compare_func(tex.zfunc(), true)`. The decompiler's helper used `reference FUNC texel`, which inverts every shadow test.
  - Fix: ps3recomp-int `c7bab5f` (`rsx_fp_decompiler.c`).
  - Tests: `tools/test_fp_shadow_compare.py` passes on the new source and has 6 failures on the old. The shadow metadata (37/0) and engine (0 failures) C tests pass in WSL. The suite passes on Windows (102/102). WSL: 99/102, the same 3 inherited failures.
  - Exe: `build/motorstorm-int-shadow-c8156239/` (SHA-256 `c81562392fb43b1e77add8e24a7f4c78c24e8e9d79c120b1963dd4c3a88e6294`).
- **HYPOTHESIS (not proven):** the inverted shadow test may not explain all-zero RGB on its own. In fp `0x04D82F81` the ambient term is multiplied by col0.w = v3.w × c38.x, and c38 is zero in every scene draw (c35 too). The direct term needs shadow > 0 and non-zero vertex colour, albedo and N·L. The capture has no vertex-attribute formats or values, no texture contents and no shadow-map depth, so the remaining zero factor cannot be named.
- **Minimum instrumentation for the next run (not authorized):** `RSX_DRAW_WATCH_FP=0x04D82F81` (existing; dumps the VB, which currently shows only a0 and a8; extend it to a2/a3), `VTX_TYPEDBG=1` (logs unhandled vertex types, e.g. CMP = 6, which falls back to a float read), and `RSX_VPC_WATCH=38` (whether c38 is ever written).

## Depth-state validation run: `20261023-231122-garage-depth` (2026-10-23)

Exe `884f2629…` (ps3recomp-int `f77ef52`, `depth_cmd.txt`). Reached `garage_capture_complete` at 79 s. No fatal error, no watchdog stop, hard deadline not fired, 0 retries, thermal monitor off, no leftover processes. 6 frames captured, 47 pipelines (as before).

- **VERIFIED (fix works):** op 606 target `0x02206100` `nonzero_fraction` 0.0000 → 0.2321 (RGB is 0 because no source pixel exceeds the bright-pass threshold; the coverage is the alpha). It propagates through the blur chain: op 607 0.2277, op 612 `0x022B5D80` 0.2200. Backbuffer `nonzero_fraction` 0.1175 → 0.2824.
- **VERIFIED (composition):** op 613 now passes the scene through. Rows 250–520 of the backbuffer: mean 0.00 → 1.18, max 0 → 16. The menu UI looks unchanged (visual comparison, not a pixel diff).
- **PARTIAL (visual):** the scene is barely visible (max 16/255) and shows strong vertical streaking. Brightened ×12, it is the horizon/sky band of `0x01DD0000`, smeared vertically. The garage geometry is not recognizable.
- **Earliest remaining blocker (VERIFIED from snapshots):** the scene target itself (`0x00750000` → `0x01DD0000`, ops 203–522) holds only a thin sky/horizon strip, mean RGB ≈ 0.66 and max 46. The garage geometry is absent before composition. The secondary issue is op 613's vertical smear (suspect: unit 1 offsets from op 596's velocity target `0x01650000`), not yet traced.
- Images: `generated/introskip/view_depth/` (`depth_bb.png`, `raster_bb.png`, `depth_bb_x12.png`, `scene_01DD_x5.png`).

## Raster run and depth-state fix (2026-10-23)

Run `20261023-224835-garage-raster` (exe `ae6e1165…`, `raster_cmd.txt`): reached `garage_capture_complete` at 87 s. No fatal error and no watchdog stop. 6 frames captured.

- **REFUTED (cull hypothesis):**
  - Op 606's quad is a strip (0,0),(0,1),(1,0),(1,1); c466 = (2, 1, 0, 0.5), so clip xy = 2v − 1.
  - Under the replay's identity x/y and y-down viewport, both triangles are clockwise. That is front for cull key 1 (BACK, `front_face` 0x0900 = CW), so the quad is not culled.
  - Op 596 has the same raster state (`cull_face` 0x0405, `front_face` 0x0900, vp_scale y < 0), the same clip mapping, and it draws.
- **VERIFIED (root cause, offline):**
  - Every guest-FP pipeline tested depth LESS_EQUAL and wrote depth, whatever the guest's depth test state.
  - Op 605 (vs `0x36961B70`, z = c467.x = −1 → depth 0) and op 606 (z = c466.z = 0 → depth 0.5) share `0x02206100` with no rebind between them, so the shared DSV is not cleared.
  - Op 605 writes depth 0, and op 606 fails LESS_EQUAL everywhere. Both have the guest depth test off.
  - `tools/test_d3d12_depth_state.py` replays this. The old fill gives (draws 1, 0); the fixed fill gives (1, 1).
- **Fix:** ps3recomp-int `f77ef52`. With the guest depth test off, the pipeline does no depth test and no write. The test enable is in the pipeline key; depth-on draws are unchanged.
  - Exe: `build/motorstorm-int-depth-884f2629/`, SHA256 `884f2629bce8cb97c4e7ef464684e51fbac6a4035fa071bf84294241ffd0d716`.
  - Suites: Windows 101/101; WSL 98/101 (the 3 inherited failures). Audit: 25 inherited findings.
- **UNVERIFIED in game:** whether the garage scene now reaches the backbuffer. Run plan: `NEXT_PRESENTATION_VALIDATION.md` (`depth_cmd.txt`).

## Garage composition traced offline (2026-10-23)

Sources: the selfsample run's RSXI frames (6 frames; op 606 also in the 3 earlier runs, 15 frames in total).

- **VERIFIED (chain):**
  - The scene is drawn into `0x00750000` (2×AA, fmt 0x3148) at ops 203–522.
  - Op 602 (`fp 0x0074B441`) resolves it into `0x01DD0000`. The content is identical: dark horizon band, max RGB 46.
  - Op 604 downsamples that into `0x022D0000`.
  - Op 613 (`fp 0x02193941`) composites into the backbuffer: unit 2 `0x01DD0000`, unit 4 `0x022D0000`, unit 5 `0x079D0000`, unit 6 `0x022B5D80`, …
  - Op 613 multiplies its result by `tex6.w` (`h0.xyz *= h2.w`).
  - Op 596 is a depth-derived pass into `0x01650000`. Op 613 reads it only as distortion offsets on unit 1, so it is not the scene source.
- **VERIFIED (first failing pass): op 606 (`fp 0x0074C341`, vs `0x7BFB2384`) on `0x02206100`** (320×180 FP16, blend RGB ONE+ONE, alpha = source, cmask 0xF).
  - Its shader writes alpha = 1 − sat(|tc0.zw| − 0.2)², which is 1 at the quad centre for any finite constants.
  - Yet the target is all zero, alpha included (`nonzero_fraction` 0.0000 over every byte, all 15 frames).
  - The blur chain (ops 607–612) carries that zero alpha into `0x022B5D80`, so op 613 blacks out the scene. The UI is drawn after op 613 and survives.
  - Op 606 is the only draw in the bloom chain with face culling on (key 1: BACK, CW).
- **HYPOTHESIS (cause):** the quad is culled. The replay passes guest clip x/y through unscaled and ignores the viewport scale sign, which decides window-space winding on RSX.
- **BLOCKED (evidence missing):** the capture lacks c466/c467 (`RSXI_VP_CONSTS=64` stops at index 89), the quad vertices, the viewport scale/offset and the raw cull/front-face registers.
  - ps3recomp-int `8e3077d` records the last two per draw (capture only).
  - Run plan: `NEXT_PRESENTATION_VALIDATION.md`.

## Selfsample validation run (2026-10-23)

Run `generated/runs/20261023-222443-garage-selfsample` (exe `bd9d4e8e…c8e9`, ps3recomp-int `1803596`), one authorized launch.

- VERIFIED: stopped at `garage_capture_complete` (78.2 s). No fatal error, GPU-watchdog stop or D3D12 error.
- VERIFIED: the self-sampling warning (previously ×4) and `pool full` (previously ×8) are both gone. Exactly 3 depth surfaces were created: `0x06FF0000` 1024×2048, `0x00ED0000` 1280×720 and `0x078E0000` 640×360.
- PARTIAL: the scene RT `0x00750000` (op 513) looks the same as in the zeta run (a dark horizon band, about 3.5 % non-black), so there is no visible shadow or garage change. The shadow-map depth itself is not snapshotted; snap00 is the colour target, which is all black because the pass writes no colour.
- VERIFIED: the presented backbuffer is now captured (snap30). It shows the garage UI overlay (button bar, panels) over black. The 3D scene does not reach the presented frame.
- Still open: op 596 depth-as-colour (2×AA layout) is still noise.

## Shadow pass keeps its depth surface (offline, 2026-10-23)

No launch. ps3recomp-int `95c210e` + `1803596`, exe `build/motorstorm-int-selfsample-bd9d4e8e/` (SHA256 `bd9d4e8edc6e786aa6d720b6ddf28d41ec105abb8ef5ca7f9fcd1eedda11c8e9`).

- **Self-sampling:** only units the fragment program fetches count (`rsx_fp_texture_units`). Unit 13, left bound by the shadow pass, no longer sends its depth to the shared buffer.
- **Pool:** only ops that test, write or clear depth/stencil allocate a surface. The captured frames name 21 zeta addresses but use 3, so the size stays 8.
- **Tests:** Windows 100/100; WSL 97/100 (3 inherited c++ failures).
- **Run:** prepared in `generated/introskip/selfsample_cmd.txt`.

## Garage run with zeta surfaces: `20261023-220434-garage-zeta` (2026-10-23)

One launch, exe `d5cb0c28…` (`10e9233`). Stopped at 79.8 s on `garage_capture_complete`. No fatal error, no watchdog, no D3D12 errors. 1887/1887 Presents OK. 6 frames captured; no leftover process.

- **VERIFIED:**
  - Zeta surfaces were created, but the 8-slot pool fills with the bloom-chain zetas (`depth surface pool full` ×9).
  - Unit 13 binds as `zeta` (`0x06FF0000`, compare 6), and 4 scene FPs compile with a depth-compare key.
  - Op 596 gets `zeta_as_color` (`0x00ED0000` converted).
  - The scene RT `0x00750000` changed from white silhouettes to dim shaded geometry with the same 17.7 % coverage. It is still not a recognisable garage.
- **First blocker (VERIFIED):**
  - Ops 1–198 write the shadow map's depth (zeta `0x06FF0000`, depth test and write on, `cmask` 0).
  - Unit 13 still holds `0x06FF0000` from the earlier frame, but FP `0x047A6B41` never samples it.
  - The "samples its own zeta" check ignores the FP's used units, so the shadow depth goes to the shared buffer. The `0x06FF0000` surface stays cleared, so the shadow test reads a constant.
- **Not answered:**
  - The presented backbuffer was not snapshotted (the 32-snapshot cap).
  - Whether op 596's output is correct: the 2×AA byte layout is still unknown.
  - X16 `.w`.
  - Cube faces.

## Garage scene: depth surfaces per zeta, depth textures with compare, X16, cube declarations (offline, 2026-10-23)

No launch. ps3recomp-int `10e9233`, exe `build/motorstorm-int-zeta-d5cb0c28/` (SHA256 `d5cb0c284ac95e9ee269007f5369e5d1cd9427a6269ce9beeb9853b9b6719bdb`). Evidence: RSXI frame 1769 of `20261023-212901-garage-rtpool`.

- **Fixed (generic):**
  - **Per-zeta depth surfaces:** each zeta address gets its own D24S8 surface, kept across switches (`RSX_ZETA_POOL=0` = old shared buffer). The shared buffer had been cleared on every switch, so the shadow map's depth could never be read.
  - **Depth textures:** DEPTH24_D8/16 textures at a zeta address bind its depth view. ADDRESS-zfunc units compile with the shared compare helper (`rsx_fp_decompile_shadow_ex`).
  - **Depth read as colour:** an A8R8G8B8 read of a zeta written last gets its depth bytes (op 596).
  - **X16 uploads.**
  - **Cube units declared `TextureCube`:** the D3D12 text rewrite was dead with the current emitter. The scene's cube units 14/15 were bound behind `Texture2D`.
- **VERIFIED offline:**
  - build OK;
  - Windows suite 100/100; WSL 97/100 (the 3 inherited failures);
  - audit: the 25 inherited findings, none in the changed files;
  - `test_d3d12_zeta_pool` passes, including a C harness under WSL: no-compare output is byte-identical, TXP calls the compare helper;
  - D3DCompile accepts the shadow+cube HLSL and the conversion shaders.
- **HYPOTHESIS (unverified until a run):**
  - that the shadow compare and cube fixes remove the white silhouettes;
  - the X16 channel presentation: the scene reads unit 11 `.w`, and under the shared remap an identity crossbar gives 1;
  - the 2×AA layout.

## Run `20261023-212901-garage-rtpool`: the bloom chain now has its own targets; the scene's shadow map and a 256×1 lookup are unbound (2026-10-23)

One authorized run. ps3recomp-int `f0b82c1`, exe `404b436d…`, command `generated/introskip/rtpool_cmd.txt`. Target `garage_capture_complete` reached at 78 s (85 s wall time). No fatal error, no GPU watchdog, no hard-deadline kill, no retry, no leftover process. Cache snapshot `generated/cache-snapshots/20261023-212901`. RSXI frames 1739 (the overflow frame, not presented), then 1769–1889 (all `ok=1`). Previews are in `generated/introskip/view_rtpool/`.

- **VERIFIED (fixes):**
  - the pool holds 26 surfaces in frame 1769 (limit 32);
  - no `render-target pool full` or `offscreen … unresolved` lines;
  - ops 605–612 (`0x02206100` → `0x02292B00` → `0x022B5D80`) write their own targets, not the backbuffer;
  - `0x022B5D80` binds `rt_exact` (620 draws), and `0x0077B300` binds `upload` (619 draws);
  - `0x0077B300`'s checksum `0xE3F037CC` is not the checksum of all-zero data, so the texture is nonzero;
  - per-draw descriptor bases are distinct;
  - 1,890 Present attempts, all `S_OK`.
- **VERIFIED (no visible change):**
  - the backbuffer is still the UI over black;
  - `0x00750000` still shows white silhouettes.
- **VERIFIED (bloom zero is legitimate):** `0x022B5D80` is all zero. Op 605 clears `0x02206100` to 0. Op 606 is a bright pass, `max(c·1.43−7.15, 0)`, over `0x02195900`, which is nonzero only at small values (12.8 % of pixels nonzero). Earlier notes called `0x022B5D80` an exposure input; it is the bloom result. The scene shaders do not sample it: their fp code has no unit 6.
- **VERIFIED (first remaining defect):** the scene programs (e.g. `0x067F5981`, `0x06FEE041`, ops 203–513) sample unit 13 projectively, which is the shadow lookup, and unit 11. Neither unit is bound:
  - `[tex] unsupported format 0xB0 (unit 13, 0x06FF0000 1024x2048)`: DEPTH24_D8. This is the shadow map rendered depth-only at ops 1–200, `cmask 0`.
  - `[tex] unsupported format 0xB4 (unit 11, 0x0077B080 256x1)`: X16.
  - Both sample null (0).
  - Unit 10 (`0x0077B300`) supplies the per-cascade scale/offset for the unit-13 coordinates.
- **VERIFIED (second defect, same class):** op 596 (fp `0x0074CE81`) samples the scene zeta `0x00ED0000` (A5, 2558×719, i.e. 2×AA) as a colour texture. The backend's colour RT for that address is `written_this_frame=false`, and `0x01650000` comes out as stripes.
- **Not known:**
  - whether the shadow map plus the X16 lookup alone explain the white silhouettes;
  - the 2×AA layout.

## Garage scene: RT pool exhaustion, SRV heap overlap and 0x9A textures fixed offline (2026-10-23)

No launch. ps3recomp-int `f0b82c1`, exe `build/motorstorm-int-rtpool-404b436d/` (SHA256 `404b436d0cd6e23e88b1e3fae1ab62aa765e285d14d8f309c00273e48644e553`). Evidence: RSXI frame 1759 of `20261023-205211-garage-display-draws`.

- **VERIFIED:**
  - **Pool exhaustion:** the garage frame binds 23 distinct offscreen surfaces; the pool held 16. The exposure/bloom chain (`0x06A8F400` → `0x02206100` → `0x02292B00` → `0x022B5D80`) got no target. Those ops replayed into the **backbuffer** (`want = -1` means display).
  - **Null exposure inputs:** 620 draws sampled `0x022B5D80` as a null SRV. 619 draws also sampled `0x0077B300` (4×1, `0xBA` = W16Z16Y16X16_FLOAT) as null, because the per-draw SRV fill's format list lacked 0x9A, although the bind recorded it.
  - **Descriptor overlap:** VP texture slots 31..52 overwrote the SRV windows of ops 0–1 (op 1's units 0–3).
- **Fix (generic):**
  - pool 32;
  - an unresolved surface's ops are skipped and reported;
  - derived, disjoint SRV heap regions;
  - 64-bit RSXI masks;
  - one format predicate for bind and fill, with the view using the uploaded resource's format.
- **Not known:** who writes `0x0077B300`. No transfer in the trace touched it.
- **Tests:** Windows 99/99, WSL 96/99 (the 3 inherited failures), audit 25 inherited. New test: `test_rt_pool_srv_layout`; it fails on the old source.

## Run `20261023-205211-garage-display-draws`: garage frames present again; the UI is visible, the 3D scene is not correct (2026-10-23)

One authorized run. ps3recomp-int `9ac4936`, exe `85a80a62…`, command `generated/introskip/display_draws_cmd.txt`. Target `garage_capture_complete` reached at 88.5 s. No fatal error, no GPU watchdog, no hard-deadline kill, no retry, no leftover process. Cache snapshot `generated/cache-snapshots/20261023-205210`.

- **VERIFIED (vertex buffer):**
  - one overflow, at guest flip 1641: 100 draws dropped, 21 of them on a display buffer, all `vertex_buffer_full`, plus 1 truncated draw (339 vertices);
  - the buffer grew once, 393,216 → 589,824 vertices (`ok=1`), which implies a demand of roughly 420k–472k;
  - after that, `callbacks.dropped` stayed at 100 for the rest of the run (114,709 recorded). No other reason appeared.
- **VERIFIED (presentation):**
  - only the overflow frame (flip 1642) was replayed without a Present (`replayed_no_present` 1 → 2);
  - from then on every guest flip presented: 1,878 attempts, 1,878 `S_OK`, last presented flip 1792 = last guest flip;
  - the gate stayed in BOOT.
- **Captures:** 6 frames. 1729 (flip 1642) is `offscreen_replay`; 1759–1879 (flips 1672–1792) are `host_present`, 619 draws each, Present `S_OK`.
- **Image (VERIFIED by inspection, private):** the presented backbuffer shows original garage UI:
  - the button-prompt bar (✕ ○ □ △);
  - a header banner;
  - a ◀▶ selector tag.
  The scene area behind it is black. `0x00750000` holds white/black geometry silhouettes, and `0x06AC7800` and `0x01650000` contain banded or striped garbage. The 3D garage is **not** correctly rendered.
- **HYPOTHESIS:** the scene corruption comes from the unmodelled 2×AA surface layout and its resolve or sampling path, or from texture sources (`null_srv`, `none`). Not yet isolated.

## Garage display draws: root cause found and fixed offline; vertex-program upload buffer now grows (2026-10-23)

No launch. ps3recomp-int `9ac4936`, exe `build/motorstorm-int-vpvb-85a80a62/` (SHA256 `85a80a62ffdc553913deeba23de6a35573498f3d6c113ad8e0f2c65726f5faf4`). Details: `RSX_DRAW_REJECTION_AUDIT.md`.

- **VERIFIED (root cause, from the last run's RSXI frames and the source):**
  - the per-frame vertex-program upload buffer held 393,216 expanded vertices per parity;
  - garage frames ask ≈393,600. In frame 1830, op 552 (a 256-index strip) kept 318 of 762 vertices and ended exactly at 393,216;
  - every later draw got `maxv = 0`, and the draw body returned without a record or an error;
  - the display pass comes last, so it was lost (`has_display = 0`, no Present).
- **Fix (generic):**
  - the buffer grows after the GPU wait at the start of `render_frame` (`vp_vb_budget.h`): demand + 25 %, 64K-vertex granule, ceiling 1,048,576;
  - already-uploaded vertices are copied to the new buffer;
  - a growth failure keeps the old buffer and is reported.
  - The first overflowing frame still loses its tail.
- **Accounting:** each draw early return now has one reason. `[draw_acct]` adds `reasons=`, `truncated=`, `vb_grows=` and bounded per-reason and display lines (flip, primitive, count, RT, FP, VP size). It is off by default.
- **FP cache:** no defect. Pipelines key on the code hash, and constants are re-read per draw. MSAA is not involved and remains unmodelled.
- **Tests:**
  - Windows 98/98;
  - WSL 95/98 (3 inherited `c++` link failures);
  - private 7/11 (inherited LFQueue tests);
  - audit: 25 inherited findings, none in the changed files.
  - New: `test_draw_rejection`.
- **Next:** the run in `NEXT_PRESENTATION_VALIDATION.md` (needs authorization).

## Run `20261023-200314-garage-display-path`: the garage's display draws reach the backend and are dropped (2026-10-23)

One authorized run. ps3recomp-int `50b3e2c`, exe `089a684e…`, command from `NEXT_PRESENTATION_VALIDATION.md`. Stopped at the target `garage_capture_complete` at 75 s. No fatal error, no GPU watchdog, no hard-deadline kill, no retry, no leftover process. Cache snapshotted (`generated/cache-snapshots/20261023-200314`).

- **VERIFIED (draw accounting, `[draw_acct]`):**
  - after the handoff (≈47 s), draw callbacks targeting the display buffers are **dropped** by the D3D12 draw bodies: `dropped_display` went 0 → 3108 by the end. The first 8 events (`rt=0x00010000`) were 1 triangle fan of 4 vertices, followed by triangle draws of 6, 256, 256, 256, 256, 104 and 6 vertices; the last drops alternate `0x00010000`/`0x00394000`;
  - `callbacks.dropped` was 0 for the whole loading screen and 12,405 at the end. 3,108 of the drops target a display buffer;
  - `groups.inline_array=0`, `groups.immediate=0`, `groups.empty=0`, `unrecorded_display_groups=0`: the guest uses ordinary DRAW_ARRAYS/DRAW_INDEX_ARRAY. Unsupported vertex paths are ruled out for this run;
  - there was no batch overflow: `[d3d12] batch full` never appeared and `dropped=0` in `[present_diag]`.
- **VERIFIED (presentation, `[present_diag]`):**
  - the last Present was at guest flip 1639;
  - by flip 1796, `replayed_no_present=157`, while `present_attempts` and `present_success` stayed at 1739, all `S_OK`;
  - the gate stayed in BOOT the whole run.
- **VERIFIED (capture):** 6 complete frames (1740, 1770, 1800, 1830, 1860, 1890):
  - all with `event=no_present`, `category=offscreen_replay` and `present attempted=0`;
  - each holds 553–554 records and 29–31 snapshots.
  - Frame 1830:
    - `0x022C0500` and `0x022C1600` (1280×720) and `0x0243AB00` (640×360) hold data;
    - `0x00750000` is about 5 % non-zero;
    - `0x01650000`, the luminance chain and the backbuffer are all zero.
- **VERIFIED (transfers, `[xfer]`, 3000-line budget spent):**
  - only subchannel 3 (NV3062: format `0xB`, pitch `0x1000`, DMA `0xFEED0000`) and subchannel 5 (NV308A: 1×4 inline words) are used;
  - destinations are local offsets such as `0x02537E80`, `0x0074xxxx` and `0x02193940`, which are in-place fragment-program patches. None is a display buffer;
  - nothing on subchannel 1 (no NV0039) or 6 (no NV3089 blit; `[NV3089G]` 0 lines).
- **VERIFIED (`[dispmem]`):** the display buffers in guest memory were all zero at flips 1640/1641 and never changed afterwards.
- **Next (offline):** find which early return in `d3d12_draw_arrays_body`/`d3d12_draw_indexed_body` drops these draws. The candidates, all **HYPOTHESIS**:
  - `upload_*_vp*` returning 0 (vertex/index fetch);
  - `pipeline_ready`/`vb_mapped`;
  - the `vp_ucode_bytes < 16` fallback.
  
  The fix must be a generic correction to that path. Do not force a Present.

## Garage display path analysed offline; display-path instrumentation and gate-independent capture added (2026-10-23)

No launch. ps3recomp-int `50b3e2c`. Exe `build/motorstorm-int-xfer-089a684e/` (SHA256 `089a684e…`), not run. Details: `RSX_GARAGE_DISPLAY_PATH.md`, `RSX_TRANSFER_ENGINE_AUDIT.md`.

- **VERIFIED:**
  - the display buffers (`0x10000`, `0x394000`, 1280×720, pitch 5120) are registered once and never change;
  - the loading screen draws straight into them;
  - no recorded garage draw does. The garage's last full-resolution image is a **2×AA surface** (`0x01650000`, format `0x3148`, pitch 10240) that no recorded op resolves;
  - every garage batch ends with a clear of `0x06A57000` and no draw, and texture unit 2 is rebound to `0x01DD0000` before the next batch, so commands run after the last recorded op;
  - no recorded garage draw reads `0x01DD0000`. The two programs that bind it do not sample unit 2;
  - the D3D12 feed has no `INLINE_ARRAY` or immediate-vertex draw path, and the backend drops some draws without counting them;
  - the game's libgcm NV0039 and NV3089 builders have no direct caller.
- **HYPOTHESIS (most likely):** the garage's final resolve/composite into the display buffer is issued after the last recorded op and never recorded.
- **Not the cause:**
  - the present gate staying in BOOT. That is expected with the intro skipped; the Present is withheld because no recorded draw targets the display;
  - the screen-copy stand-in.
- **Transfer engines:**
  - NV3089 copies in guest memory only;
  - NV0039 is not implemented, and subchannel 1, where libgcm binds it, is executed as 3D (latent);
  - NV308A and NV3062 are correct for their use here.
- **Added (`50b3e2c`, all off by default):**
  - `PS3_DRAW_ACCT_MS`: undrawn BEGIN/END groups and dropped draw callbacks, by target surface;
  - a latched trigger gate (`NV3089_GATE` no longer samples 1 blit in 64);
  - `PS3_XFER_TRACE`: every method on subchannels 1–6;
  - `PS3_DISPMEM_PROBE`: guest display-buffer contents at each flip;
  - `RSXI_EVENT=no_present`/`present`: capture without a gate FLIP; frames labelled `offscreen_replay` or `host_present`.
- **No backend behaviour changed:** the root cause is not yet demonstrated, so no fix was made.
- **Tests:**

  | Suite | Result |
  |---|---|
  | Windows | 97/97 |
  | WSL | 94/97; the same 3 inherited failures |
  | Private | 7/11; the same 4 LFQueue scripts, which need logs |
  | Audit | only the 25 inherited findings |
- **Next run:** prepared in `NEXT_PRESENTATION_VALIDATION.md` and waiting for authorization.

## Run `20261023-190803-garage-present`: garage frames replayed but never presented (2026-10-23)

Authorized single run. ps3recomp-int `9bad862`, exe `346f4e9e…` (verified), intro skip, native audio, cache snapshot `generated/cache-snapshots/20261023-190803`, thermal off. Stopped by the 12 s no-present stall line, about 60 s in; 0 processes left.

- **VERIFIED:**
  - all 1,757 Present attempts succeeded (HRESULT 0), with no failures or occlusions; the last one was at guest flip 1650, about 48 s in, right after `loadscreen_renderer_exited` (47 s);
  - after that, guest flips (+66) and replays continued. `replayed_no_present` went from 2 to 67 with `present_attempts` flat: garage batches (554 records) were replayed and the GPU completed them (`fence_completed` rising), but no Present followed;
  - no Present failure caused this.
- **The gate never left BOOT** (`gate.flip=0`, `gate.clear=0` for the whole run):
  - no `event=flip_mode_present` line;
  - the RSXI "main" phase, keyed to the first gate FLIP replay, never started. Only the pre frame 1595 was captured (loading screen, presented OK), and the manifest stays `capturing`. **No garage frame was captured.**
- **No `[NV3089G]` line:**
  - no traced 2D blit after the trigger;
  - caveat: the gate file is polled every 64 blits, so fewer than 64 blits after the trigger would go unseen;
  - six `[GCM2D] inline write` lines (to `0x0074B180`, tiny) only.
- **`0x01DD0000`:** `[TEXLOC] LOCAL nz=0 MAIN nz=0`, so the guest memory is empty when sampled. The screen-copy fallback is bound there (`fp 0x47A6B41`, `0x2193941`, `0x2537E81`, `0x2538DC1`, `0x4D7D301`).
- **Also empty in guest memory:** MRT `0x01650000`, consistent with GPU-only render targets.
- **Shaders and errors:** 35 `pso_ready`, 0 compile or PSO failures, no D3D12 errors logged, no GPU watchdog. `0xB0`/`0xB4` are refused once each, as before.
- **The garage is NOT shown to be visible.**

## Presentation stages instrumented; garage frames were not presented in the last capture (offline, 2026-10-23)

No launch. ps3recomp-int `9bad862`. Exe `build/motorstorm-int-diag-346f4e9e/` (SHA256 `346f4e9e…`), not run.

- **What the last run proved (VERIFIED):** the batch was replayed after the handoff (frame counter 1744 → 1763).
- **What it did not prove:** that anything was presented. A replay with no display-targeted draw runs without a Present.
- **Earlier garage capture (VERIFIED for exe `7770ec7a…`):** run `20261022-064218` recorded `"present":0` for all its garage frames. Each had 554 records, none targeting a display buffer, and the backbuffer was all zero.
- **Garage passes:** a shadow pass into 1024×2048; the scene into MRT `0x00750000`/`0x01650000`; a down-sample chain; final passes into `0x01650000`. How the image reaches display buffer `0x10000`/`0x394000` is UNKNOWN (HYPOTHESIS: an NV3089 2D blit, which the D3D12 path performs as a guest-memory copy).
- **Added (`9bad862`):**
  - `PS3_PRESENT_DIAG_MS`: flips, gate decisions, replays (and replays without Present), Present attempts, successes and failures with HRESULTs, the fence;
  - `RSXI_EVENT=flip_mode`: a pre frame, then main frames from the handoff, each finalized only after its Present returned;
  - `NV3089_GATE_MAX`;
  - the runner `{run_dir}` placeholder.
- **Why the last capture was empty (VERIFIED):** the cube `pso_ready` stop line killed the process mid-frame. That stop is removed from the proposed run.
- **Texture formats:** `0xB0` = DEPTH24_D8 linear (the shadow map), `0xB4` = X16 linear (a 256×1 LUT). Both are still refused, and no conversion was guessed.
- **Tests:**

  | Suite | Result |
  |---|---|
  | Windows | 96/96 |
  | WSL | 93/96 (the 3 inherited failures) |
  | Private | 7/11 (the 4 inherited LFQueue failures) |
  | Audit | the 25 inherited findings |

- **Docs:** `RSX_PRESENTATION_VALIDATION.md`, `GARAGE_FRAME_CAPTURE.md`, `GARAGE_RENDER_PIPELINE.md`, `NEXT_PRESENTATION_VALIDATION.md`.
- **Garage rendering is NOT complete:** no presented garage image exists.

## Presentation-gate validation run (2026-10-23, `generated/runs/20261023-180259-present-gate`)

One authorized run, exe `a757cb88…` (ps3recomp-int `25cbff4`). Stopped by its stop line at 49.4 s: the first cube-map fragment program (`fp=0x04D81101`, cube mask `0x8000`) reached `pso_ready`. No retry. Cache snapshot `generated/cache-snapshots/20261023-180259`, hashes match the pre-run state.

- **Replay after the renderer exit (VERIFIED):** the backend frame counter went from 1744 to 1763 after `AsyncRenderThread` exited, where the previous run stayed frozen. The next renderer's programs were translated at replay: 7 cube-map programs plus MRT (`nrt=2`) programs, all `pso_ready`, none failed.
- **Presents after the exit (UNVERIFIED):** the run ended about 2 s after the exit, so no heartbeat or `[vstat]` sample landed after it. There was no stall report either, but one needs 3 s.
- **Dropped draws:** none; no `batch full` line.
- **Capture:** RSXI triggered at frame 1763 but the run was stopped before that frame ended, so no image was saved. Garage visibility and the white/black screen remain unverified.
- **`c[59].w` (VERIFIED):** the fade runs 3 times, each starting at 0.985 and falling 0.0152 per change (≈ 0.5/s), never clamped at 0:
  - boot, about 3–10 s: falls to −2.92, then holds;
  - about 13.4 s: written to 0;
  - the loading screen, from frame 1238 (≈ 31.3 s): still falling at −2.40 when the 512-line cap was reached (≈ 37 s).
- **Errors:** no GPU, device or shader errors. The two `[tex] unsupported format 0xB0/0xB4` lines also occurred in the previous run.

## Presentation gate fixed: guest flips present again after display colour clears stop (offline, 2026-10-23)

No launch. ps3recomp-int `25cbff4`; exe `build/motorstorm-int-gate-a757cb88/` (SHA256 `a757cb88…`), not run.

- **Defect (VERIFIED, run `20261023-172442-present-stall`):**
  - After the first present at a display colour clear, `rsx_d3d12_backend_present` dropped every later flip, permanently.
  - MotorStorm's next renderer clears only depth/stencil: 40 flips were swallowed and the batch grew toward `MAX_DRAWS`, after which records are dropped silently.
- **Fix:**
  - `include/ps3emu/present_gate.h`: after 2 flips with no display colour clear, the flip presents again. A display colour clear re-arms clear mode. No duplicate presents.
  - Draw records dropped from a full batch are now counted and reported. `MAX_DRAWS` is unchanged.
  - Titles that colour-clear every frame are unchanged; the harness compares old and new policy.
  - Details: `RSX_PRESENTATION_GATE_FIX.md`.
- **Fade (`LOADING_SCREEN_FADE_TRACE.md`):**
  - `c[59].w` falls at 0.5 per second of host time: a 2 s fade-in from black that starts at the loading-screen page load and does not stop at 0 (INFERRED).
  - Presentation suppression is not the cause: the ramp runs while presents are steady.
  - The guest writer is not identified offline.
  - New opt-in `RSX_VPC_WATCH=59` records the value timeline. No clamp or timing change was made.
- **Tests:**

  | Suite | Result |
  |---|---|
  | ps3recomp-int, Windows | 95/95 (harnesses need a compiler) |
  | ps3recomp-int, WSL | 92/95; the 3 inherited failures |
  | New `test_present_gate` | 9 source + 19 harness checks |
  | New `test_vpc_watch` | 4 source + 6 harness checks |
  | Private | pass; the 4 LFQueue scripts need logs, as before; `render_milestones` passes on the render and gate configs |
  | Audit | the 25 inherited findings only |
- **Next run:** `NEXT_PRESENTATION_VALIDATION.md` (needs authorization).

## Present-stall diagnostic run: the runtime swallows guest flips; the guest drives the gain (2026-10-23)

Run `generated/runs/20261023-172442-present-stall/` (exe `be870473…`, ps3recomp-int `c874771`, `NEXT_RENDER_DIAGNOSTIC_RUN.md` as written, live 672 MB cache kept, snapshot `generated/cache-snapshots/20261023-172441`). Stopped by the stop line `[present-progress] no present for 6000 ms` at 52.2 s; no retry, thermal off, no leftover process.

- **VERIFIED (stall = case C):** `AsyncRenderThread` tid 28 exits (`0xBABE`, stderr 5655) right after the last heartbeat (`ms=45125 frames=1716`). In the 6 s that follow, `flips=+40 drain_moves=+41 ticker_calls=+40 replays=0 presents=0 gate.clear_mode=+40`, other gates 0, `batch=985/2048` (721 at 3 s). The guest keeps flipping and submitting draws; `rsx_d3d12_backend_present` drops every flip because clear-driven mode is latched, and no display colour clear (the only remaining present trigger) arrives (clears seen: masks `0x3`, `0x2`). No draw was dropped yet; at this rate the 2048 limit is hit after roughly 12 s more (~88 records/s). Not a GPU deadlock. Fix candidate: the frame-boundary policy in `rsx_d3d12_backend_present`/`d3d12_clear` (not changed; needs its own authorization).
- **VERIFIED (gain source):** both loading-screen vertex programs (`vp_FF398E97`, `vp_F69565E0`; 5 instructions, no branch, start slot 0) pass `c[59]` straight to TEXCOORD1. The fragment program computes `rgb = X + w·(tc1.rgb − X)` with `tc1.rgb = 0`, `w = c[59].w`, i.e. gain `1 − w`. Captured `c[59] = (0,0,0,w)` with w = −0.5611 / −0.7129 / −0.8652 at frames 1340/1350/1360: predicted gains 1.0971 and 1.1942; measured 1.0972 and 1.1949. The guest writes a negative, decreasing fade weight; the D3D12 translation is faithful. Why the guest's fade parameter runs negative is UNKNOWN (HYPOTHESIS: a fade timer running past its range during the long load, or a wrong host time input). The VP branch-base fix does not apply to these programs and did not change the brightening.
- **VERIFIED (blend words):** `[BLEND] enable=1 sfactor=0x03050302 dfactor=0x00010303` (equation not set), i.e. the decoded straight-alpha state.
- **Cache:** the game/FIOS rebuilt `cache.dat` (672 MB → 59.8 MB). Garage milestones and the stall time match the previous run (world read complete 34.2 s vs 34.3 s; stall ~46 s); the larger cache did not change progression.
- No shader failure (13 `pso_ready`), no cube-map program, no GPU error, no fatal line.

## Loading-screen gain is pre-store, not accumulation; presents stop when AsyncRenderThread exits (offline, 2026-10-23)

No launch. Run `20261023-150148-garage-render` re-analysed. ps3recomp-int `c874771`, exe `be870473…` (not run).

- **VERIFIED (blend):** `0x0122418B` is the D3D12 key for straight alpha (colour `SRC_ALPHA`/`INV_SRC_ALPHA`/`ADD`; alpha `INV_DEST_ALPHA`/`ONE`/`ADD`; all channels written). The translation matches the RSX methods `0x310`–`0x320` (12 harness checks). No blend defect. (`RSX_BLEND_STATE_INVESTIGATION.md`)
- **VERIFIED (gain):**
  - frames 1361/1371/1381 equal `min(255, g · frame1361)` with g = 1.104, then 1.208 (linear);
  - the same g applies to channels next to saturated ones, and per-pixel steps do not shrink;
  - this refutes framebuffer accumulation and alpha mishandling.
- **Inputs (VERIFIED, INFERRED):** textures, fragment constants and blend state are identical across frames (VERIFIED). The fragment programs mix in a vertex-supplied colour by a vertex-supplied weight (`tc1`), so a vertex-stage value drives the gain (INFERRED). Its values were not recorded. (`LOADING_SCREEN_FRAME_ACCUMULATION.md`)
- **VERIFIED (stall boundary):** at 45.8 s (frame 1733), a guest thread joins `AsyncRenderThread` (tid 28), which exits normally.
  - After that the drain still decodes RSX commands: depth/stencil clears, binds of the unsupported depth-like formats `0xB0` (1024×2048) and `0xB4`.
  - No replay, Present, `[vstat]` or shader translation follows.
  - FIOS and SPU continue to 210 s.
  - Flip requests were not recorded, so case A (guest stopped flipping) and case C (runtime swallowed flips) are both open.
- **HYPOTHESIS (case C mechanism, in code):** once clear-boundary presents start, guest flips no longer present. Only a display colour-clear with display draws does, and records past 2048 are dropped. Not changed. (`PRESENTATION_STALL_ANALYSIS.md`)
- **VERIFIED:** the frame-clock watchdog watches the host thread, which kept cycling. It worked as designed. New `PS3_PRESENT_PROGRESS_MS` reports flips, drain, replays, present-gate reasons, batch fill, FS and SPU activity during a stall.
- **VERIFIED (FIOS):**
  - The 0→671 MB sequential PSARC walk matches `cache.dat` growth (29 → 672 MB), i.e. cache population.
  - `garage_sky_read_complete` was completed by that walk, not by the game (6.41 MB requested). (`FIOS_SEQUENTIAL_READ_ANALYSIS.md`)
- **Fix:** D3D12 vertex programs now decompile with their branch base (`test_vp_branch_base`). Its effect on MotorStorm is UNKNOWN.
- **Next:** `NEXT_RENDER_DIAGNOSTIC_RUN.md`: stop at a 6 s presentation stall, plus RSXI VP constants and programs. Needs authorization.

## Garage render validation run: loading screen brightens with constant inputs; presents stop at 45 s (2026-10-23)

Run `generated/runs/20261023-150148-garage-render/` (exe `8baed049…`, ps3recomp-int `dadfcaa`, intro skip, native audio, `--allow-extended`). Cache snapshot `generated/cache-snapshots/20261023-150148`.

- **VERIFIED termination:** wall-clock timeout, 210.1 s. No fatal line, no `[fc-watchdog]` report, no `Present failed`, no `GcKernel::Present() Timeout`; no leftover process.
- **VERIFIED:** `garage_sky_read_complete` at 95.98 s (all 205 blocks). It was read inside a sequential 64 KiB sweep of the PSARC (pos 0 → 671 MB at the stop) while FIOS `cache.dat` grew 29 MB → 672 MB (FIOS caching the archive to `dev_hdd1`). Whether the game requested the sky or the sweep covered it is UNKNOWN.
- **VERIFIED:** no cube program within 210 s: 0 `[CUBE]`, 0 `cube≠0` `[shader]` lines. 13 programs translated, compiled and got a pipeline; 11 bound by draws; 0 failures, 0 fallbacks. The last new program (`0x02538941`) came during the intro.
- **VERIFIED:** guest presents stop at frame 1733 (~45.8 s); no `[rsx-hb]` after that, while the frame-clock thread kept making progress (no watchdog report). SPU tasksets (images `406081863`, `341580667`, `308733018`, `491898574`) and FIOS reads continue to the end. Loading did not reach shader creation for the garage; whether the frontend is blocked or merely slow (HDD cache fill at ~4–6 MB/s) is UNKNOWN.
- **VERIFIED queries:** 4 distinct ZPASS reports, all during boot: offsets `0x14110`, `0x14120`, `0x14130`, `0x14100`, `dma=0xFEED0001`, value `0xFFFF` (not measured). None new after the intro.
- **VERIFIED capture (frames 1361/1371/1381, garage loading artwork):** 3 draws each, straight to the backbuffer (`fp 0x02537E81` ×2, `0x02538941`), blend enabled (`0x0122418B`), 0 clears, no post-FX chain. Program, constants and texture checksums are identical across the three frames, yet the backbuffer brightens: R/G/B mean 150.4/122.9/61.8 → 156.0/128.2/66.9 → 160.5/132.6/71.4, white pixels 3.9 → 5.7 %.
- **HYPOTHESIS (new lead for white-to-black):** the brightening depends on the destination, not the inputs: blending onto a backbuffer that is never cleared accumulates. This weakens the exposure/luminance hypothesis for the loading screen (no luminance pass runs there). Next: decode `blend_key 0x0122418B` and compare what the guest display buffer at RT offset 0 holds against the D3D12 backbuffer (offline first).

## Bink intro video renders; frontend advances to the garage scene (2026-10-21)

- **VERIFIED decode:** BINK handle `0x46E50CC0`: 1280x720, 3159 frames at 30000/1001. FrameNum advances at about 7.8 fps (about 1/4 of real time, SPU-bound), so the intro takes about 7 min.
- **VERIFIED render path:**
  - The conversion draw `fp 0x051860C1` samples Y (1280x720, B8 `0xA1`, double-buffered `0x00935B80`/`0x00A87380`) and V/U (640x360) planes into offscreen RT `0x053A6D00`.
  - Composite `fp 0x02537E81` samples that RT; the post-FX chain then runs and the frame is presented by `fp 0x02193941`.
- **VERIFIED root cause of the black video (ps3recomp D3D12 backend):** the `SCREEN_AS_TEX` fallback (a display-sized texture reads the previous presented frame) ran before the exact offscreen-RT match. It also caught the display-sized B8 luma plane, which left the picture chroma-only.
  - Fix: the RT match comes first, and the fallback only takes A8R8G8B8/D8R8G8B8 textures.
  - Test: `ps3recomp/tools/test_d3d12_texture_source_order.py`, mutation-checked.
- **VERIFIED:** the original intro plays to the end with motion and colour (`generated/frames/video-luma-20261021-1/`, `menu-long-20261021/`; all frame hashes distinct). Awaiting the user's visual confirmation.
- **VERIFIED:** with no skip and no input, the frontend advances by itself after the intro (about 7.7 min). It loads `track_garage` and `default.race` (through the PSARC; loose-file probes fail as usual) and compiles cube-map shaders. It shows an artwork screen with the MotorStorm emblem (`menu-long` frames 22–23).
- **BLOCKED (new):** over about 25 s that screen brightens toward white (mean luma 19 → 196, converging), then presents turn black.
  - An A/B run with `SCREEN_AS_TEX=0` (`menu-noscr-20261021`) gives the same curve, so the frame-copy fallback is ruled out.
  - **HYPOTHESIS:** auto-exposure. The luminance chain (`fp 0x74D0C1` 640x360, `fp 0x7400C1` 320x180 from RT `0x01DD0000`) is rendered into D3D resources only. A CPU/SPU readback of the measured luminance would find guest memory unwritten, and the exposure would run to its maximum.
- **Not established:**
  - whether `mainmenu.gui` is requested (PSARC-internal opens are not logged);
  - whether the emblem screen is the title or a loading screen;
  - `FrontendVideoCanStart`/`SetIntroVideoSeen` (not reached within 150 s);
  - the 1/4-speed SPU decode.
- **Intermittent:** about 3 of 5 launches stall before the fonts or video open. Not investigated.

## FIOS/LFQueue false NOSYS fixed; intro splash screens render (2026-10-21)

- **VERIFIED (correction):** "One 256 KiB Bink read" was a logging artifact: the fs log prints only the first read per descriptor. The game's Bink read callback `func_005CB5B8` (Bink IO thread, tid 28) read about 8 MB in 512 KiB chunks through FIOS before stalling.
- **VERIFIED wait chain at the stall:**
  - `func_0065B460(count, ops[], timeout)` is the game's FIOS "wait for N ops" routine. It checks op state `+0x88` and status `+0xC4`/`+0x3C`, links a waiter at `+0xC8`, and lwcond-waits in 2 ms slices.
  - The Bink IO thread's op waited on FIOS mediathread tid 7.
  - tid 7 was blocked on lwmutex `0x404960B0`, held by mediathread tid 6.
  - tid 6 was in `cellSpursEventFlagWait(0x40494D80)`, waiting for the SPU decompressor (image `482286362`, entry `0xF98780`, taskset `0x40493480`).
- **VERIFIED first incorrect return:** exactly one `_cellSpursLFQueuePushBody` call in 3,304 returned `0x80410723` (NOSYS), with the guest queue left unchanged. It came right after Bink created its own taskset `0x0135D080` in the same SPURS `0x4004F180`, also with task 0 enabled. FIOS's protocol is Clear → Push → Wait, so the failed push left tid 6 waiting for a completion that was never queued.
- **VERIFIED root cause (ps3recomp `cellSpurs.c`):**
  - The recipient scan replaced its `0xFFFE` "registered waiter" selector with the first match's task id. Later tasksets then skipped the registration filter, and Bink's taskset counted as a second owner.
  - The direct-recipient first push (`selector=0000`) had the same ambiguity.
  - Fix: the selector is constant for every candidate. When several tasksets match, the one whose task registered on the queue (recorded at its PUTLLC) is the owner; otherwise NOSYS as before.
  - Regression test: `libs/spurs/tests/test_lfqueue_push_recipient.c`, which fails on the old logic.
- **VERIFIED after the fix (hooked build, 150–180 s probes):**
  - No PushBody NOSYS.
  - The Bink read callback ran 5,536 times; fd 4 read 86.5 MB, more than the 53.5 MB file, so the video loops.
  - The Bink SPU task (`0x0135D080`) completed 795 decode rounds of up to ~170 ms.
  - FIOS preloading continues (PSARC 445 MB; `/audio/atvsmall_player.vsb` fails to open: absent from the disc and the PSARC).
  - Draw-gated D3D12 captures (`generated/frames/bink-intro*-20261021/`) show new original screens: "Sony Computer Entertainment presents", the copyright/Havok screen and the MotorStorm Pacific Rift logo. Awaiting the user's visual confirmation.
- **BLOCKED (next):** after the logo, draw-bearing presents fall to about 5 per second and every captured frame is black. Video frames are not yet visible, and `mainmenu.gui` has not been requested. Next: trace Bink frame output (texture upload, shader, draw) on the render side.
- **Audit:** `audit_public.py --tree ps3recomp` reports the same 29 pre-existing worktree items:
  - `.git/`, `scratch/ppu_conformance.{cpp,exe}`, `ppu_conformance.obj/`;
  - generated `runtime/spu/tests/out_*` lifted outputs;
  - `packaging/macos`, a wiki PDF under `docs/`, `tools/__pycache__/`.
  - They are left in place and must stay out of any release staging tree. No changed or new file is flagged.

## Font atlas completes; frontend reaches the GUI intro video (2026-10-21)

- **VERIFIED:** The original fonts are on the disc as `PS3_GAME/USRDIR/GUI/FONTS/{FRAMDCN,KAB_PLAIN}.TTF` (an incomplete extraction caused the earlier "absent" claim). In the trace-hooked build (`build/motorstorm-trace`, exe SHA-256 recorded in `generated/logs/exe-hashes-20261021.log`), the game opens both through `/dev_bdvd/...` after its `/dev_hdd1/<font>.ttf` cache probe fails, as designed.
- **VERIFIED root cause of the atlas stall:** `cellFontCreateRenderer` had two parameters instead of `(library, config, renderer)`, and Bind/Destroy took an index instead of the caller's `CellFontRenderer*`. Bind returned `INVALID_PARAMETER`, so every later render call failed with `RENDERER_UNBIND` and the glyph measured 0×0. `func_00584C20` then never returned.
- **VERIFIED after the fix (probe `rtrace-fonts2-20261021`, 90 s):**
  - `func_00584C20` returns 25 of 25 times, with glyph sizes between 9×9 and 12×15.
  - `func_001E8058` returns 7 of 7 times.
  - The frontend opens `gui/video/gui/gui_intro_eu.bik` and creates "Bink Audio Thread" and "Bink IO Thread".
- **BLOCKED (next):** The intro video does not play. The Bink file gets one 256 KiB read and nothing more. Its IO thread (tid 28) waits in the game's streaming layer at `0x0065B460`, under `0x003BC110`. The main thread polls Bink (`0x00C6ED28 → 0x005CB5B8`). No new draws after the open; no title screen or menu, and `mainmenu.gui` is not requested within 90 s.
- **PARTIAL overhead (60 s, tracing off):**
  - ordinary build: 119.8 s CPU, 708 MB peak private memory;
  - hooked build: 142.1 s CPU, 737 MB peak private memory.
  - Not like-for-like: the ordinary build predates the font fixes and stalls in the atlas, while the hooked build runs further, into Bink.

## Glyph-atlas stall after failed font open (2026-10-21)

- **VERIFIED:** The second `func_001E8058` invocation does enter `func_005867A8` from `0x001E82B8`. The first invocation's entry clears a 2048×1024-bit atlas occupancy bitmap and returns; the second takes the glyph path at `0x00586C20`. On tid 1, after `framdcn.ttf` fails to open, original code calls `cellFontBindRenderer` (returns `0x80540002`), unregistered `cellFontSetScalePixel` (`0x4D19C631`), `cellFontRenderSurfaceInit` (`0x90B9465E`) and `cellFontRenderSurfaceSetScissor` (`0xB422B005`). The unresolved-NID default returns 0 for those three and writes nothing. `cellFontRenderCharGlyphImage` then returns `0x80540002` because the font handle is not open. The game ignores these results and enters glyph-atlas packer `func_00584C20` (return site `0x00586D38`), which does not return within 75 s. Thread 1 makes no further HLE call. A guest NULL+0x10 read by `func_0022D6B8` follows immediately.
- **VERIFIED:** The unresolved-NID warning is capped at 40 lines per process, so these cellFont calls were invisible in earlier logs.
- **HYPOTHESIS:** `func_00584C20` packs a glyph whose size comes from the never-written glyph image (`r1+140`/`r1+144`), so it does not terminate. The game expects the font open to succeed. It probes `/dev_hdd1/kab_plain.ttf` and `/dev_hdd1/framdcn.ttf` before `cellFontOpenFontFile` on `/dev_bdvd/PS3_GAME/USRDIR/gui/fonts/*.ttf`, which suggests a cached or extracted copy (possibly from `/fonts.rpk`) is expected.
- **BLOCKED:** Next: (1) find the original code that opens `/dev_hdd1/<font>.ttf` and what it does on failure (extraction from `/fonts.rpk`?); (2) implement the three missing cellFont APIs in ps3recomp from public documentation with focused tests. Do not substitute fonts or fake a successful open. Private logs: `generated/logs/{frontend-second-checkpoints,scan-5867a8-inside,font-glyph-path}-20261021-*`. All probed AOT chunks were restored byte-for-byte and the ordinary executable rebuilt.

## Post-SetExitOnline handoff (2026-10-21)

- **VERIFIED:** In the bounded original-game trace, `SetExitOnline` (`0x00782E68`) returns to the live command dispatcher (`0x0059DC60`), which returns to `func_0059F2F8` at `0x0059F978`. The enclosing command scanner `func_005B24D8` also returns. No later dispatcher entry was captured in that 110-second run; this does not establish that the command queue is empty.
- **VERIFIED:** The scanner's caller, `func_001E8058`, runs on PPU tid 1 and is called from `func_001F5658` at `0x001F6014`. One invocation completes calls through `0x001E82B8` and `0x001E82C4`, returns normally, and its caller resumes. A second invocation passes the call at `0x001E82AC`, enters trampoline `0x00753158` at `0x001E82B8` with r4=`0x005B51C4`, r5=1, r6=0, and does not return within the 90-second bound. The trampoline targets original `func_005867A8` in the AOT source; a bounded trace has directly observed this handoff for the earlier call, while the second target's internal path is being traced.
- **VERIFIED:** Two sparse probes saw `func_005867A8` finish a finite original bitset scan: its cursor advanced across 0x40000 bytes over about 2,097,152 bit iterations and the function returned 1. That completed instance was in the earlier `func_001E8058` invocation. No second entry to this function appeared within the 90-second sparse bound. The scan is not evidence of an incorrect translated branch.
- **BLOCKED:** The first unmet title/menu condition remains unidentified. The next focused capture is the second `func_005867A8` invocation's branch and return path, then the surrounding `func_001E8058` state. No `mainmenu.gui` request or title/menu image is verified. No runtime compatibility behavior was changed.
- **TESTED:** The reusable private-AOT tracer now supports multi-function call-site traces, multiple return checkpoints, guest labels and sparse power-of-two sampling while restoring every modified chunk byte-for-byte and rebuilding the ordinary executable. Six focused tool tests pass. Private logs: `generated/logs/frontend-{handoff,outer-handoff,next-query,postquery-checkpoints,bitset-progress,after-bitset,caller-handoff}-20261021-*`.

## Frontend command and callback trace (2026-10-21)

- **VERIFIED:** Private ELF/AOT mapping identifies original command wrappers for `PrepareLoadingScreen` (`0x0077F800`), `PopulateLoadingScreen` (`0x0077F868`), `Preload` (`0x0077F8D0`), and `PreloadDone` (`0x0077F938`). The `mainmenu.gui` string is referenced by `func_00016758`; its role in title initialization is not yet established.
- **VERIFIED:** A bounded original-game trace reaches `PopulateLoadingScreen` on PPU tid 1. It queues `func_000717B0` through `func_009B33E8`; tid 11 invokes the callback through the original work-queue path, writes its object `+0x24` to 1, and returns normally. `func_00070D98` then writes the preload object's `+0xE0F8` byte to 1. An exact-address read watch saw only the earlier zero read by `PopulateLoadingScreen`, not a later consumer read in its 55-second bound. This is evidence that the producer runs, not that all preload work is complete.
- **PARTIAL:** The original command-dispatch call site at `0x0059E160` belongs to `func_0059DC5C`. It invoked `PopulateLoadingScreen` and later `SetExitOnline` within a 70-second bound. No invocation of `PrepareLoadingScreen`, `Preload`, `PreloadDone`, or `func_00016758`, and no read of the `mainmenu.gui` TOC slot, was observed in the selected bounded traces. Other call paths and later execution are not excluded.
- **VERIFIED:** A private entry trace identified the live dispatcher translation as `func_0059DC60`, called by `func_0059F2F8` at guest return `0x0059F978`. Its command object at `0x401D2BA0` repeatedly held state `0x10`, which calls wrapper `0x0076C808` and original predicate `func_00014898`. That predicate reads byte `0x010D529C`. It returned zero initially; original `func_00094D98` later wrote 1 to that byte, the predicate returned 1, and the interpreter advanced. Thus the state-`0x10` wait resolves naturally and is not the persistent loading blocker.
- **PARTIAL:** The next command object at `0x401D3040` invoked `SetExitOnline` (`0x00782E68`). A 120-second bounded trace recorded no further dispatch transition or command-handler call, and no title/menu frame. Whether the driver intentionally ended this command stream or waits on another frontend owner is unverified.
- **VERIFIED:** The user-supplied PSARC contains `/scripts/cache_preload.xml` and `/gui/mainmenu.gui`. The preload list has 1,812 entries; one path, `/audio/ATVSmall_Player.vsb`, is absent from the named PSARC manifest and loose disc files. No startup failure or retry involving that path was observed; its causal relevance is unknown.
- **BLOCKED:** The prerequisite that starts the original title/menu command stream after `SetExitOnline` remains unidentified. Next: trace `func_0059F2F8` after its final observed dispatch and identify the owner of the next frontend script or callback. No runtime behavior was changed to force the transition.
- **TESTED:** Opt-in indirect-call target and caller-range filters were added without changing guest dispatch. Bounded 50–90-second probes and a clean Windows x64 rebuild/link passed. Private temporary AOT markers were removed and the generated source rebuilt. Logs: `generated/logs/frontend-{dispatch,callback,state,preload-exact,menu-request,init-exit}-20261020-stderr.log`; build log: `generated/logs/frontend-clean-build.log`. No meaningful new original frame was observed.
- **TESTED:** Additional 70–120-second private dispatcher, predicate and exact-byte write probes established the state-`0x10` transition and later `SetExitOnline` call. See `generated/logs/frontend-{predicate-body,predicate-writer,transition-after-ready,after-ready-call}-20261021-stderr.log`. Both temporary AOT chunks match their pre-probe backups by SHA-256; the final Windows x64 rebuild/link passed. `git diff --check`, five audit regressions, and the fresh source-only staging audit at `build/public-stage-frontend-final-20261021/` passed. No files were published.

## Focused loading dependency trace (2026-10-20)

- **VERIFIED:** Private AOT inspection maps thread 12's 200-µs loop to `func_004AF670`. It reads a byte at object `+0x4064`; zero executes work handlers and repeats, while nonzero exits the worker. The object is allocated as `0x406C` bytes, initialized to zero in `func_004AFE18` (`0x004B0128`), and has direct nonzero writers in `func_004AF6F8` and `func_004AFA90`. A filtered entry trace reached the loop on tid 12. Continued zero is consistent with an active worker and is **not established** as a title-loading dependency.
- **VERIFIED:** The original save-data task `func_0022D6B8`, invoked through `func_00833E70` on tid 11, receives return code zero from `cellSaveDataListAutoLoad` and takes its success path. It changes task state `+0x3F8` from 0 to 1. A byte at task `+0x40` is 1 at an intermediate point and is cleared later in the same function; it is not evidence of a persistent completion signal. The task does not remain in the save-data API.
- **PARTIAL:** A bounded opt-in `PS3_HLE_AFTER_NID=21425307` trace recorded 11 subsequent imports on tid 11, comprising thread ID and lightweight mutex operations. An exact state watch confirmed the original write of 1 to task `+0x3F8` at `0x46BD6810`. A post-import read watch saw no read of that word over 90 seconds; it covers reads through the normal guest-memory helpers, not every possible raw or DMA access. The live-thread census measured tid 11 CPU unchanged from 5 to 15 seconds after the save call, while `JobBatchHandler` tid 12 accumulated about 10 seconds of CPU over that interval. None of these observations establishes the title transition's first unmet condition.
- **BLOCKED:** The title transition's original function, gating condition and intended producer are still unidentified. The next decisive experiment is to trace the original frontend/preload state transition and its callback ownership, beginning with the savedata task's enclosing scheduler and main-thread state. Do not change save-data or the worker stop byte on the current evidence. Private traces: `generated/logs/loading-{postsave,branch,taskchain,worker-entry,save-state-writes,postsave-state-reads,postsave-census}-20261020-*`.
- **TESTED:** The Windows x64 incremental build and link passed after removing all private AOT probes. The 70/90/60-second native watches and census reached the original save task; none verified a title/menu transition. `git diff --check` in the nested framework passed, all five public-audit tests passed, and the fresh source-only tree `build/public-stage-loading-trace-final-20261020/` passed the public release audit. No files were published.

## Loading-screen PSO and offline-network investigation (2026-10-20)

- **VERIFIED font ABI defect:** A read-only trace of two original `cellFontOpenFontFile` calls showed the runtime interpreting r3 (`library=0`) as the output font and immediately returning `INVALID_PARAMETER`. The public five-argument API places the output font in r7; after correcting the handler declaration and implementation, the original calls reach file opening and return `OPEN_FAILED` for the requested TTF paths. The focused five-argument regression passes, and the rebuilt original-game probe reached at least draw `#7000` and both save-data loads. This is a corrected API contract, not proof that missing fonts hold the title transition.
- **VERIFIED asset inventory:** The user-supplied PSARC manifest has 5,004 named entries and includes `/fonts.rpk`, but neither requested `kab_plain.ttf` nor `framdcn.ttf`. The disc's shallow file layout also has no loose TTF. The actual intended source for those fallback font paths is unresolved; no substitute font or fabricated success was added.
- **VERIFIED wait trace:** A 45-second `PS3_WAITBT=1` probe identifies queue 17's repeated timeout-zero receive as PPU thread 24 at syscall stub `0x0108DD20`; its first guest stack has no higher caller chain. Queue 15 is a distinct thread 19 path through `func_00A3F600+0x50`. These captures do not establish that either queue blocks the main loading transition. Private log: `generated/logs/loading-waitbt-20261020-stderr.log`.
- **VERIFIED extended bound:** A 300-second FIRST_FRAME probe with late draw-gated capture stayed on the loading emblem. Three saved late frames had 2,627–3,923 nonblack RGB pixels within the emblem bounds; no title/menu pixels appeared. The trace logged 24,649 original SPURS task signals, a last periodic draw milestone of `#7000`, both save-data LOAD completions, zero PSO creation failures, zero unlifted SPU branches, and zero assertions. Queue-17 receives returned success with events about every 10–16 ms, so its worker is active. This is a measured five-minute loading state, not proof of a single root cause.
- **PARTIAL wait ownership:** `PS3_POLLTOP=10` identified PPU thread 12 repeatedly sleeping for 200 µs at guest return `0x004AF6D0` inside `func_004AF670`. The original function checks a byte at object offset `+0x4064`; a read-only register snapshot gives object `0x40CADA20` and watched byte EA `0x40CB1A84` in that run. The object address is diagnostic evidence, not a runtime constant.
- **VERIFIED targeted flag watch / BLOCKED producer:** Two bounded `PPU_WWATCH=40CB1A84` runs observed one original PPU byte store of zero at guest `0x004B0128` (tid 1), followed by thread 12 repeatedly reading the zero flag. Neither run recorded a nonzero PPU store to that byte. This establishes the initialization writer and a missing *observed PPU* completion write during the bounds; it does not exclude an SPU DMA or host-side write later. A page-guard diagnostic armed on the page but did not report even the known PPU store, so its absence of hits is inconclusive. Do not set the flag artificially.

- **VERIFIED graphics defect:** D3D12 debug message 690 identified the failing `0x02193941` PSO precisely: its pixel shader uses sampler register 4, which the four-unit root signature did not bind. The original full-screen composition samples texture units 0–6; units 4 and 6 are 640×360 and 40×22 offscreen render targets in the observed draw. The backend now preserves and binds all 16 RSX texture units across draw snapshots, descriptor tables, samplers, and render-target transitions. The rebuilt Windows executable logs `guest FP pipeline ready (fp=0x02193941)` and no PSO creation failure. This fixes a real rendering defect but did not reveal a title screen.
- **VERIFIED network defect:** The initialized offline `cellNetCtlGetState` previously wrote `Disconnected` and then returned `NOT_INITIALIZED`. It now returns success with the disconnected state; calls before `Init`, after `Term`, and with a null state pointer retain their error contracts. The standalone lifecycle regression passes. A matched 60-second original-game probe changed hundreds of repeated `NOT_INITIALIZED` polls to one successful disconnected query followed by `Term`, while preserving offline behavior.
- **PARTIAL startup:** Bounded 120- and 180-second FIRST_FRAME runs with the graphics and network fixes reached both original save-data LOAD callbacks, repeated SPU task signals, and more than 6,000 D3D12 draw submissions. No new PSO failure, assertion, unsupported import, or unlifted SPU branch was logged. The 120-second capture directory was created too late to retain its images; the correctly prepared 180-second capture saved six spaced draw-bearing frames, all showing only the original animated loading emblem (2,131–3,834 nonblack RGB pixels). A later 90-second probe with the font ABI fix reached at least draw `#7000`, but captured no new screen. Title and menu remain unverified. The evidence does not yet establish a single remaining blocking API or whether later content was submitted invisibly.
- **TESTED:** Windows incremental build/link passed after each runtime fix; fragment shader regression 49/0, SPU execution 103/0, overlay discovery 1/0, offline NetCtl lifecycle regression, five-argument font ABI regression, and public-audit regression 5/0 passed. Private traces: `generated/logs/pso2193941-capture-20261020-*`, `texture16-20261020-*`, `netctl-disconnected-20261020-*`, `netctl-180-20261020-*`, and `fontabi-20261020-*`.
- **NEXT:** Identify the intended nonzero producer for the thread-12 wait flag by tracing the original job request and its completion callback. Establish whether that task is on the loading critical path; a worker wait alone does not prove causality. Determine whether font-file failures are expected fallback probes or a real UI dependency. Do not attribute loading to thread 24's working queue-17 receive.

## First original rendered image (2026-10-20)

- **VERIFIED root cause:** D3D12 cached the guest `SET_SHADER_CONTROL` 32-bit export flag but called the fragment decompiler with `RSX_FP_CTRL_AUTO`. For the second six-vertex screen draw (`fp=0x02538DC1`, `exp32=0`), AUTO exported `r0`, an intermediate coordinate, instead of hardware-selected `h0`, which contains the sampled image. The backend now passes the recorded flag to the decompiler; no guest shader or asset was changed.
- **VERIFIED first image:** A 35-second bounded original-game probe captured four draw-bearing 1280×720 backbuffers in `generated/frames/exportmode-fixed-20261020/`. All contain a changing, centered original loading emblem (2,634–2,938 nonblack RGB pixels; image bounds near x=602–683, y=315–398). The user visually confirmed it matches the game icon. The earlier all-black captures sampled guest flip presents without draws; they did not establish that draw-bearing presents were black. No title screen, menu or gameplay is verified.
- **TESTED:** Incremental Windows x64 build/link passed; the 49-check fragment decompiler regression, 103-check SPU execution regression, overlay discovery test and five public-audit tests passed. The current probe retains repeated SPU event completions. A preexisting PSO failure for a different FP (`0x02193941`, `0x80070057`) still appears in both baseline and fixed logs; investigate when that draw becomes relevant.
- **PARTIAL later startup:** A 60-second bounded probe sampled four spaced draw-bearing presents; all still show the animated loading emblem (2,634–3,798 nonblack pixels). Title/menu transition and any later upstream render target remain unverified.
- **NEXT:** Trace subsequent original frames and the upstream render target using draw-gated captures. Determine whether the loading emblem progresses to a title/menu, and investigate the separate PSO failure if it blocks that transition.

## SPU overlay AOT continuation (2026-10-20)

- **VERIFIED:** Image `283218738` executes both DMA-loaded 12 KiB overlay variants at LS `0x35F00` through native AOT code. The first variant's observed indirect entries are `0x38790`, `0x38AD0`, `0x35F18`, `0x35F10`, and `0x36B40`; the second uses `0x35F10`, `0x35F18`, `0x35F70`, `0x36390`, and `0x36E70`. The latest 45-second probe executed `0x36E70` through AOT and logged no unlifted overlay branch. Earlier `async RETURNED rc=0` lines followed unlifted-branch halts and are not proof of guest job completion; the diagnostic was corrected.
- **VERIFIED:** Full-body fingerprints now gate dispatch of the locally generated overlays. An overlapping DMA write invalidates the old fingerprinted code even from the same EA, and unknown replacements fail explicitly rather than dispatching a stale base-image function. Legacy source-based continuation DMA behavior remains intact. The focused SPU runtime regression passes 103 checks; the discovery regression passes.
- **VERIFIED event completion:** The SPURS taskset is `0x0140D680`. Task slot 0, native SPU image `283218738`, receives event flag EA `0x0140F000` as task argument 3. In a 25-second bounded probe, that image issued `GETLLAR` at LS `0x158D8` and `PUTLLC` at LS `0x15B08` against the flag's 128-byte line. Its proposed store changed the event word from `0x0000` to `0x0001`; the PPU then observed the bit and completed its wait. The filtered trace recorded 1,639 wakes. No force or SPU interpreter diagnostic mode was enabled. This verifies repeated task work-cycle completion, not final task exit.
- **Historical capture limitation:** A 45-second probe submitted original RSX draws and completed 3,163 waits on event `0x0140F000`; guest flips and D3D12 presents occurred. Four sampled captures were black because the capture selector did not require draws in the captured present. Later draw-gated captures and the export-mode correction establish visible original output.
- **Historical rendering trace:** Four captures after skipping 500 presents were exactly black, but these too lacked a draw gate. `DRAWARGS` found two six-vertex on-screen draws using textures `0x0074AF00` and `0x04D88580`. One earlier upstream-target snapshot at `0x01DD0000` was black; its relationship to a draw-bearing frame remains unverified.
- **VERIFIED texture evidence:** The first on-screen source is a one-pixel local texture at `0xC074AF00` with no nonzero sampled byte. A separate 2560x720 local source at `0xC0750000` was also empty in the sampled region; the second on-screen source at `0xC4D88580` contained data (2,115 of 4,298 sampled bytes nonzero). The corrected guest FP displays the original icon from the latter draw. Full guest-to-GPU BC3 byte equivalence has not been independently read back.
- **TESTED:** Windows x64 incremental build/link; bounded event probes `generated/logs/spu-overlay-{eventwatch,event-atom}-20261020-*`; D3D12 capture `generated/frames/d3d12-20261020/`; overlay dispatch 103/0; Python overlay discovery 1/0; audit regressions 5/0; source-only release staging audit. Private binaries and lifts remain ignored.

## Latest SPU overlay investigation (2026-10-19)

- **VERIFIED:** Image `283218738` branches indirectly from LS `0x03CF4` (link `0x03CF8`) into DMA-loaded code. A 12 KiB GET to LS `0x35F00` first copied zero bytes from guest EA `0x4305EA80`, then a populated body from the same EA; a later GET from `0x43061A80` replaced it with a second body. Private version captures and hashes are under ignored `generated/overlays/spu38790/versions/`.
- **PARTIAL:** The two populated bodies were lifted ahead of time into private generated source: 84 and 64 registered functions, respectively, with no reported unsupported instructions. A public local-build script selects the captured versions by hash; the native runtime selects a resident lift only after matching code bytes at the observed entry and invalidates it on a different-source overwrite. A focused runtime test passed 99 checks. Native probes executed past the original `0x38790` branch and subsequent observed indirect targets, but later runs varied in how long they spent in earlier queue loading.
- **BLOCKED:** No bounded probe has yet confirmed completion of image `283218738` or a wake of event flag `0x0140F000`; earlier runs stopped on newly discovered indirect entries, and the latest runs ended before overlay dispatch. The image ran in taskset `0x0140D680`, to which that event flag is attached, but the expected event-setting action is unverified. No original draw/present, frame or menu is verified. Do not treat a returned async job after an unlifted branch as a completed original job.
- **TESTED:** Native Windows compile/link, SPU overlay registration regression, bounded startup probes, and source-release audit. The final probe logs are `generated/logs/spu38790-entry4-{20261019,atom-20261019}-*.log`; AOT and capture artifacts remain private.

Older sections below remain as dated history.

## Latest native startup result (2026-10-19)

- **VERIFIED:** The Edge Zlib line-420 assertion was the original PPU checking a nonzero `_cellSpursLFQueuePushBody` return at guest `0x007285DC`/`0x007285E4`. The return was `0x80410723` (`NOSYS`) on later direction-3 submissions, not a decompressor error. Two bounded native probes after the producer fix show at least 96 logged successful pushes (trace capped at 96), repeated original SPU wake/DMA/queue consumption, PPU event completions, further archive reads, and original RSX clear commands. Neither probe printed the assertion.
- **PARTIAL:** The handler now covers reference-captured uncontended direction-3 states and original SPU waiter registration transitions, including the observed waiter phase wrap. Full queues, outstanding reservations, ambiguous owners and unverified encodings remain `NOSYS` without guest mutation. This does not establish general LFQueue compatibility.
- **BLOCKED:** Both probes later branch from an SPU image logged as ID `283218738` to unlifted local-store address `0x38790` (LR `0x03CF8`); a PPU thread waits on event flag `0x0140F000`, bit `0x0001`. The relationship between that branch and wait requires tracing. No original draw/present, frame or menu is verified; visual inspection is not yet useful.
- **TESTED:** LFQueue planner, native startup regression, preserved initializer regression, silent-audio regression, incremental Windows link, and public-source staging audit passed. Probe logs: `generated/logs/edgezlib-{atomic-waiter,repeat}-20261019-{stdout,stderr}.log`; private reference captures remain under ignored `build/ps3ref/`.

The dated sections below describe earlier milestones and blockers that the latest result supersedes.

## 2026-10-19 verified LFQueue integration

- **VERIFIED:** The independently written direction-3 PushBody handler now handles the captured initial registered-waiter transition, with guest lock-line serialization, reservation, 32-byte ring copy, publication and taskset signal. The native queue at `0x40494E00` changed consumer word `0000000000010000 -> 0000000004010000` and producer word `0000000000000000 -> 0001000000000001`, matching the original firmware capture. Its ring slot at `0x40494E80` held the 32-byte caller item. Other waiter encodings, ambiguous owners, full queues and outstanding reservations still return `NOSYS` before mutation.
- **VERIFIED:** In two bounded probes, original SPU task 0 left its first `WAIT_SIGNAL`, DMA-read the 32-byte ring slot at guest PC `0x09748`, committed original queue atomics and caused the PPU event flag `0x40494D80` bit `0x0001` to wake. The SPU later entered `WAIT_SIGNAL#2`. A third probe reproduced the DMA and second wait but did not log the first PPU event wake; event ordering needs investigation.
- **BLOCKED:** The original game now prints `edgezlib_inflate_queue.cpp:420 (0 == ret) -- assertion failed` and does not reach a meaningful frame or menu. Determine the failing `ret` source and why the second queue/event wait persists. The prior missing PushBody producer is resolved for this observed first item, not for all queue states.
- **TESTED:** Incremental Windows x64 build/link, capture-checked LFQueue planner, native queue/DMA/wake regression, initializer regression, SPURS taskset wake (9 passed), and silent-audio regression passed. The staged public source audit and five audit tests passed. Private logs: `generated/logs/pushbody-{integration,final,repeat}-20261019-*`; build log: `build/lfq-build-20261019.log`.

## 2026-10-19 FIRST_FRAME optional-service probe

- **VERIFIED:** A bounded `PS3_HLE_TRACE=12000` native probe recorded 12,147 calls across 67 distinct NIDs, including PushBody and the subsequent SPURS event-flag wait, before its trace budget ran out. `tools/report_startup_apis.py` resolves all 67 from the generated registration table and pinned NID database. Essential calls include PPU threading, locks, SPURS, timers, filesystem, game data, video output and system callbacks. The only reached optional category is ten `cellAudioOut*` capability/device queries, already handled by the existing runtime. No `cellAudioInit`, network, trophy, pad or save-data API was observed within this trace window.
- **PARTIAL:** Added opt-in `FIRST_FRAME=1` with independent `FIRST_FRAME_AUDIO=silent|unavailable|native`. On the native Windows WASAPI build, `silent` keeps `cellAudioInit`, the original guest mixer, 48 kHz block pacing, ring cursor progression and completion-event delivery, while skipping host device output. `unavailable` returns `CELL_AUDIO_ERROR_NOT_INIT`; default mode is unchanged. No other optional service was changed because none was reached before the SPURS blocker.
- **VERIFIED tests:** Audio-policy test passed on WSL; native Windows silent-audio integration test passed init, clock-paced cursor advancement, event delivery, unavailable-error return and clean shutdown. Incremental Windows build linked. Matched six-second default and FIRST_FRAME game probes both initialized D3D12, read `MS2.PSARC`, and reached explicit PushBody unsupported. Neither logged a flip/present or original game frame. The silent audio backend was not invoked by this game during the bound, so it did not advance startup. The current queue-atomic trace interleaved two threads' diagnostic lines, preventing the initializer parser from using that capture; the preserved atomic-enabled reference capture still passes the initializer regression.

## 2026-10-19 scheduler wake control

- **VERIFIED:** The isolated fixture's genuine firmware `spursSendSignal(taskset, 0)` call returned zero without an LFQueue push. Its taskset signal word `+0x40` changed `0 -> 0x80000000 -> 0`; waiting `+0x50` stayed `0x80000000`, and the task's completion marker remained zero through a bounded 200 ms check. This matches the already captured PushBody notification outcome, so LFQueue recipient selection alone cannot explain the non-resumption. Private capture: `build/ps3ref/lfq-direct-task-signal-20261019-rpcs3.log`.
- **VERIFIED:** Repeating the matched no-push and firmware-push fixtures with RPCS3's static SPU interpreter reproduced the blocked wait and published-but-unconsumed item. Both reference regressions passed. This rules out a failure specific to RPCS3's LLVM SPU decoder in this fixture; it does not establish a correct task lifecycle.
- **PARTIAL:** Native read-only `SPURS_SCHED_TRACE` at task 0's wait records `ready=80000000`, `waiting=00000000`, and taskset SPURS pointer `0x4004F180`. The isolated firmware fixture has `ready=00000000`, `waiting=80000000` after blocking. Native `spu_taskset_wait_signal` parks a dedicated host thread without updating those guest bitsets. The implementations differ, but the firmware fixture also fails on a direct signal, so this comparison is not proof that changing native bitsets would resolve startup.
- **BLOCKED:** The precise scheduler/task-context condition that prevents resumption remains unknown. No native PushBody state mutation or synthetic wake was added. The rebuilt native executable still reaches explicit PushBody unsupported and no meaningful frame. Next decisive experiment: trace the SPURS policy worker's handling of the cleared signal and compare task context-save and runnable metadata with a known resumable task.

## 2026-10-19 focused notification decision

- **VERIFIED:** A post-load breakpoint capture in the isolated original-firmware test measured recipient count **1**, recipient ID **0**, and a successful callback. The callback transiently sets taskset signal bit `+0x40=80000000` for task 0. Scheduler notification and check calls return zero; by callback return the signal bit is clear again, while the waiting bit at `+0x50` remains `80000000`. The earlier zero-recipient static prediction was disproven.
- **BLOCKED:** The isolated task still does not resume or consume the published item. The missing transition is in scheduler handling of the task signal: it is cleared without the waiting bit clearing or the task resuming. Its lifecycle or scheduler precondition is not yet established. Native PushBody remains explicitly unsupported and original startup has not advanced.

## 2026-10-19 original consumer wait-object cycle

- **VERIFIED mismatch:** The original native task's syscall-2 trace has queue EA `0x40494E00` plus 5 (`0x40494E05`) in SPU local-store wait-object slot `0x2FDC`. The isolated task previously wrote queue waiter `+0x04=0001` but did not set this slot. Its direct double-wait also omits the original consumer's queue-header read and conditional atomic retry path.
- **VERIFIED experiment:** `TEST_SPU_WAIT_OBJECT` sets the observed wait-object address before the second isolated wait. Matched private no-push and push captures (`build/ps3ref/lfq-waitobj-{no-push,push}-20261019-rpcs3.log`) pass the blocked-control and published-but-unnotified regressions. The no-push hold remained blocked. Original firmware PushBody returned zero and published `A0..BF`, but the taskset waiting bit stayed set and the task did not consume the item. The wait-object correction alone is insufficient.
- **BLOCKED:** The original notification helper receives a recipient count after atomic commit. Whether that count is zero in the fixture has not been observed dynamically. The next decisive capture is this count at firmware helper `0x439C` and the queue/taskset inputs used to select it, compared with the original consumer's full registration. The previous RPCS3 GDB attempt disconnected before a breakpoint, so no recipient count is claimed.
- **PARTIAL First Frame profile:** `tools/probe_first_frame.ps1` runs the existing native code with original PPU/SPU and graphics paths, local assets, offline network state, and optional audio-unavailable mode. A five-second bound again reached syscall-2 wait and explicit unsupported PushBody (`generated/logs/first-frame-lfq-wobj-20261019-stderr.log`). No frame or menu appeared; native PushBody and the corrected initializer were not changed.
- **VERIFIED checks:** Both matched reference captures passed `tools/test_ps3ref_lfq.py`; the five-second native trace passed `tools/test_spurs_lfqueue_push_pending.py`. Five public-audit tests passed. `build/public-stage-20261019-waitobj-cycle/` passed the source-only tree audit. Push/no-push private SELF hashes are `5bdbab9e6608fb056ba55705d78cf393166d1622a849763ac52cdfbbd0788dda` and `8dc290e302d20f58f5a53f41d479d1d0423c974dc21c92ffbeba098c7f58a`. The workspace root has no Git index, so `--staged` cannot run there; no commit or release was made.

## 2026-10-19 SPURS wait and notification probe

- **VERIFIED:** A one-bit nonzero task LS save pattern made the isolated firmware SPURS task enter a real `WAIT_SIGNAL`: taskset `waiting +0x50` held `80000000` through a 100 ms no-push control, and the 32-byte completion marker remained zero. Merely increasing context storage from `0x40000` to `0x41000` did not fix the earlier `STAT` return. The earlier `STAT` is therefore associated with the zero save-pattern fixture, but its exact firmware validation branch remains unproved.
- **VERIFIED:** With the task blocked before PushBody, original firmware returned zero, wrote the 32-byte item to ring slot 0, and changed queue `+0x00..+0x0F` from `00000000000100000000000000000000` to `00000000040100000001000000000001`. The taskset waiting bit stayed `80000000` and no completion marker appeared. This repeated with an attached LV2 queue and the game's tagged SPURS-owner form. The manually registered waiter is therefore still missing a notification precondition or consumer-side protocol step; publication alone did not signal it.
- **PARTIAL:** Added an independently authored, capture-checked pure planner for the initial waiter-free producer transition and a focused C regression. The native PushBody entry point remains explicitly unsupported and leaves guest memory unchanged for MotorStorm's registered-waiter call, as required by `AGENTS.md`.
- **VERIFIED checks:** Reference no-push and blocked-push assertions passed against private captures. Native rebuild linked successfully (SHA-256 `86595588786035C7D2BE8CE88FC6EA59A6CD3F09F2A9C75F6D2DD3BE592B56C9`). An eight-second bounded startup with `SPU_LFQ_ATOM_EA=0x40494E00` passed the direction-3 initializer and pending-PushBody regressions; original task 0 still waits. Five public-audit unit tests and the source-only release-tree audit at `build/public-stage-20261019-lfq-wait/` passed. A targeted RPCS3 GDB probe of the notification helper failed when its GDB server disconnected before a breakpoint; no helper-register claim is based on that attempt. No game frame or menu appeared.

## 2026-10-18 isolated PS3 firmware reference progress

- **VERIFIED:** Ubuntu WSL now has locally built ps3dev PPU GCC 13.2.0, SPU GCC 9.5.0 and PSL1GHT. The pinned local source revisions and private build logs are recorded in `docs/BUILD.md`. An independently authored PSL1GHT SPURS sample compiled, linked and executed under the user-installed RPCS3 firmware; its TTY log reached `Finalize spurs`.
- **VERIFIED:** A separate genuine-firmware direction-3 LFQueue fixture created a SPURS context and taskset, initialized a 32-byte/depth-4 queue, and called NID `0x8A85674D`. Four pushes, one pop and a wraparound push returned zero. The first ring slot contained the exact 32-byte input. With no waiter, the BE producer word `+0x08..+0x0F` advanced from zero to `0001000000000001`, then to `0004000000000004`; after a pop and wrap push it was `0005000000000005`. A PPU PopBody waiter with an attached LV2 event queue was also delivered the original item. These traces are private under `build/ps3ref/`; three focused log regressions pass.
- **PARTIAL:** A minimal SPURS SPU task accepted task ID 0, executed a DMA marker into PPU memory, and exited through the task syscall gate. A controlled SPU test registered BE `0x0001` at LFQueue `+0x04` using GETLLAR/PUTLLC. In one run, original PushBody returned zero and changed the consumer word from `0000000000010000` to `0000000004010000` while advancing the producer word to `0001000000000001`. This is a firmware commit observation with the registered field; it is **not** proof that a blocked SPU task was notified or consumed the item.
- **BLOCKED:** The test's direct `WAIT_SIGNAL` syscall returns before PushBody. A two-wait run briefly showed a zero pre-push marker and a post-push marker, but a 100 ms no-push hold produced the marker without any push, falsifying that notification inference. The first wait returned zero; the second returned `0x8041090F` (task `STAT`), including when the task was created with aligned context-save storage. The taskset's 16-byte `waiting` bitset at `+0x50` remained zero both when queue `+0x04` was `0001` and after the hold. A later push returned `0x80410905` after a test task had exited. The fixture must reproduce the original task wait contract and verify a nonzero waiting bit before notification can be specified. Full-queue, mode-3 blocking, concurrent ordering and SPU notification remain unverified. The native PushBody handler and game executable were not changed or rebuilt; native startup remains at the same SPURS stall. No menu or meaningful frame is available for visual inspection.
- **VERIFIED checks:** `tools/test_ps3ref_lfq.py` passed `no-waiter`, `ppu-waiter`, `spu-task`, and `spu-wait-control` modes against private captures. The prior native initializer and explicit-unsupported regressions passed against their saved traces. Five public-audit unit tests passed; `build/public-stage-20261018-ps3ref-final/` was staged and audited as source-only. No proprietary input or generated executable was staged or published.

**2026-10-18 firmware investigation — VERIFIED/PARTIAL:** The user-installed RPCS3 firmware 4.93 contains `build/rpcs3/dev_flash/sys/external/libsre.sprx`. A bounded, local PPU-debug run decrypted it to an ignored `build/rpcs3/ppu_progs/.../prog.prx`; the original RPCS3 configuration was restored afterward. The local loader identifies NID `0x8A85674D` as a `cellSpurs` export at ELF-relative PPU entry `0x171B8`. Private disassembly confirms a direction-3 reservation helper, guest-ring copy, commit helper and separate notification path. The packed atomic state transitions and waiter notification arguments remain unverified, so the public PushBody handler still fails explicitly without queue mutation. No native runtime code changed, no new native build/probe was warranted, and startup remains at the verified SPU/PPU waits. See `docs/RESEARCH.md` and `generated/firmware_analysis/libsre-inventory.json` (private).

**Verification:** The local firmware inventory completed and cross-checked the export descriptor; Python syntax check, the existing direction-3 initializer regression, the explicit PushBody failure regression, five public-audit tests, and a fresh source-only release-tree audit passed. RPCS3 is no longer running and its `PPU Debug` setting is back to `false`. Single push/pop, wraparound, full-queue, concurrency and notification tests remain pending because no verified producer behavior has been implemented.

**VERIFIED public-source boundary:** `original/`, `generated/`, and `build/` are Git-ignored. `tools/audit_public.py` rejects private and lifted content in staged Git blobs or release staging trees. `tools/stage_public_source.py` produced audited source-only staging trees under `build/` on 2026-10-18; five focused audit tests passed. This is local staging only, not a release. `libsre.sprx` and any lifted firmware output remain private; public SPURS behavior must be independently implemented.

**2026-10-18 latest LFQueue probe — PARTIAL:** NID `0x8A85674D` now resolves to a validating runtime handler. For the observed valid direction-3 queue it returns `CELL_SPURS_TASK_ERROR_NOSYS` without changing guest memory, instead of falsely returning success. The original SPU still waits; the producer protocol is **BLOCKED**, and startup has not advanced. `generated/logs/startup-lfq-explicit-nosys-final-stderr.log` records the 8-second probe. The existing initializer regression and new explicit-failure regression both pass. No meaningful frame or menu appeared.

**Build and distribution evidence:** The final rebuilt Windows executable is SHA-256 `f54f34c64fb95217c723585a7fb6cd2f2864cb7abbc21527cf8a6bc0e8361c83`. `tools/build_incremental.cmd` completed with exit 0 and linked the executable. The final eight-second trace is `generated/logs/startup-lfq-validation-final-stderr.log`; initializer and explicit-failure gates passed. Five public-audit tests passed; `build/public-source-lfq-final-2/` passed the release-tree audit. The workspace root has no Git index; the nested ps3recomp checkout has no staged files. No proprietary files were deleted or published. No visual validation is required.

| Milestone | Result | Evidence |
|---|---|---|
| Disc identification and targeted extraction | VERIFIED | `original/game/manifest.json`; title ID `BCUS98155`, disc `VERSION 01.02`, `APP_VER 01.00` |
| ps3recomp revision | VERIFIED | Supplied `VERSION.txt` and pinned source checkout: `0fe7dbf5db9a467aca268865fb26170ea113c541` |
| Decrypted ELF | VERIFIED | `generated/decrypted/EBOOT.elf`, SHA-256 `bbb7fe2545e54847483439f59cda54e907db23a111d7afe9a1b655624886b287` |
| PPU function discovery | VERIFIED | 14,437 OPD descriptors, 11,722 unique functions, 386 imports; `generated/logs/ppu-loader-decrypted.json` |
| PPU code generation | PARTIAL | 78 C++ chunks, 53,278 emitted functions; 26 missing-continuation warnings; `generated/logs/ppu-lifter-decrypted.log` |
| SPU discovery and code generation | VERIFIED | 26/26 embedded images lifted and registered; `generated/spu_lifted/inventory.json` |
| Native runtime compilation | VERIFIED | `build/runtime-clang/ps3recomp_runtime.lib` built with Clang 23.1.3 |
| Native PPU compilation | VERIFIED | All generated PPU units compiled; `generated/logs/port-build.log` |
| Native linking | VERIFIED | 26 embedded SPU images plus the raw Wws_Job policy module linked; `generated/logs/port-build-wws-pm.log`. EXE SHA-256 `db03fe3fe991d9b9d827636af78894b12c5a6c8a42313781eacb330d4cf5959a` |
| Original startup code | PARTIAL | Original entry ran, initialized D3D12 at 1280×720, opened and read `MS2.PSARC`, and resolved/executed Wws_Job. A startup SPU task then waited for a signal while a PPU thread waited on event bit `0x0001`; `generated/logs/startup-with-wws-*.log` |

**VERIFIED blocker:** The PPU calls unresolved cellSpurs NID `0x8A85674D` (`_cellSpursLFQueuePushBody`) from guest `0x007285DC` with queue `0x40494E00`, item `0xD00303F0`, and mode 3. The runtime returns without publishing the 32-byte item; task 0 remains in `WAIT_SIGNAL` on that queue. The earlier `+0x30` waiter interpretation was produced by an incorrectly initialized direction-0 queue; the corrected direction-3 consumer registers at `+0x04`. `SPURS_LFQ_TRACE=1` captures the queue line and item. The separate PPU event flag at `0x40494D80` also remains unset. A correct guest-format ANY2ANY LFQueue push, commit, and registered-task notification is now the next implementation step. No wake or queue item has been fabricated. Menus and gameplay remain unverified.

Latest verification: `generated/logs/build-spurs-lfq-trace.log` linked successfully; final 8-second probe `generated/logs/startup-lfq-final-stderr.log` repeated the unresolved PushBody call, task 0 wait, and PPU event-flag wait. Native startup did not advance beyond the previous milestone.

## 2026-10-18 LFQueue investigation update

- **VERIFIED:** The initializer now writes the guest ANY2ANY empty state: zero producer/consumer control words, `size` at `+0x10`, `depth` at `+0x14`, marked buffer pointer at `+0x18`, direction 3 at `+0x24`, `v1=0xFFFFFFFF` at `+0x28`, and empty waiter packs at `+0x30/+0x50`. It validates alignment, size, depth, direction and guest ranges. The original lifted SPU consumer at LS `0x9C04` reads `+0x24`, takes its direction-3 path, commits `GETLLAR/PUTLLC` on the queue line, and registers a waiter at `+0x04`.
- **VERIFIED:** Native build/link succeeded (`generated/logs/build-lfq-final.log`), latest EXE SHA-256 `93cc49a812f50ee4d7a5922f5d7533c6670eaef47407404ebc931d962b8ec15b`. `tools/test_spurs_lfqueue_init.py generated/logs/startup-lfq-init-final-stderr.log` passed. The final seven-second startup probe still reaches unresolved PushBody, task 0 `WAIT_SIGNAL`, and PPU event-flag wait.
- **BLOCKED:** `_cellSpursLFQueuePushBody` has argument/queue validation and an explicit unsupported result, but no producer operation. The SPU consumer confirms layout and waiter registration, but does not reveal the PPU producer reservation, commit, notification and full-queue protocol. The available reference implementation also leaves direction-3 push helpers unfinished. Single push/pop, wrap, full, concurrency, and notification tests remain pending until those rules are established. Menus and gameplay remain unverified; no visual validation is required.

## 2026-10-18 reference-call attempt

- **VERIFIED:** A private RPCS3 GDB harness attached to the user-supplied full ISO and set a breakpoint at the original PPU PushBody call, guest `0x007285DC`. RPCS3 recognized title `BCUS98155` and firmware loaded, but this reference run froze first at guest `0x00531338` with a null-memory read. The same failure occurred when booting the locally decrypted ELF. No PushBody before/after queue state was captured. Private traces remain under `generated/firmware_analysis/`.
- **VERIFIED:** An unchanged 8-second native probe, `generated/logs/startup-lfq-20261018-ref-blocked-stderr.log`, still resolves PushBody to explicit unsupported, leaves task 0 in `WAIT_SIGNAL`, and leaves the separate PPU event flag blocked. `tools/test_spurs_lfqueue_push_pending.py` passed against that log. No native runtime code was changed or rebuilt in this attempt.
- **BLOCKED:** The reservation, commit, and waiter notification transition is still unverified. Do not replace the explicit unsupported result with a guessed success. The next decisive experiment is a standalone PS3-side direction-3 LFQueue test that calls the firmware export with a registered SPU waiter and records queue/ring/task state before and after, or a corrected reference boot that reaches the original call.
- **VERIFIED:** The direction-3 initializer regression passed after an 8-second probe with `SPU_LFQ_ATOM_EA=0x40494E00` enabled (`generated/logs/startup-lfq-20261018-init-regression-stderr.log`); this address is a diagnostic filter only.

## 2026-10-18 isolated producer analysis

- **VERIFIED:** Private firmware analysis identifies `+0x08` as the atomically reserved producer word and `+0x0E` as its 16-bit reservation cursor. In the empty direction-3 state, static control flow advances cursor 0 to 1 modulo twice the depth. The original wrapper copies to `(buffer & ~1) + size * (cursor modulo depth)` before a distinct atomic commit. See `docs/RESEARCH.md` for the partial field map.
- **VERIFIED:** Original SPU image `spu_cbf1b1a19a3f3eb95183a55e5b65c2de6eef9e025fed16eed2a0a8f1c563dd6f` contains the direction-3 consumer path at LS `0x9C04`, and the native trace confirms waiter registration at `+0x04`.
- **BLOCKED:** The commit state with a registered waiter and the callback that signals the SPU remain unverified. The public PushBody handler still returns explicit unsupported for a valid push. No native runtime code was changed or rebuilt, and startup has not advanced.
- **BLOCKED:** No local PPU/SPU PS3 compiler or PSL1GHT installation is available to build a valid isolated firmware fixture; bundled LLVM lacks a PowerPC target. The smallest decisive experiment requires a real SPURS taskset, waiting consumer and one original firmware push under a locally built PS3 test.
- **VERIFIED:** Existing regressions rerun: `tools/test_spurs_lfqueue_init.py generated/logs/startup-lfq-20261018-init-regression-stderr.log` passed; `tools/test_spurs_lfqueue_push_pending.py generated/logs/startup-lfq-20261018-ref-blocked-stderr.log` passed. A new source-only staging under `build/public-stage-20261018-isolated-lfq` passed the public-source audit. No new native startup probe was run because no runtime code changed.

## 2026-10-23: garage-read validation run (one authorized extended run)

Run `generated/runs/20261023-134457-garage-read/`: exe `8bc4932e…`, intro skip, native audio, `FS_CALLER=1`, `PS3_FSLOG_READS=5`.

**VERIFIED:**
- `track_garage.rpk` (23.2 MB stored, 764 zlib blocks) was read in full from `MS2.PSARC`, 31.8–34.2 s, with no short reads and no errors.
- The run stopped at `garage_world_read_complete` (34.26 s), while reading `Track0a_Garage_Sky1_driver.rpk`.

**Not shown:** decompression, parsing and the next rendering stage.

The emblem white-to-black behaviour was not reached. Details: `docs/NEXT_GARAGE_VALIDATION_RUN.md`.

## 2026-10-25: exposure readback watch run (one authorized run, new machine)

Run `generated/runs/20261025-100328-garage-rtrb-watch/`: exe `a9553e30…` (ps3recomp-int `61fed2d`), `RSX_RT_READBACK=1`, watch `06A1E400,02903600`, `RSX_RTVIS=06A1E400,0x800,max=6000`, `VP_NOFIXPROJ=1`, intro skip. Stopped at `[rtvis] summary reads=1200` after 58.6 s; no fatal, watchdog or GPU-timeout line.

**VERIFIED:**
- Exposure surface `0x06A1E400` (16x16 FP16, EA `0xC6A1E400`) was created once (res 26, never evicted, resized or GPU-sampled), selected at gen 3 and applied every frame (`nz=512/512`, no skips). Control `0x02903600` behaved the same way.
- `func_004C3778` reads `+578` nonzero from read 28 (237 of 242, FP16 about 0.002-0.007). Reads at `+1322/+1362/+1426/+1514` stay `0x0000`. The earlier rtrb2 run read zero at `+578` through gen 50.

**Not shown:** whether the zero offsets match the GPU texels, and the garage image (no capture in this run).

## 2026-10-25: garage capture and exposure probe run (one authorized run)

Run `generated/runs/20261025-102805-garage-capture-probe/`: exe `96d9dee1…` (ps3recomp-int `307b08a`), `RSX_RT_READBACK_PROBE=06A1E400:242/52A/552/592/5EA`, RSXI `targets` capture (4 frames, mindraws 600, stride 70). Stopped at the RSXI capture-complete line (frame 2064) after 62.5 s; no fatal, watchdog or GPU-timeout line.

**VERIFIED:**
- Four garage frames were captured (1854, 1924, 1994, 2064; 619-637 draws each). In all four the presented image shows recognizable garage geometry (dome frame, rider) under the UI, but very dark. It is not black and not overexposed.
- The scene RT `0x01DD0000` (RGBA8, 1280x720) is already dark before compositing (max about 53/255).
- In 11 probe lines (copies 1-8, 65, 129, 193), `+0x242` matches across GPU staging, converted payload and guest memory after the copy, and guest reads of `+578` return the same values in order. The other four offsets are `0x0000` already in GPU staging. Guest reads see the previous frame's copy (`flips_since_write=1`), with no inconsistent values.
- Garage runs at about 13 fps between captures. Each capture causes a 1.5-2.3 s pause (meta 0.8-2.0 s).

**Not shown:** why the zero texels are zero on the GPU. `+578` read zero for gens 165-181, which falls between probe samples.

**Offline follow-up (RSXI op logs, frames 1854-2064, no launch):**
- VERIFIED: the exposure chain is: op 523 `fp_0074B181` (four taps of scene MRT1 `0x01650000`, averaged, squared, ×16) → `0x02195900` (320x180 FP16) → ops 524-528 `fp_0074AB41` (single-tap copies down to 10x5 `0x022C1600`) → op 603 `fp_0074C781` → `0x06A1E400`. Every draw has a full viewport/scissor, blend off and cmask 15.
- VERIFIED: the scene shader `fp_067F5981` writes MRT1 = COLOR0 × 0.0625 (RGB), so dark RGBA8 pixels quantize to 0.
- VERIFIED: in op 603, G = sqrt(lum/vp_c[33].x) and R = 0.7/max(min(G,10),0.02) + 0.3, so lum≈0 gives R = 35.3. This equals readback word0 `0x5069` (35.28) and the CPU-fed `vp_c[33].x` = 35.3 (3.4 in frame 1854). The scene VS passes `vp_c[33].x` as tc6.y, which the scene FP multiplies into COLOR0.
- Conclusion: the exposure feedback works and sits at its maximum. The scene is dark even at ×35.3, so pre-exposure scene colour is about ≤0.006. HYPOTHESIS: the darkness is upstream of exposure (lighting or texture inputs of the scene pass).

**Offline follow-up 2: scene shader `fp_067F5981` (105 draws per frame, ops 336-440, all four frames):**
- VERIFIED: the bindings and fp constants are identical across all 105 draws and all four frames. Vertex shader `vp_9158278F`; blend off.
  - Textures: u0 DXT1 1024² (albedo); u1 A8R8G8B8 1×1 (sign-expanded normal); u10 FP16X4 4×1 (cascade scale/offset); u11 X16 256×1 (sampled `.w`, remap `0x02EE`); u12 Y16X16F 32×512; u13 shadow depth `0x06FF0000`; u14 DXT1 256² (SampleLevel); u15 DXT1 32².
- VERIFIED (ALU in the dumped HLSL):
  - Sun term = albedo × `(0.02,0.01,0)` (fp const 16, the same value as vp c40) × (1−tc6.x) × saturate(N·L).
  - Shadow = mean of 3 u13 taps (lines 165/204/216).
  - The ambient/env term (u14, u15, albedo) is scaled by `col0.z` = `v3.w × vp_c[38].x` (fp line 142, vp line 47).
  - The result is multiplied by tc6.y = `vp_c[33].x` (35.3).
  - So directly sun-lit pixels give at most about albedo × (0.71, 0.35, 0): orange, with no blue. This matches the captured image (orange/red highlights, the rest black) and the scene RT peak of about 53/255.
- HYPOTHESIS: the ambient/env contribution is about zero. Candidates are the vertex colour `v3.w`, `vp_c[38]`, `vp_c[35]` and `vp_c[57]`, and u14/u15 contents. A wrong shadow compare or the u11 remap would affect only the sun term or fog.
- Uncertainty:
  - RSXI writes only the first 32 non-zero VP constants (`RSXI_VP_CONSTS`, default 32; 243 are non-zero), so c35/c38/c57/c466/c467 are not recorded.
  - The dumped HLSL is decompiled without the live texture state (no depth compare, remap or gamma), so u13/u11 fetch behaviour cannot be judged from it.
  - Vertex attribute formats are not recorded.
  - No mid-pass snapshots exist (end-of-frame only; `0x01650000` is overwritten by op 596).

**Offline follow-up 3: v3.w, attribute format, c35/c38/c57 (existing artifacts only, no launch):**
- Correction to follow-up 2: c35 and c38 *are* determined by the capture. RSXI writes the non-zero VP registers in ascending index order (`rsx_d3d12_backend.c` ~5668-5676, from the per-draw host VP constant buffer). Every one of the 105 scene draws in all four frames lists registers up to index 51 and omits 35 and 38, so both were all-zero at draw time.
- VERIFIED (host constant state): `vp_c[35]` = 0 and `vp_c[38]` = 0 for all 420 scene draws, in frame 1854 (`vp_c[33].x` = 3.4) as well as later (35.1-35.3). No other draw in the four frames has a non-zero c35 or c38 either.
- Consequence, per the dumped VS: tc6.x = c35.x = 0, so the sun factor (1−tc6.x) = 1. col0.z = v3.w × c38.x = 0 (vp line 47), so the FP's ambient/env term (scaled by saturate(col0).z, fp line 142) is zero whatever v3.w holds.
- Not in the artifacts: `vp_c[57]` (above the recorded index 51), the value of `v3.w`, and the attribute formats and strides (draw records hold no vertex-input fields; the VS reads ATTR3 as float4).
- Status of the ambient explanation: PARTIAL. The zero ambient follows from the recorded c38 = 0 through the decompiled VS/FP. **Unverified:** whether the guest meant c38 to be zero (scene data / time-of-day) or whether a constant upload is being lost or misplaced in the host path, and the decompiler's mapping itself. Do not patch c38 or the exposure.
- Proposed next capture (requires new authorization; not run): the same bounded garage capture with `RSXI_VP_CONSTS=512` and `RSXI_SNAP=passes`, plus a trace of guest VP-constant uploads that touch register 38 (writes to the transform-constant load slot). Recording vertex attribute formats would need an inspector change, which also needs approval.
