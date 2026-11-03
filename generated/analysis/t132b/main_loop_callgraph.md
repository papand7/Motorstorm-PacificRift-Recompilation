# T132b: one iteration of the MotorStorm PR main loop `0x82358` (static, retail EBOOT)

Read-only static analysis: nothing was built or launched. The inputs were `generated/decrypted/EBOOT.elf`, the developer build
`c38/rv/resourceviewer.elf` and its `symbols.txt` (used for engine names), and earlier notes: t132, t84 (visibility),
garage_menu (pad), and the exposure entries in `docs/STATUS.md`. The scripts are in `t132b/tools/` and reuse
`t132/tools`. The derived data is:
- `retail_devnames.json`: 3127 retail functions matched to developer names by masked signature;
- `vtables.json` / `vtable_rtti.json`: 1305 vtables, named from RTTI;
- `graph.pkl`: the direct call graph;
- `gstack_chains.txt`: the runtime stack chains found in existing logs.

Labels: **VERIFIED** = seen in code (or in an existing runtime stack); **PARTIAL** = only part is seen;
**HYPOTHESIS** = inferred.

## 0. Objects the loop uses (app = r26 = `new(0xE780)` at 0x13D14; ctor 0x6AE98, init 0x61988/0x47098)

| Field | Object | Evidence | Label |
|---|---|---|---|
| app+0x40 | **ms2Rendering** (vtable 0x103CF48) | 0x47388 stores the result of 0x355608, which builds vtable 0x103CF48 (0x351118). A runtime stack has 0x8299C+0x1B4 → 0x34CDE8, which is slot 0x44 | VERIFIED |
| app+0x44 | **Ms2Audio** (0x1034938) | 0x473D0 ← 0x101EC0 → ctor 0x7CB758 | VERIFIED |
| app+0x4C | **ms2Physics** (0x103BFD8) | 0x47574 ← 0x3104C8 → ctor 0x8D5228 | VERIFIED |
| app+0x130 / +0x140 | app `Timer` / its step (dt) | t132 | VERIFIED |
| app+0x16C | trails / JobBatchHandler object (strings "trailsupdate", "Trails", "RipplesGeneric") | ctor 0x3A10D0, stored at 0x47564 | PARTIAL |
| app+0x170 | **GameParticleSystem** (0x1037748) | ctor 0x23C360 stores the vtable at obj+0 (0x23C3DC) | VERIFIED |
| app+0xBF58 | game **World** (no vtable; clock object at +0x28) | stored at 0x48250 (ctor 0x212D48); passed as r3 to `World::Update` 0x216008 from 0x6CDF4 | VERIFIED |
| app+0xBF40 | **Ms2Online** (0x1037ED8) | 0x47A54 ← 0x2814B0 | VERIFIED |
| app+0xDB4C | **ms2GameScene** (0x103CB98). The frontend may get MinimalSceneRenderWrapper | created by `ms2Rendering` slot 0x1C (0x350050 → 0x3352B0 / 0x35A408) at 0x38480 | VERIFIED (factory); per-state type PARTIAL |
| app+0xDB20 | list of local views (players), iterated per frame | 0x829DC… | PARTIAL |
| `*0x1268A50` (G) | online singleton. Its slots reach 0x970, so it must be `evo::online::cOnline` / `cOnlineNP` / `cOnlineOnline` (the only vtables with more than 0x25C entries) | vtable sizes | PARTIAL |
| `0x1238930` (r25) | capture state: request byte, face 1..6, mode | loop code. Use for light-probe cubemap capture is HYPOTHESIS: `ms2Rendering` slot 0x14 references "/app_home/lightprobes/" | VERIFIED code / HYPOTHESIS meaning |

The game-state stack at app+0xBF84 holds 0x20-byte entries, which are 4 delegates `(obj, OPD)`:
- d0: enter;
- d1: per-frame update;
- d2: exit;
- d3: isDone.

The loop copies the top entry to app+0xBF64..0xBF80 (0x82438–0x82474). In the 5-function state groups (garage_menu), the
per-frame update is race **0x6CC98** and garage **0x41488**. Both call `World::Update` 0x216008. **PARTIAL:** I did not
trace how a group maps onto d0–d3. The garage enter path, however, is in a runtime stack:
0x82420+0xEC → 0x7804B0 → 0x82308 → 0x82188.

## 1. Annotated call graph of one iteration (loop head 0x82560, back edge 0x82D7C)

`dt` = seconds(app+0x140) (f30). `wstep` = seconds(World clock +8), the **previous** world step (f31). Class columns:
**SIM** = must run exactly once per sim tick. **REN** = render-only. **MIX** = render-side, but advances time-based
state with dt. **SYS** = platform or online.

| # | Site | Call (resolved) | What | Class | Label |
|---|---|---|---|---|---|
| 1 | 0x82580 | G->vt[0x144]() (if true: G->vt[0x528]() → `*0x1268B98`) | online status poll | SYS | VERIFIED call; meaning HYPOTHESIS |
| 2 | 0x825A8–0x825C8 | 0x206D40(World+0x28)+8 → `Time::GetSeconds` 0x434D00 ×2 | reads wstep and dt | — | VERIFIED |
| 3 | 0x825F4 / 0x8260C | `ms2Rendering`->vt[0x28]() (scene) → **0x238570**(GameParticleSystem, dt, wstep, scene) | particle update: rate ratio = wstep/scene->vt48(), clamped to 1 → 0x490568 | MIX | VERIFIED call/object; HYPOTHESIS that it is purely visual |
| 4 | 0x82634–0x8269C | scene->vt[0x40]() → World+0x708 = min(wstep/x, 1) | world/render time ratio | MIX | VERIFIED |
| 5 | 0x826A8 / 0x826C0 / 0x826C8–0x82728 | 0x253440(app[0xDAD0]); 0x20D090(World); 0x252A18() → 0x252F88(obj, wstep/k) | singleton time-scale updates (0x252A18 is also used by pause) | ? | VERIFIED calls; meaning unknown |
| 6 | 0x82764 | G->vt[0x8B0](G, delegate{app, OPD 0x107C148}) | online per-frame pump | SYS | VERIFIED call |
| 7 | 0x8276C | **0x436420 `evo::kernel::frameStart()`** (cellSpursGetWorkloadInfo) | frame start, SPU profiling | SYS | VERIFIED (dev match) |
| 8 | 0x82774 | 0x5C6CD0 → 0x72DFA8 per list item | deferred GcKernel resource release | REN | PARTIAL |
| 9 | 0x827A0 | **`ms2Rendering`::BeginFrame 0x3463F8 (slot 0x08)**(app Timer): `RenderSystemATG::Begin` 0x50D4B8 (slot 0x0C; lwmutex lock, opens the command buffer, no ref poll), 0x4E0980, 0x4DB0D8, 0x4C3728 (render state) | starts RSX command generation | REN | VERIFIED |
| 10 | 0x827B4 | app[0x16C]+0x44 = seconds(app+0x138) | trails time | MIX | VERIFIED |
| 11 | 0x827F0 | scene->vt[0x30](dt) = 0x3309C0 → 0x39DE38 | scene pre-update | MIX | VERIFIED call |
| 12 | **0x82804** | **0x19AC0(app,0) → 0x1C2CA8 → 0x729250 → 0x72B530 pad update** | **input: consumes the FpPadThread ring** | SIM | VERIFIED |
| 13 | **0x82824** | **d1: state update.** In a race, 0x6CC98 → 0x2FE80(app, &ctl) builds control input, then **`World::Update` 0x216008**(World, &ctl, mode) | **game/world tick** (below) | SIM | VERIFIED (race/garage path) |
| 14 | 0x8282C | 0x457B88 → 0x4E6EF0 | per-frame linear allocator reset (records the high-water mark) | REN | PARTIAL |
| 15 | 0x82860 | scene->vt[0x44]() = 0x330940 → 0x45B8A0 / 0x45B788 | scene-list maintenance | MIX | PARTIAL |
| 16 | 0x828A8–0x828A0 | r25 capture state machine (face 1..6) | debug/capture | REN | VERIFIED code |
| 17 | 0x8290C | **scene->vt[0x34](scene, `ms2Rendering`->vt28(), dt, face) = 0x331240** | **visibility/cull kick**: per view × 24 scene lists → `KickVisibility` → `pvsjob` SPU batches (t84 §9.1) | REN (but receives dt) | VERIFIED |
| 18 | 0x82918 | 0x24AC60(app[0xDB0C]) | sceNp manager polling | SYS | VERIFIED imports |
| 19 | 0x82940 | **`Ms2Online`**->vt[0x24]() | online game update | SYS/SIM in online play | VERIFIED object |
| 20 | 0x82984 | 0x2EAAC8(app[0xDC28], G->vt970()) | NP id compare (lwmutex) | SYS | VERIFIED imports |
| 21 | 0x82994 / 0x82FD4 | if byte app[0xE75C]: 0x3DA90 → 0x2F218 **App::SetPaused** | pause request | SIM-state | VERIFIED |
| 22 | 0x829A0 | 0x238998(particles) | particle frame begin | MIX | VERIFIED call |
| 23 | 0x829D4 | **`Ms2Audio`::vt[0x20](app Timer) = 0x7C9F70** | audio update | SIM-coupled (should run once per tick) | VERIFIED object/slot |
| 24 | 0x82A20–0x82C30 | **per view** (app+0xDB20 list): 0x1E6270(app[0x5C][i],1/0); 0x23BA38(particles, view) (camera bounds "Camera%d"); **`ms2Rendering` vt[0x3C](view, scene, dt, face, 0) = 0x348A30**; **vt[0x44](view, i>0, n>2) = 0x34CDE8 post-effects** (at its top: **exposure readback 0x4C3778**, reading `0x07EBA600` = the previous frame's op 603); vt[0x40](view) = 0x34B230; vt[0x74](view) = 0x34ADB8; vt[0x68] = 0x359EF0 | per-view scene render, renderable families (`Vis::Wait` 0x45CAA8 → `PVSComputerImpl::WaitForCompletion` 0x5F74B0) → `ExecutePushBuffer` 0x50D868 → renderablejob SPU → FIFO | REN | VERIFIED structure and 0x34CDE8/0x4C3778; other slot semantics PARTIAL |
| 25 | 0x82C40 | 0x238900(particles) | particle frame end | MIX | VERIFIED call |
| 26 | 0x82C84 / 0x83008 | `ms2Rendering` vt[0x70] (0x346228) or vt[0x6C] (0x359BF8) | finish views | REN | PARTIAL |
| 27 | 0x82C9C | **0x810D8(app)**: GUI/frontend ("RACE", "PAUSE", "PHOTO", "GARAGE", gui/%s.gui) | GUI logic and GUI draw | MIX | PARTIAL |
| 28 | 0x82CA4 | 0x32508(app): message/dialog queue (cellMsgDialogAbort) | system UI | SYS | PARTIAL |
| 29 | 0x83014 / 0x83090 | app[0xDF54]==1: `ms2Rendering` vt[0x10] (0x346AD8, "output.jpg") screenshot; r25 mode: vt[0x14] (0x350658, light probes) | captures | REN | VERIFIED strings |
| 30 | **0x82CF0** | **`ms2Rendering`::EndFrame 0x346A40 (slot 0x0C)**(app Timer): `RenderSystemATG::End` 0x50B8B0 (slot 0x10), then `rs[+0x3B4]`->vt[0x14] = **`DisplayATG::Present` 0x5226A8** → 0x522950 → `GcKernel::Present` 0x72E518 → **ref poll 0x72E1E0** (waits for frame N−1) → flip 0x7515B4; GET_REPORT/ZPASS 0x733880 | **Present/flip** | REN | VERIFIED |
| 31 | **0x82D0C** | **`Timer::Step` 0x435F28(app+0x130)** | next dt (fixed 1/30) | SIM | VERIFIED |
| 32 | 0x82D14 / 0x82D1C | 0x32DE28 (bare `blr`); 0x4AAF70 **`evo::multiprocessor::CleanupPerFrameJobMemory()`** | job memory recycle | REN/SYS | VERIFIED (dev match) |
| 33 | 0x82D44 | app[0xDB14]->vt[0x10]() | unknown per-frame object | ? | VERIFIED call |
| 34 | 0x82D6C | d3: isDone → loop or exit (d2) | state machine | SIM | VERIFIED |

### `World::Update` 0x216008 (called once per iteration from the state update; VERIFIED unless marked)

1. 0x209B20(World+0x28): steps the **world clock** (two `Timer::Step`s at +0 and +0x20). A flag pair at +0x40/+0x41
   handles pause, and (HYPOTHESIS) a single-step-while-paused debug feature.
2. **`wdt` = seconds(clock+8)**, clamped to **≤ 0.04 s** (fsel at 0x2161C8).
3. G->vt148() (online check), then 0x215268.
4. Per vehicle: **0x214250**(World, vehicle, wdt). This is the vehicle update (input, AI, character); the inner content is
   PARTIAL.
5. 0x20E088; World[0xDC]->vt2C(); if `wdt > 1e-5`: 0x10D6C8(World[0xDC]).
6. **World[0xDC]->vt[0x1C](wdt) = `ms2Physics::Update` 0x8CF1C0.** This runs the 60 Hz tick converter 0x31BA20,
   then **one Havok step 0x30B710** (multithreaded hkp; it waits on its own SPU jobs), then 0x4158D0 (16 per-subsystem
   slot-0x1C updates).
   - The arguments match `ms2Physics` (`dt` in f1, skip when < 1e-5). `World[0xDC]` itself is PARTIAL: it is not
     tied by a store to the app+0x4C object.
7. Then: many per-competitor updates (0x12A038 ×8, 0x152B98 ×8), particles/trails (0x44DD10 ×4), and online
   (G->vt144). The suspension, tyre, collision, AI, animation and camera code sits in these callees and in `vt` calls
   on game objects; I have not mapped it individually (PARTIAL).

## 2. Answers

**(a) Is there a clean split between update and render?** There is no single call that separates them, but the
order is strictly sequential on one thread: `BeginFrame` (9), then input (12), the sim tick (13), visibility kick (17),
audio (23), per-view render (24), GUI (27), and `EndFrame`/Present (30). **VERIFIED.**
- The authoritative sim tick is one call: **d1 at 0x82824**, which reaches `World::Update`. Next to it, the following
  must also run once per tick: input 0x82804, pause 0x82FD4, `Ms2Audio` 0x829D4, `Ms2Online`/G pumps, `Timer::Step`
  0x82D0C and isDone 0x82D6C.
- Render-side code also consumes time.
  - **MIX** calls receive dt or wstep: particles (3, 22, 25), scene vt30/vt34 (11, 17), `ms2Rendering` vt3C (24),
    trails time (10), and the world+0x708 ratio (4).
  - Running the render half twice per tick would advance those visuals twice unless it is called with dt = 0.
    **HYPOTHESIS** (dt is passed; what each callee does with it was not traced).
- No sim consumer of GPU-written data was found.
  - **Exposure readback** 0x4C3778 is reached only from the post-effects slot 0x34CDE8 (render; STATUS: one frame of
    latency, no wait).
  - **ZPASS reports** are issued in Present (0x733880) and gated by label 0x48 (render/occlusion).
  - **ctrl->ref** is only used for pacing.
  - **PARTIAL:** I did not prove that no sim path reads report or label memory.
  - Visibility (`pvsjob`) is kicked in (17) and waited on inside the renderers (24), so skipping render also requires
    skipping the kick. HYPOTHESIS: the sim does not use PVS output.

**(b) Does it wait on the GPU before the update?** No, only in Present. **VERIFIED for direct calls.**
- 0x72E1E0 has 5 direct callers:
  - `GcKernel::Present` 0x72E518 (loop step 30);
  - `DisplayATG` slot 0/1 (destructors);
  - the loading-screen render thread 0x329410 (OPD 0x1088970; not in the loop);
  - teardown 0x72EFF0.
- `RenderSystemATG::Begin` takes an lwmutex but does not poll ref.
- The wait at the end of iteration N waits for frame N−1's ref, so the update of N+1 overlaps RSX work on N.
- Other in-frame waits are SPU job batches, not the GPU:
  - `JobBatchInternal::Wait` = vtable 0x103F718 slot 0x1C = 0x4AACA0;
  - `PVSComputerImpl::WaitForCompletion` 0x5F74B0, used by the renderers;
  - the internal Havok step.
- `cellSpursEventFlagWait` is reached only from the audio system (0x5D5160 / AudioSystem slots 0/1) and Edge
  decompression, not from the loop body. PARTIAL: virtual paths were not exhaustively excluded.

**(c) Is there a render-only path or double-buffered state?**
- **Pause** (VERIFIED): `App::SetPaused` 0x2F218 pauses the app Timer (`Timer::SetPaused` 0x4360A8) and both world
  clocks (0x209AA0) when offline. In online play it only calls `Ms2Audio`->vt54.
  - The loop keeps running every step with dt = 0.
  - `World::Update` then skips the physics work (`wdt ≤ 1e-5`) while all render steps still run.
  - This is the existing render-only frame.
- **Photo mode:** strings `TogglePhotoMode`, `PhotoConfig`, `enableCameraWhilePaused`, RTTI `ViewObtainerPhotoMode`
  and `ViewObtainerReplay`, `VehicleRecorder`. So the camera can move while the sim is paused. **PARTIAL:** the strings
  and classes exist; the code path was not traced.
- **No previous/current interpolation of sim state was found.**
  - The only history is render-side motion-blur parameters (`worldviewprevious`, `modelviewprojectionprevious`,
    `viewProjectionMatrixPrevious`, `VelocityExtrapolationSetup`). **VERIFIED strings**; whether every object keeps a
    previous matrix is HYPOTHESIS.
  - The renderer reads transforms the update wrote in the same iteration directly. There is no snapshot. **HYPOTHESIS
    (strong):** single thread and strict order; the visibility block copies camera matrices at kick time (t84).
  - GPU command buffers alternate on frame-counter & 1. That double-buffers GPU commands, not game state.

**(d) Is input sampled once per iteration?** Yes. **VERIFIED.**
- The pad is polled on its own thread: `FpPadThread` 0x72ADF0 (`cellPadGetData` into a 20-slot ring).
- The main thread consumes it exactly once per iteration at **0x82804** (0x19AC0 → 0x1C2CA8 → 0x729250 → 0x72B530),
  before the state update.
- The race update then builds the control block 0x2FE80 for `World::Update`. **PARTIAL.**
- 0x19AC0 also runs inside the loaders 0x85EF0 and 0x8EA00, which are outside the frame loop.

## 3. Implications for 60 fps rendering (HYPOTHESIS)

- Interpolated extra frames would need three steps:
  - run steps 9–10 and 15–30 with dt = 0 (the pause model), but without `Timer::Step`, audio, online or GUI-logic
    side effects;
  - re-kick visibility;
  - interpolate the transforms that the renderables read.
- No previous-state buffer exists, so the port would have to snapshot the transforms at the end of d1.
- Particles, trails and post-fx adaptation are dt-driven and would need dt split across the sub-frames.
- Present's ref poll and label-0x48 gate are per Present, so two Presents per tick would pace at the vblank gate.

## Tools (in `t132b/tools/`)

| Tool | Purpose |
|---|---|
| `common.py` | shared setup, `fend` |
| `buildmap.py` | builds `retail_devnames.json` |
| `names.py` | names and demangling |
| `cg.py` | calls in a function, vtable slots, strings |
| `graph.py` | direct call graph |
| `up.py` | caller tree with vtable membership |
| `tree2.py` | callee tree |
| `summ.py` | subtree strings and imports |
| `vtables.py` / `rtti.py` / `vtdump.py` / `devvt.py` | vtable scan, RTTI names, retail and developer vtable dumps |
| `vtrefs.py` / `vtxref.py` | find constructors |
| `fieldw.py` | field writers |
| `slotcalls.py` / `slotf1.py` | virtual call sites |
| `fuzzy.py` | prefix-match against the developer build |
