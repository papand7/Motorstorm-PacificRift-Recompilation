# Player settings: one file, `settings.ini`

For the launcher, the in-game PC Settings pages and the port (`port-vkgame/pc_settings.h`, `pc_keys.h`, `pc_pages.h`, `pc_menu.cpp`, `main.cpp`; the racing-wheel layer is `ps3recomp-vkgame/libs/input/pad_wheel.h` and `pad_wheel_dinput.h`). Contains no game data. Status of every claim below: see the end.

## The file

`settings.ini` sits beside the game exe (the launcher's `MotorStorm` folder). Plain text, one `key = choice` per line, `#` or `;` for comments, any case, spaces around `=` ignored, CRLF fine. A choice is its label (`1080p`, `Ultra Quality`) or its value (`1.5`, `ultra`). Unknown keys, unknown choices and unreadable lines are ignored, so a newer file loads in an older exe. A key that is missing means "the default".

The port **owns** the file: the in-game page rewrites all of it on every change (comments and unknown lines are dropped). Anything else that writes it must read it, change the keys it knows and write the whole file back (write `settings.ini.tmp`, then rename over it).

| key | page | choices (default marked *) | what it drives |
|---|---|---|---|
| `display` | Display | Windowed*, Fullscreen | `PS3RECOMP_VK_FULLSCREEN` 0 / 1 |
| `resolution` | Display | 480p, 720p*, 1080p, 1440p, 2160p | `RSX_RES_SCALE` 0.667, 1, 1.5, 2, 3 (480p: the video-out reports a 480p widescreen TV and the game renders at 720x480; use it with the upscaler) |
| `vsync` | Display | On (1), Off* (0) | `RSX_PRESENT_INTERVAL`. The port's default is 0 (`k_defaults`): a non-blocking, tear-free present (Vulkan MAILBOX; FIFO on a surface without it). On sets 1, the blocking FIFO present |
| `dynres` | Display | On, Off* | MSPR patch `drs` when Off (the game's own resolution drops are suppressed) |
| `screens` | launcher Display (no in-game row: the Display page is full) | Single*, Dual, Triple (or 1, 2, 3) | `PS3RECOMP_VK_SPAN` 2 / 3 (nothing at Single), read at start (restart). One borderless window over two or three side-by-side monitors of the same height and top, or over one NVIDIA Surround / AMD Eyefinity display that wide (`libs/video/rsx_multiscreen.h`). The view is widened by the window's aspect over 16:9 (Hor+, same vertical field; 1.00 lens hook `screens_patch_lifted.py` in `PATCHES_100`); HUD and menus stay 16:9 on the middle monitor (of two: the one the cursor is on at start); frames without a 3D scene (menus, loading, movies) are pillarboxed there. Overrides `display` (the span window is always borderless). The in-game page keeps the line when it rewrites the file. Experimental: see `generated/analysis/multiscreen/RESULTS.md` |
| `framerate` | Display | 30 FPS*, 45 FPS, 60 FPS, 80 FPS, 120 FPS, 144 FPS, 180 FPS (above 30: experimental) | `PS3_SIM_PACE_HZ` 30 / 45 / 60 / 80 / 120 / 144 / 180 and `MSPR_CAM_MODE` 0 / 1 / 1 / 1 / 1 / 1 / 1 (camera fix on above 30). `vfps` is in the MSPR patch list for every choice. Old files: `Variable` and `60fps` read as 60 FPS; the old `60fps` patch is gone. Measured clean at 45 to 60 Hz with `RSX_PRESENT_INTERVAL=0` (the default) |
| `fsrmode` | Upscaling | FSR 1*, FSR 3.1 | `RSX_FSR_MODE` 1 / 3. **Always set**, also at the default (see below) |
| `fsr` | Upscaling | Off*, Ultra Quality, Quality, Balanced, Performance | `RSX_FSR` off / ultra / quality / balanced / performance |
| `hdr` | Upscaling | Off*, On | `RSX_HDR` 0 / 1 |
| `motionblur` | Graphics | On*, Off | MSPR patch `mblur` when Off |
| `aniso` | Graphics | Original*, 2x, 4x, 8x, 16x | `PS3_ANISO` |
| `textures` | Graphics | Off*, On | `RSX_TEX_PACK` = `<exe folder>/textures/pack` (not applied when that folder is missing) |
| `pbr` | Graphics | Off*, On | `RSX_TEX_PBR` = 1 (needs a pack with PBR maps) |
| `lod` | Graphics | Lowest, Low, Original*, High, Ultra | `MSPR_LOD_BIAS` +2 / +1 / -1 / -2 and `MSPR_CULL_SCALE` 2.5 / 1.5 / 0.5 / 0.25, and for Lowest `MSPR_SHADOW_RANGE` 120 (the game's 200 m shadow range; `main.cpp` `mspr_dist_f` kind 0) (Lowest and Low: coarser and more culling, a shorter draw distance for scenery and trees, faster, more pop-in; this row is the draw distance setting) (1.00: needs `dist_patch_lifted.py` on the lifted tree; the launcher's lift applies it, with the other hook patches in `launcher/pipeline/lift_motorstorm.py` `PATCHES_100`) |
| `lighting` | Graphics | Original, Enhanced* | `RSX_LIGHTING` 0 / 1, always set. Enhanced (experimental): new lighting, ambient occlusion, screen-space reflections and tone mapping. Both lightings draw the sun shadows world-fixed (below) |
| `shadows` | Graphics | On*, Off | `MSPR_NO_SHADOWS` 0 / 1. Off skips the game's own shadow casters (depth-only draws into the 1024x2048 shadow atlas, `rsx_shadow_off.h`), so no shadow map is built (the world-fixed one included). Reflections are not changed. Shown only with Fidelity Original; with Enhanced it is hidden and its value is kept (not written to the environment). |
| `volfog` | Effects (own page, the fourth hub item) | Off*, On | `RSX_FX_VOLFOG` 0 / 1, read at start (restart). Volumetric fog in the scene pass. Enhanced only: with Fidelity Original the row stays on the page, reads "(needs Fidelity Enhanced)", and sets nothing. The launcher lists it under Graphics. |
| `ruts` | Effects (second row) | Off*, On | `RSX_FX_RUTS` 0 / 1, read at start (restart). Wheel ruts in the scene pass, only where the game lays its own tyre tracks (none in the air). Enhanced only, as `volfog`. The launcher lists it under Graphics. |
| `fxquality` | Effects (third row) | Full*, Light, Minimal | `RSX_FX_QUALITY` 0 / 1 / 2, read at start (restart). Light: no ambient occlusion and no light shafts; Minimal: also no screen-space sun shadows. An effect's own variable (`RSX_FX_AO`, `RSX_FX_SHAFTS`, `RSX_FX_SSSHADOW`) wins. Enhanced only, as `volfog`. |
| `particles` | Effects (fourth row) | Off, Low, High* | `RSX_FX_PARTICLES` 0 / 1 / 2, read at start (restart), set at the default too (the port draws none with the variable unset). Extra Particles: dust, mud clods and water spray kicked up by the wheels where they touch the game's tracked ground, with bursts on landings and hard turns, none from wheels in the air (`ps3recomp-vkgame/libs/video/rsx_particles.h`). An added layer over the Enhanced scene pass, coloured from the ground at the contact point; the game's own particles are unchanged. Low: fewer and a smaller pool. Enhanced only, as `volfog`: with Fidelity Original nothing is set and none are drawn. The launcher lists it under Graphics. |
| `shadowq` | Performance (first row) | High*, Medium, Low | `RSX_SHADOW_TILES_RES` 4096 / 3072 (High: the exe's 6144 host texels = 768 m of 0.125 m texels; 4096 = 512 m, 3072 = 384 m, all past the game's own 300 m fade), and for Low also `RSX_SHADOW_TILES_PCF` 0 (one compare, hard edges) and `RSX_SHADOW_TILES_STATIC` 0 (no stored layer: 288 MB less video memory). Restart. Each variable set in the environment wins on its own |
| `texq` | Performance | Full*, Half, Quarter | `RSX_TEX_DROP_MIPS` 1 / 2 (restart; `ps3recomp-vkgame/libs/video/rsx_draw_engine.c` `eng_tex_drop_levels`): a mipmapped 2D game texture of at least 128 texels on its short side is created without its 1 or 2 finest levels (a quarter or a sixteenth of its memory; the finest level kept is at least 32 texels). Unmipmapped textures (render-target copies, lookup tables, video frames), cubes, volumes and texture pack replacements are never changed. Log: `[tex-drop]` |
| `fxdensity` | Performance | Full*, Reduced, Low, Minimal | `MSPR_FX_SCALE` 0.6 / 0.35 / 0.3, and `MSPR_FX_RAIN2` 0 for Low and Minimal, `MSPR_FX_WHEEL` 0 for Minimal (restart). The game's own particle levels, scaled where it reads them (`launcher/pipeline/lowend_patch_lifted.py`, `main.cpp` `mspr_vq_f`, `mspr_gopt`): `scripts/viewportquality.xml` Particles LodScaleMin/Max and EmissionRateMin/Max and ScreenRush ParticleLimitScalar, and `ms2_GameOptions.cfg` particleEmissionScale; Rain2Enabled (the screen rain layer, off in the game's 2- and 4-player entries) and enableWheelParticles (the wheels' dust and mud). 0.6 and 0.35 are about the game's own 2- and 4-player values. Logs: `[mspr-vq]`, `[mspr-gopt]` |
| `oppdetail` | Performance | Full*, Reduced, Low | `MSPR_VEH_LOD_BIAS` +1.5 / +2.7 and for Low `MSPR_VEH_CULL_SCALE` 1.33 (restart): viewportquality.xml's "vehicle" group (the other cars and their wrecks; the player's own car is the "player" group and keeps its values), the game's own 2- and 4-player values. `main.cpp` `mspr_dist_f`, through the `lod` hooks (`dist_patch_lifted.py`). Log: `[mspr-dist] ... group 3 (vehicle)` |
| `drsfloor` | Performance | 50% (Original)*, 40%, 33% | `MSPR_DRS_MIN` 0.4 / 0.33 (restart): viewportquality.xml ViewportScaling variableScalingMin, the lowest scale the game's own dynamic resolution may use (0.5 for one player). Used only with `dynres = On`: with Off it reads "(needs Dynamic Resolution On)" and sets nothing (`pcs_row_unused`). Log: `[mspr-vq] variableScalingMin` |
| `debris` | Performance | On*, Off | `MSPR_DEBRIS` 0 (restart): viewportquality.xml Debris Enabled, the loose parts that fly off wrecks (the game's `debris_ms2` set: bolts, panels), off in the game's own 4-player entry. **Changes the gameplay feel** (no loose parts to hit or drive over); the info line says so. Log: `[mspr-vq] Debris Enabled` |
| `boostblur` | Performance | On*, Off | `MSPR_BOOST_BLUR` 0 (restart): `ms2_GameOptions.cfg` enableBoostBlur, the radial blur while boosting (the motion blur is the Graphics page's `motionblur`). Log: `[mspr-gopt] enableBoostBlur` |
| `framegen` | Performance (eighth row); the launcher lists it under Upscaling | Off*, Light, On | `RSX_FRAMEGEN` light / 1, read at start (restart); Off sets nothing. One generated frame between two real ones (see "Frame generation" below). Light: the port's own motion-vector interpolation (`ps3recomp-vkgame/libs/video/vulkan/rsx_vk_fg.comp`); On: AMD FSR 3.1 frame generation (`amd_fidelityfx_framegeneration_vk.dll`, FidelityFX SDK 2.4.0 signed runtime, AMD's licence: `THIRD_PARTY_LICENSES.md`). Both need `fsrmode = FSR 3.1` with `fsr` not Off, and `hdr = Off`; the row does not change those, and without them the renderer presents as before and logs why. |
| `prompts` | Graphics | Keyboard*, Controller, Auto | `MSPR_PROMPTS` keyboard / controller / auto: the game's button icons redrawn as key caps of the first key bound to each button (port `pc_prompts.h`); Auto shows keys unless a gamepad or wheel is connected. Applied at once, also after a rebind |
| `wheelmode` | Racing Wheel | Auto*, Any Device, Off | `PAD_WHEEL` auto / any / off. Applied at once (no restart) |
| `wheelrange` | Racing Wheel | Device, 180 deg, 270 deg*, 360 deg, 540 deg, 720 deg, 900 deg | `PAD_WHEEL_RANGE`: wheel rotation, lock to lock, that gives the full stick |
| `wheeldeadzone` | Racing Wheel | 0%, 1%*, 2%, 3%, 5%, 8% | `PAD_WHEEL_DEADZONE` |
| `wheelcurve` | Racing Wheel | Linear*, Soft, Softer, Sharp, Sharper | `PAD_WHEEL_CURVE` 0..4 (exponent 1.0, 1.25, 1.6, 0.8, 0.65) |
| `wheelpedals` | Racing Wheel | Profile*, Separate, Combined | `PAD_WHEEL_PEDALS` |
| `wheelpedaldir` | Racing Wheel | Auto*, Normal, Inverted | `PAD_WHEEL_PEDAL_DIR` |
| `wheelffb` | Racing Wheel | Off*, Centering, Rumble, Both | `PAD_WHEEL_FFB` (off by default) |
| `wheelffbstrength` | Racing Wheel | 20%, 40%, 60%*, 80%, 100% | `PAD_WHEEL_FFB_STRENGTH` (the device's overall gain) |
| `audiothread` | launcher Performance (no in-game row: the Performance page is full) | On*, Off | On keeps `audiothread` in the `MSPR_PATCH` list (the default list has it): the game's audio update runs on its own guest thread, joined at the frame's flip (`port-vkgame/audio_thread.cpp`; 1.00 call site 0x000829D4, `mspr_patch_lifted.py`). Off takes it out (`pc_settings.h` `pcs_mspr_drop`), read at start (restart). A set `MSPR_PATCH` wins. See `generated/analysis/cpu_placement/RESULTS.md` |
| `threadplace` | launcher Performance (no in-game row) | Off*, Auto | Auto sets `PS3_CPU_PLACEMENT=auto` (unless set), read at start (restart): on a CPU with fast and slow cores (Ryzen AI Zen 5 + Zen 5c, Intel P + E cores) the guest main thread keeps a fast core of its own, the render threads the other fast cores, and the audio-mix, background shader, file, movie, pad and network threads the slow cores (`port-vkgame/cpu_placement.h`). No change on a CPU whose cores are all alike. `PS3_CPU_SLOW_CORES=<core list>` names the slow cores by hand. See `generated/analysis/cpu_placement/RESULTS.md` |
| `unlockvehicles` | launcher Cheats tab | Off*, On | every vehicle class and ticket counts as unlocked (`mspr_unlock_vehicles_on`, read at start; the first version's key `unlockall` is read when this one is absent). Saves are not changed |
| `unlocktracks` | launcher Cheats tab | Off*, On | every track passes the Free Play track-list filter (`mspr_unlock_tracks_on`, read at start). The Festival and Time Trial lists are not covered |
| `playername` | launcher Settings > Multiplayer (no in-game row: the page has choice rows only) | free text: 3 to 16 letters, digits, `-` or `_`, starting with a letter (a PSN online ID's rules); no line = none* | the name other players see. Read at start (`pc_settings.h` `pcs_player_name`): sets `PS3_NP_ONLINE_ID` (sceNp GetNpId / GetOnlineName / GetOnlineId, the name the game's own online pages and the LAN room server's member list carry, `libs/network/np_psnr.c`; also the name in the LAN browser instead of the computer name, `lan_play.cpp`) and `PS3_USER_NAME` (the system user name, `libs/system/cellUserInfo.c`, "User" without it), each unless already set. An empty or invalid value sets nothing (today's defaults: "PS3Player" offline). With a name, the runtime also derives the console's open PSID and MAC from it (`lv2_register.c` `open_psid`, `cellNetCtl.c`), as it does for `PS3_NP_ONLINE_ID`, so two players are two consoles. The launcher refuses an invalid name with a message; the in-game page keeps the line when it rewrites the file. See `generated/analysis/player_name/RESULTS.md` |

Sun shadows are world-fixed in both lightings, with no row: `RSX_SHADOW_TILES=1` is a default of the executable (`k_defaults`, port-vkgame/main.cpp) and of the launcher (`PLAY_ENV`). The game's casters are drawn into one shadow map fixed in the world (0.125 m texels, 512 m round the camera), so a shadow depends only on the sun and its casters, not on the camera (`ps3recomp-vkgame/libs/video/rsx_shadow_tiles.h`). `RSX_SHADOW_TILES=0` in the environment gives the game's own camera-following cascades; it is for testing only.

**Upscaler mode (`fsrmode`)** sets its variable at its default too. The default is FSR 1, as the launcher's (`launcher/electron/settings.js`), so the exe sets `RSX_FSR_MODE=1`. FSR 3.1 needs AMD's two DLLs beside the exe; without them that choice is not applied and the port runs FSR 1 (the page shows "FSR 3.1 (No FSR3 DLL)"). The mode only matters when `fsr` is not Off.

## Frame generation

`framegen` (`RSX_FRAMEGEN`, `ps3recomp-vkgame/libs/video/rsx_vk_framegen.h`) shows one generated frame between two real
ones: 30 real frames a second are shown as 60. It does not make the game run faster: the simulation, the input and the
physics stay at the Frame Rate setting.

- **Needs** the FSR 3.1 upscaler (its motion vectors, depth and camera): Upscaler FSR 3.1 with a quality (not Off), and HDR
  Off. Menus, loading screens and videos have no 3D scene: they are shown as before, without generated frames.
- **Light** is the port's own pass over the motion vectors (measured 0.06 ms of GPU a generated frame at 1707x960 on an
  RTX 5060); it ghosts more at the edges of moving objects and what the camera reveals. **On** is AMD FSR 3.1 frame
  generation (optical flow plus the motion vectors): better edges, about 2-3 ms of GPU a generated frame at 1707x960 on the
  same GPU and about 90-100 MB more video memory (the context reports 98 MB at 1707x960).
- **Latency:** a real frame is shown half a real frame later than without generation (about 17 ms at 30 FPS, 11 ms at 45),
  plus the generation's GPU time. The generated frame only shows motion between two frames the game already drew.
- **HUD:** the game draws the HUD into the same image. The port copies the frame before its first HUD draw, finds the HUD
  where the frame differs from that copy, and shows the real frame's pixels there, so the HUD is not interpolated (no
  ghosting; it updates at the real rate). `RSX_FRAMEGEN_UI=0` turns this off.
- **V-Sync Off (default, MAILBOX):** the port paces the two frames itself (the real frame half an interval after the
  generated one); best on a VRR (G-Sync / FreeSync) display. **V-Sync On (FIFO):** every present waits for a refresh, so
  twice the frame rate must fit the refresh rate (30 FPS on a 60 Hz display); a higher rate queues presents and slows the
  game.
- Diagnostics: `[framegen]` lines every 10 s in the log (shown frames, real and generated counted apart, step evenness, the
  real frame's hold, GPU time); `RSX_FRAMEGEN_PACE=0`, `RSX_FRAMEGEN_DEBUG=1`, `RSX_FRAMEGEN_SHOTS=<dir>`
  (`generated/analysis/framegen/RESULTS.md`).

## Performance page (opt-in, for small GPUs and handhelds)

The in-game page `options-pcp` (fifth hub item) and the launcher's Performance card. Every row's default is today's look
and sets nothing; nothing is chosen for the player. The launcher's **Low-end preset** button only fills the page (and Level of detail Lowest,
Dynamic Resolution On, Effects quality Minimal, Extra particles Off, Volumetric fog Off); it is saved only with Save settings.
All rows use the game's own values where the game has them (its viewportquality.xml entries for 2 and 4 players, its
options file), hooked where the game reads them (`launcher/pipeline/lowend_patch_lifted.py`, in `PATCHES_100`; players
need Install > Build once). Not offered, because the game has no own control for them (no logic was rewritten):
foliage density (grass and bushes are scenery meshes, no instance or density value; the draw distance covers them),
a lower AI update rate for distant cars (no AI LOD or update distance in `data/ai/*` or the options), depth of field
(the game has none) and a bloom switch (the game's only switch, enablePostProcessing, turns off all post-processing; the
port's `RSX_BLOOM_SCALE` only changes the look and saves no time). Measured effects: `generated/analysis/lowend_opts/RESULTS.md`.

## Racing wheels (Thrustmaster, Logitech and other DirectInput wheels)

A wheel is an **additional** input on port 0, read through DirectInput 8 (`dinput8.dll` is loaded at run time: no new dependency). A gamepad (XInput) and the keyboard keep working: buttons are OR-ed, each trigger takes the larger value, steering takes the source further from the centre. With a wheel and no XInput pad the wheel is the port-0 device, which turns the keyboard fallback off while the wheel is attached. Wheels that Windows already exposes as an Xbox controller (Logitech G920, Thrustmaster TMX in Xbox mode) were already usable as a gamepad and are not changed by this.

What the game reads (`libs/input/cellPad.c`, MotorStorm): steering = left stick X, throttle = R2 pressure, brake = L2 pressure (the pressure bytes of `cellPadGetData` with press mode on, which the game switches on itself), buttons = the pad's digital bits. The wheel layer fills exactly those: `lx` from the steering axis, `r2`/`l2` from the pedals (the digital R2/L2 bits above a threshold of 30, as the XInput path), the d-pad from the hat, buttons from the table below.

**Which devices.** `wheelmode = Auto` takes (best first) a device the player named with `wheel.device`, a model in the profile table (by VID/PID), a DirectInput "driving" device, a Thrustmaster/Logitech device whose name says wheel/racing/T300/G29/..., in that order. `Any Device` also takes any joystick with at least two axes and four buttons. A gamepad-type device is never taken unless named, so a pad is not read twice. A lost wheel is looked for again every 2 s (hot-plug); a wheel that reads nothing for 0.75 s is dropped. While the game window is not in the foreground the wheel reads as centred with released pedals and force feedback is stopped (set `PAD_WHEEL_BACKGROUND=1` to keep reading).

**Mapping.**
- Steering: the axis value is -1..1; `wheelrange` makes that rotation (270 deg: 135 deg either side) the full stick on a device whose driver lock is larger (the lock comes from the profile, 900 deg unless noted, DFGT 200; override with `wheel.steer.lock`); then the deadzone (rescaled so the edge still reaches full), then the curve, then `wheel.steer.invert`. Output is 1..255 with 128 at the centre (never 127: that value aliases SELECT+START).
- Pedals, separate axes: each pedal runs from "released" to "pressed". `wheelpedaldir = Auto` takes the first sample as released (a pedal resting at the high end, the usual Thrustmaster and Logitech case, reads as inverted) and moves the released end outward if the pedal was held at start; `Normal` and `Inverted` force it. 3% short of the far end counts as fully pressed. Explicit calibration (below) overrides all of it.
- Pedals, combined (`wheelpedals = Combined`, the driver's combined-pedals mode): one axis, centre = released, throttle toward 0 and brake toward 65535 (the Xbox-on-DirectInput convention; `Inverted` swaps them), 3% deadzone, `wheel.pedals.center` for a centre that is not the middle.
- Hat: 8 directions to the d-pad (`wheel.hat = none` turns it off).

**wheel.* keys** (not choices, so not on the page; the in-game page and the launcher keep them when they rewrite the file):

| key | meaning |
|---|---|
| `wheel.device = 044F:B66E` | use only this VID:PID (`any` = no preference) |
| `wheel.steer.axis = X` | `X Y Z Rx Ry Rz Slider1 Slider2` (default: the profile's) |
| `wheel.steer.invert = yes` | flip steering |
| `wheel.steer.lock = 900` | degrees of rotation the driver maps to the whole axis |
| `wheel.throttle.axis`, `wheel.brake.axis` | axis, or `none`; in combined mode the throttle axis carries both |
| `wheel.throttle.rest`, `.full`, `wheel.brake.rest`, `.full` | raw 0..65535 value released and fully pressed (both given = calibrated; the probe prints them) |
| `wheel.pedals.center` | combined-mode centre, raw |
| `wheel.hat = none` | ignore the hat |
| `wheel.button.N = Cross` | wheel button N (1-based, 1..32) to `Cross Circle Square Triangle L1 R1 L2 R2 L3 R3 Start Select Up Down Left Right` or `none` |

**Assumed layouts (HYPOTHESIS, not checked on a wheel).** DirectInput numbering depends on the driver (Thrustmaster's driver, Logitech G HUB or Profiler, the PS3/PS4/PC switch on the wheel), so these are defaults only:
- Axes, all supported models: steering X, throttle Y, brake Rz. If a pedal does nothing, run `wheel_probe --calibrate`, or `--live` and move one pedal at a time.
- Buttons, Thrustmaster (DualShock 4 order): 1 Square, 2 Cross, 3 Circle, 4 Triangle, 5 R1 (right paddle), 6 L1 (left paddle), 9 Select, 10 Start, 11 R3, 12 L3.
- Buttons, Logitech G29/G920/G923: 1 Cross, 2 Square, 3 Circle, 4 Triangle, 5 R1, 6 L1, 9 Select, 10 Start, 11 R3, 12 L3. Logitech G25/G27/DFGT: 1 R1, 2 L1, 3 Cross, 4 Square, 5 Circle, 6 Triangle, 7 Start, 8 Select. Unknown devices: 1 Cross, 2 Circle, 3 Square, 4 Triangle, 5 L1, 6 R1, 7 Select, 8 Start.
- Models (`pad_wheel.h` `k_pcw_profiles`): Thrustmaster VID 044F: T300RS B66E, T300RS GT B66F, B65D, B66D (PS4), T150 B677, TMX B67F, TX B669, T500RS B65E, TS-PC B689, TS-XW B692. Logitech VID 046D: G29 C24F (PS4 C260), G920 C262, G923 C266 / C267, G25 C299, G27 C29B, DFGT C29A, Driving Force C294 / Pro C298. The PIDs other than the T300RS, T150 and the Logitech wheels are from memory.

**Force feedback** is **off by default** (`wheelffb`). It is DirectInput effects on the wheel's steering axis, and the wheel is then opened exclusively (other programs lose force feedback while the game runs; if exclusive access is refused the wheel still works as an input). What the game gives it: MotorStorm imports `cellPadSetActDirect` (a DualShock rumble request), which the port already passed to XInput/SDL; with `Rumble` or `Both` that request drives a 25 Hz sine effect on the wheel (large motor 0..255 gives up to 75%, the small motor adds 25%). **Force feedback from the game's physics (tyre forces, collisions, road) is not available**: the game computes none for a pad and sends nothing the port could turn into it. `Centering` is a spring toward the middle, independent of the game, a stand-in for the driver's auto-centre (which is switched off while it runs and restored at exit). Safety (all in `pad_wheel.h` and unit-tested): levels are capped low (spring 35%, rumble 50% of the device scale) and then scaled by the strength setting through the device's overall gain; a level rises at most 20000/s and drops at once; the rumble effect is finite (1 s) and renewed every 0.4 s, so it stops by itself if the game stops polling, and a request nobody renews stops after 5 s; every effect is stopped when the window loses focus, at `cellPadEnd` and at process exit; no constant-force effect is used (it would push the wheel to one side).

**wheel_probe** (`port-wheel/tools/wheel_probe.c`, read only, built by `tools/build_wheel_tests.cmd`): `wheel_probe` lists the DirectInput devices with VID:PID, type, axes, buttons, hats, force feedback and the profile it would get; `wheel_probe --live` shows raw axes, buttons, hat and the resulting pad state (`--device N`, `--any`); `wheel_probe --calibrate` asks for the wheel, the throttle and the brake in turn and prints the `wheel.*` lines (axes, released/pressed values, combined or separate).

## Key bindings

Keyboard only (the keyboard fallback, used when no XInput pad is plugged into port 0). Gamepad rebinding is not in the alpha.

Format: `key.<action> = <key>[, <key>]`, up to two keys. Key names: letters, digits, `F1`..`F24`, `Num0`..`Num9`, or `Space Enter Tab Ctrl Shift Backspace Left Right Up Down Insert Delete Home End PageUp PageDown CapsLock Pause NumLock ScrollLock NumPlus NumMinus NumMultiply NumDivide NumDecimal Semicolon Equals Comma Minus Period Slash Backquote LBracket Backslash RBracket Quote`; `0xNN` (a Windows virtual-key code); or `none`. Esc, Alt, the Windows keys and mouse buttons cannot be bound. `Ctrl` is either Ctrl key.

**Default keys** (`pad_kb_layout_default` in `ps3recomp-vkgame/libs/input/pad_keyboard_map.h`; unit-tested):

| action (`key.`) | page | default | | action (`key.`) | page | default |
|---|---|---|---|---|---|---|
| `accelerate` | Driving | W, Up | | `start` | Buttons | Enter |
| `brake` | Driving | S, Down | | `select` | Buttons | C |
| `steerleft` | Driving | A, Left | | `up` | Arrows | Up |
| `steerright` | Driving | D, Right | | `down` | Arrows | Down |
| `handbrake` | Driving | Space | | `left` | Arrows | Left |
| `cross` (boost, accept) | Driving | Ctrl | | `right` | Arrows | Right |
| `square` | Driving | Q | | `circle` (back in menus) | Buttons | **none** |
| `triangle` | Driving | E | | `l1` | Buttons | **none** |
| | | | | `r1` | Buttons | **none** |

Actions with no default key: `circle`, `l1`, `r1`. The launcher and the page show them as "none". Consequence: in menus Back (Circle) has no key until the player binds one.

`up/down/left/right` are the menu movement and the d-pad; Up and Down are also accelerate and brake, and Left and Right also steer. A key can belong to two actions on purpose (shared defaults); a rebind removes the key from the other action, and a reset keeps shared defaults on both.

## Precedence (strongest first)

1. The process environment (the test runners, a shell). Any variable already set wins.
2. `settings.ini`. For a key the file names, the variable it drives is set from the file (unless step 1 set it), **and a line for that variable in `motorstorm.cfg` is ignored**. A key at its default sets nothing, except `fsrmode`, `framerate` and `lighting` (always set), so the port's own default applies.
3. `motorstorm.cfg` (`NAME=value`, written by the launcher): for variables **no settings.ini key covers** only: `PS3_VFS_ROOT`, `RSX_TEX_DUMP`, `RSX_RT_DXC`, `RSX_FSR3_DIR`, diagnostics. A cfg line for a variable the ini names (e.g. `RSX_FSR=quality`) is ignored once `settings.ini` has the matching key, which the in-game page writes in full on its first save.
4. The port's built-in defaults (`main.cpp` `k_defaults`).

Why: the player must not have two files that disagree. The old launcher wrote `RSX_FSR=...` into `motorstorm.cfg`; the in-game page wrote `settings.ini`. Now both write `settings.ini`; `motorstorm.cfg` keeps paths and diagnostics only.

Migration: if `settings.ini` does not exist, the launcher creates it from the old cfg lines (`RSX_FSR`, `RSX_FSR_MODE`, `RSX_HDR`, `PS3RECOMP_VK_FULLSCREEN`, `RSX_PRESENT_INTERVAL`, `RSX_TEX_PACK` set = `textures = On`, `RSX_TEX_PBR=1` = `pbr = On`) and deletes those lines from the cfg.

## Availability

A choice whose feature is missing is kept in the file but not applied, and the page shows the reason next to it ("On (No pack)"):

| choice | missing when | page text |
|---|---|---|
| `textures = On`, `pbr = On` | `<exe>/textures/pack` (or `RSX_TEX_PACK`) is not a folder | No pack |
| `fsrmode = FSR 3.1` | `amd_fidelityfx_loader_vk.dll` not beside the exe (or in `RSX_FSR3_DIR`); the port then runs FSR 1 | No FSR3 DLL |
| `framegen = On` | `amd_fidelityfx_framegeneration_vk.dll` not beside the exe (or in `RSX_FSR3_DIR`). Light needs no DLL | No FSR3 FG DLL |

## Speed options the launcher sets (not in settings.ini)

- `PS3_SPU_HWFLOAT=1` (set by the launcher's `PLAY_ENV`, `launcher/electron/service/builder.js`, on by default): lifted
  SPU single-precision maths runs on the host's own float unit (MXCSR round-toward-zero, flush-to-zero, denormals-are-zero)
  instead of the exact helpers, with the same results bit for bit. Host calls (channels, stops, halts) always run with the
  thread's own MXCSR. The variable is read only as exactly `1`; on a CPU without FMA3 the runtime prints
  `[spu-hwfloat] PS3_SPU_HWFLOAT=1 ignored: this CPU has no FMA3` to stderr and runs the exact helpers. The runtime default
  without the variable stays off.
- Status: VERIFIED (unit and bracket tests: `tests/test_spu_hwfloat_nested_host.c`, `tests/test_spu_hwfloat_bracket.py`);
  PARTIAL for speed and game output (not measured in a race; no game was run for this change).

## What the launcher does

The supported build is MotorStorm 1.00 (Stable); the install needs only the disc's decrypted 1.00 `EBOOT.elf`.

The launcher (`launcher/electron`, see `docs/LAUNCHER.md`) does not decrypt anything and holds no keys. Its settings
are the ones below, written as labels; the decrypted program files (EBOOT.elf) the install needs are the player's own,
chosen by them, checked by hash and never copied into `settings.ini` or anywhere else.

Status of the items, as the launcher has them now:

1. **Write `settings.ini`, not `motorstorm.cfg`, for every key in the table above** (read-modify-write, whole file, tmp + rename; the launcher's `SETTINGS` object maps: `RSX_FSR` -> `fsr`, `RSX_FSR_MODE` -> `fsrmode`, `RSX_HDR` -> `hdr`, `PS3RECOMP_VK_FULLSCREEN` -> `display`, `RSX_PRESENT_INTERVAL` -> `vsync`, `HD_TEXTURES` -> `textures`, `PBR` -> `pbr`). Labels in the file are the choice labels above, not the numbers. Keep writing `PS3_VFS_ROOT` etc. to `motorstorm.cfg`. The launcher's FSR default is `fsrmode = FSR 1`, the exe's too.
2. Done: the launcher's Settings page has `resolution`, `dynres`, `framerate`, `motionblur`, `aniso`, `lod`, `lighting`, `prompts`, the eight wheel rows, the two Cheats switches and the thirteen key bindings (`key.<action>`), written to `settings.ini` in the same format. The in-game page remains an equal editor of the same file.
3. **Ship the pinned DXC** (Microsoft DirectXShaderCompiler release zip; the files from `bin/x64`: `dxc.exe`, `dxcompiler.dll`, `dxil.dll`) into `<MotorStorm folder>/dxc/`, like the other toolchain pieces. Pin the release and its sha256 in the launcher. DXC is LLVM-licensed (Apache-2.0 with LLVM exceptions): add it to `THIRD_PARTY_LICENSES.md`.
4. Ship AMD's FSR 3.1 runtime (`amd_fidelityfx_loader_vk.dll`, `amd_fidelityfx_upscaler_vk.dll`) beside the exe (already planned for FSR 3.1).
5. **Generate the PC Settings pages on the player's PC** (never ship them). Tool: **`tools/pcmenu/make_pcmenu.py`** (public source; its five reader modules `page.py actions.py widgets.py coverage.py pack.py` sit in the same folder, no other dependency). Run after install and after every game or exe update:
   `py -3 tools/pcmenu/make_pcmenu.py --psarc <game>/PS3_GAME/USRDIR/MS2.PSARC --out <MotorStorm folder>/pcmenu`
   - Inputs: the retail pages `/gui/options.gui` and `/gui/options-controls.gui`, extracted from `MS2.PSARC` by the tool itself (archive table of contents and two members); and `port-vkgame/pc_pages.h` and `pc_settings.h` (the page table and the setting count; pass `--port <folder>` if the launcher ships them elsewhere). Alternative input: `--gui <folder>` with the two extracted pages.
   - Outputs: `pcmenu/gui/{optionz,options-pc,options-pcd,options-pcg,options-pcw,options-pcf,options-pcp,options-pck1,options-pck2,options-pck3}.gui` (the hub holds eight items: Display, Graphics, Racing Wheel, Effects, Performance and the three key pages; Display and Upscaling share one page) and `pcmenu/pcmenu.json` (the hashes of inputs and outputs). The pages are game data: the output stays on the player's PC.
   - Regenerate when the exe, `pc_pages.h`, `pc_settings.h` or the tool changes (`pcmenu.json` says which).
   - Exit code 0 means every page re-walked clean. If the folder is missing the game shows the retail Options page and `settings.ini` still applies.
   - Needs Python 3. `--psarc` needs nothing from the game but that one file.
6. The exe finds `pcmenu` beside itself (or `PS3_VFS_OVERLAY`). Never put `pcmenu/` into a release or CI artefact: it is made from game data. `tools/audit_public.py --tree tools/pcmenu` passes for the tool itself; run it again before each release.

## Status of the claims

- VERIFIED (unit tests, `generated/analysis/pcmenu/tools/build_tests.cmd`; 0 failures; the mutation build fails as it must): parsing, writing, precedence and ownership rules, the upscaler default and its FSR 1 fallback, availability skipping, key parsing and format, the default key set above, rebinding, conflicts, shared defaults and reset, the key-capture state machine, the page table (every setting and key row on exactly one page).
- VERIFIED (offline generator, `tools/pcmenu/make_pcmenu.py`, 2026-11-13): eight pages from the retail pages, all re-walked clean (0 unrelocated pointers); the `--psarc` and `--gui` routes give identical bytes.
- VERIFIED (syntax only): `pc_menu.cpp` compiles for 1.02 and 1.03 (`syntax_pc_menu.cmd`). Not linked, not run.
- PARTIAL: the two 1.03 hook sites were found by instruction shape against the 1.02 functions (lookup: callers 0x00561DA4 and 0x00564214, the 666 "no such function" constant is in it; resource load: `func_00503718`). Not run. `pcmenu_lifted_103.py` not applied.
- VERIFIED (simulated samples only, no wheel: `ps3recomp-vkgame/libs/input/tests/test_pad_wheel.c` and the wheel rows in `tests/test_pc_settings.c`; `port-wheel/tools/build_wheel_tests.cmd`): the steering range, deadzone, curve and invert arithmetic; pedal calibration, auto-detected direction, inverted pedals, combined mode; the hat to d-pad; the profile choice by VID/PID and device ranking; `settings.ini` wheel.* parse and write; the force feedback level caps and ramps; the eight wheel rows agree with the mapping's tables; `cellPad.c` with the wheel code still passes the XInput `test_pad_trigger_getdata`.
- VERIFIED (build only): `pad_wheel_dinput.h`, `wheel_probe.exe` and `pc_menu.cpp` compile. The probe finds no DirectInput controller on the development PC (no Thrustmaster or Logitech device is attached).
- NOT VERIFIED on a real wheel: everything that needs one: the axis and button layouts above, the PIDs from memory, the DirectInput open/acquire/hot-plug path, the force feedback effects, the T300's mode-dependent layout, the feel of the default range (270 deg) and curve. NOT VERIFIED in the running game: that the generated Racing Wheel page loads, and that a wheel drives a car.
- VERIFIED (unit tests): `playername` parse, rules, "a set variable wins" and the two variables (`tests/test_pc_settings.c`); the launcher's check, save, removal and read-back (`launcher/electron/test_settings.js`); `PS3_USER_NAME` in `cellUserInfoGetStat` (`ps3recomp-vkgame/libs/system/tests/test_userinfo_name.c`). In the game: see `generated/analysis/player_name/RESULTS.md`.
- NOT VERIFIED in the running game: that the generated pages load, that the rows react, that a key capture works with the real keyboard, MSPR live toggles, settings after a restart, RT and FSR availability text, the default keys in play. See `generated/analysis/pcmenu/RESULTS.md` for the walk to do.
