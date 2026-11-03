# T146 — runtime switch inventory (integration/t146-unified-runtime)

Every switch below was checked against its `getenv` site in `ps3recomp-t146-integration`. "Runtime" =
in-game validation status. Presets: `presets/preset_{baseline,visual-test,performance-test,combined-test}.cmd`
(all call `preset_common.cmd`, which sets every switch here; opt-in switches are *unset*, not `0`).

Status words: **VERIFIED** (measured in a game run), **offline** (synthetic/WARP/pins only), **none**.

## Default-on behaviour in the integrated tree (no switch needed)

| Switch | Default | Values | Purpose | Task | Runtime | Risk |
|---|---|---|---|---|---|---|
| `PS3_SPURS_GUEST_MAXCONT` | **on** | `0` = off | guest maxContention (5 lanes for Wws workloads) | T106 `b84ed80` | VERIFIED +57% FPS (4.7→7.2) on the T109 line; never run on the renderer line | five-lane races (T106 fixed 4) |
| `PS3_SPU_FP_CACHE` | **on** | `0` = off | exact SPU image fingerprint memo | T123 | offline (2.0→0.04 ms/frame) | none found (memcmp-exact) |
| `PS3_VM_STORE_FAST` | **on** | `0` = off | single-gate lifted store fast path | T140 | offline (store 3–4→1–1.5 ns) | 2 threads on SPU-marked lines ~20% slower |
| `RSX_FP_SPAN` | **on** | `0` = fixed 4096 | read FP ucode through END (≤64 KiB) | T113 | VERIFIED (white sheet gone, 0x07200641 compiles) | — |
| `RSX_RT_READBACK` | **on** | `0` = off | GPU→guest colour write-back | T113 | VERIFIED (exposure follows scene) | — |
| `RSX_VS_MEMO` | **on** | `0` = off | remember the last VS lookup | T119 | offline | — |
| (no switch) per-draw `getenv` read once | on | — | T119 `a1875dd` | offline | — |
| (no switch) FP refuse-without-END | on | — | T117 (decoder half) | offline | Vulkan/Metal keep 4096 windows: long programs refused there |
| (no switch) atomic flip-pending take | on | — | T132 | offline (18 checks) | — |
| (no switch) T122 frame fence (+1), back-buffer wait only on a new buffer, epoch counter | on | — | T122 | VERIFIED (23 runs, no regression) | — |
| (no switch) SSE4.1 SPU float/fi/cwd paths | on (SSE4.1 builds) | `-DSPU_SCALAR_FLOAT` | T136 | offline (bit-identical, 225M cases) | fma ~11% slower on denormal lanes; assumes RN MXCSR |
| (no switch) T106 five-lane race fixes, SPU diag TLS, `gcm_note_spu_put` lock | on | — | T106/T81 | VERIFIED (T106 B/D arms) | — |

## Opt-in switches (off unless set)

| Switch | Values | Purpose | Task | Deps | Perf | Runtime | Correctness risk |
|---|---|---|---|---|---|---|---|
| `PS3_SPURS_READY_LEVEL` | `1` | SPURS1 level admission | T109 | — | lower idle CPU | none (arm never run) | could stall if the job manager relies on polling |
| `PS3_SPURS_KICK_WAKE` | `1` | wake coordinator on kick-line commit | T123 | — | kick→done 15 ms→60 µs (fixture) | none | lost-wake window, poll storms (T123B) |
| `PS3_SPURS_EVENT_SCHED` | `1` | WaitOnAddress coordinator | T123B | Win8+ | p99 kick→done 1194→41 µs (fixture) | none | hook-invisible writes wait ≤ fallback |
| `PS3_SPURS_EVENT_FALLBACK_MS` | 1–100 (4) | event-mode fallback poll | T123B | EVENT_SCHED | — | none | — |
| `PS3_USLEEP_SPIN` | `2` (`1` broken ≥1 ms) | timer + spin tail to exact deadline | T121 | `PS3_USLEEP_TAIL_US` (600) | usleep 517→250 µs; +~1 core | none | host CPU cost |
| `PPU_RESV_STORE` | `1` | plain stores break other reservations (now incl. lifted stores) | T140 | — | slower stores | none | — |
| `PPU_RAW_STORE_COH` | `1` | raw-store SPU lock-line coherence | T140 | **re-lift + recompile** (not in this exe) | — | none | — |
| `PS3_SIM_PACE` (+`_HZ` 30, `_LAG_MS` 200, `_STATS`) | `1` | real-time pacing of the fixed 1/30 s step | T132B | — | — | none | holds the main thread; keep off in A/B (physics timing) |
| `GCM_SEMA_ACQUIRE` | `1` | honour the vblank flip gate | existing; T132 analysis | — | — | none | could wedge; T132 left off |
| `PS3_SPU_WWS_AOT` / `_BASES` / `_VERIFY` | `0` / hex list / `1` | Wws job AOT (exe built with `MSPR_WWS_AOT`) | T37–T109 | AOT exe only (`port-t106aot`) | +4% FPS (T106 D1) | VERIFIED on T109 line | registration is opt-in: the generated constructor (`generated/spu_raw/wws_reloc_t81c/wws_reloc_register.c`) registers only for exactly `1`; `=0` additionally refuses at dispatch. T106's AB note ("on unless 0") does not match this generated output — check the constructor of the AOT dir actually built |
| `RSX_GUEST_SAMPLERS` | mask, 15 = all | guest filter/wrap/LOD/bias/aniso/border | T110 | — | — | none | unit 0 debug-font workaround replaced |
| `RSX_TEX_MIPS` | `1` | guest mip chains | T115 | best with GUEST_SAMPLERS=15 | +3–9% CPU on miss, +33% VRAM | none | trilinear without guest samplers |
| `RSX_TEX_CACHE` | `1`/`2` | exact texture-cache validation, CONTROL3 pitch | T115B | — | 0.5–2 ms est. | none | — |
| `RSX_RT_WINDOW` | `1` | RT sampled through declared window | T120 (+T142 fetched-unit rule) | — | — | none | self-read needs RT_FEEDBACK |
| `RSX_DEPTH_STATE` | `1` | guest depth/stencil in guest-FP pipelines | T120 | — | — | none | stencil clear values unknown (T144) |
| `RSX_STENCIL_EXACT` | `1` | guest stencil without the depth part | T144 | ignored with DEPTH_STATE | — | none | shadow-atlas EQUAL 64 vs unknown clear |
| `RSX_FP_PRECISION` | `1` | FX12/FX9/FP16 clamps | T133 | — | — | none | changes shader text |
| `RSX_MSAA` | `1` | 2-sample antialias-3 surfaces | T137 | **needs GUEST_SAMPLERS=15** | ~38 MiB, ~1.5 ms (890M est.) | none | 0x1D7C never captured |
| `RSX_RT_FEEDBACK` | `1` | copy target before self-sampling draw | T141 | needs RT_WINDOW | small | none | — |
| `RSX_ZETA_EXACT` | `1` | exact depth24 in zeta-as-colour | T141 | — | — | none | — |
| `RSX_MRT_STATE` | `1` | COLOR_MASK_MRT / BLEND_ENABLE_MRT | T141 | — | — | none | — |
| `RSX_SHADER_WINDOW` | `1` | SET_SHADER_WINDOW origin for WPOS | T145 | — | — | none (offline: 3 race FPs mirrored) | — |
| `RSX_COLOR_XFER` | mask, 7 = all | sRGB output / texture gamma / expand | T110 | — | — | none | **unverified colour change: not in any default preset** |
| `RSX_ATTR0_CONST` / `RSX_RTPOOL_GF` | `1` | attr0-off draws / RT eviction policy | T110 | — | — | T113 runs: no effect | — |
| `PS3_TEX_SNAPSHOT_EPOCH` | `1` | hash a texture once per sync epoch | T122 | — | drain 115→53 ms | VERIFIED (race runs) | review `gcm_epoch_pure()` list before default |
| `RSX_VP_COMPACT` | `1` | compact indexed strip records | T119 | — | RSX drain 114→80 ms | VERIFIED (T122 exe C) | — |
| `RSX_SHADER_CACHE` | 0–3 | bytecode/disk/PSO-library cache | T116 | `_MEMCACHE`, `_DIR`, `_MAX_MB`, `_CLEAR`, `RSX_PSO_LIB_SAVE_FRAMES` | cold 959→135 ms warm (40 shaders) | none | T146 fixed failure-memo key (u64 depth, wpos_key) |
| `RSX_SRV_REUSE` | `1` | share identical per-draw SRV windows | T143 | — | render CPU −32–42% (bench) | none | reset on any resource creation |
| `RSX_BIND_DEDUP` | `1` | skip repeated per-draw binds | T143 | — | −0.06 ms | none | foreign binds drop the shadow |

## Diagnostics (off unless set)

`RSX_GPU_PROF=<frames>[,max]` (T143), `RSX_GPU_SYNC=<frames>` (T122), `RSX_FRAME_PERF`, `RSX_DRAW_SPLIT=1` (T119),
`RSX_SHADER_STATS=1` (T116), `PS3_CRITICAL_PATH_TRACE` / `_SAMPLE_MS` (T134), `PS3_SPURS_SCHED_STATS=<ms>` (T123B),
`PS3_VM_STATS=<ms>` (T140; forces the slow store path), `PS3_SC_WAIT_MS` (T109), `SPURS_BUSY_MS`, `PS3_FTRACE_SPUJOB`,
`PS3_FTRACE_ARM`, `PS3_SPU_AOT_PROF`, `RSX_XFER_LOG` (T107), `RSX_ATTR0_LOG`, `RSX_VPC_WATCH_*` (T113), `D3D12_DBG`,
`D3D12_GBV` (T141), `RACE_PRESENT_PROBE*`, `RTPOOL_LOG`.

## Not integrated

`PS3_SPURS_LANE_HANDOFF` (T144 SPURS): uncommitted work in `ps3recomp-t144s`, synthetic net regression in default-like arms.
