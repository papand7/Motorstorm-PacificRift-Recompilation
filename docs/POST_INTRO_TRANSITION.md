# Post-intro transition (intro end → garage request)

Status labels follow AGENTS.md. Offline analysis only; no launch was made for this document (2026-10-23).

## Earliest blocker (native audio) — OPEN, cause unknown

Run `generated/runs/20261023-100017-audio`:
- Exe: `611ad702…969ba8`, ps3recomp-int `8b62438`, `FIRST_FRAME_AUDIO=native`.
- Runner settings: target `garage_resources_requested`, timeout 210 s.

**VERIFIED from the logs:**
- **Exit:** the runner stopped at its **210 s timeout** (exit 2). The garage was never requested.
- **Video:** decode stopped at **Bink frame 2255 of ~3160**, about 104 s into the vstat timeline. The previous `ind` run (silent audio) reached 3160.
- **GPU watchdog:** the guest logged **26 × `Gc ERROR: GcKernel::Present() Timeout!`**.
  - The last RSX reference passed was 2526.
  - The RSX GET pointer stayed at `0x11068`.
  - Presents stopped.
- **Main thread (tid 1):** polls `usleep` from lr `0x0072E5C0`, inside a caller of `0x72E1E0`.
- **Audio:** the Bink audio port 1 (now 8 channels after `AudioOutConfigure` succeeded) fell to ~2 % fill. No `PortStop` was issued.
- **Thermal:** peak 355 K; the guard did not trip.

**What this establishes:**
- With native audio, this is the earliest observed blocker on the way to the menu.
- The cause is unknown. Not established:
  - whether the 8-channel port or the game's audio-out wait changes Bink's audio/video sync;
  - whether the FIFO stall is the cause of the hang or a consequence of it.
- The `sse2` and `ind` runs (silent null sink, 2-channel port) logged 0 Present timeouts.
- Native audio is not to be disabled as a workaround. A silent-audio comparison run would be a diagnostic only, and would need separate authorization.

## Transition path (silent-audio runs)

Measured from old exe `375bb574`, run `20261021-220103-baseline-diag`, and the 2026-10-23 `ind`/`sse2` runs.

| Step | Evidence | Label |
|---|---|---|
| `ms2.psarc` opened | `[fs] open '…/ms2.psarc' -> fd 5` (fd 3 in the old diag run), stderr line ~83 | VERIFIED |
| Intro Bink opened, decoded to frame 3160 | fs open of `gui_intro*.bik`, decode-round counters | VERIFIED |
| Intro completed | `intro_video_completed` at 583 s (old diag run) | VERIFIED |
| Frontend asks for the garage | first `[fs] open FAIL '/dev_bdvd/PS3_GAME/USRDIR/worlds/track_garage_ain_objects.rpk'` at 597 s; a loose-file probe before the archive lookup | VERIFIED |
| After the request | 150 s `no_progress` (run ended at 773 s); FIOS SPU `WAIT_SIGNAL`, a POISON-DMA line, one spu-spin, failed `/dev_bdvd/PSN_GAME/…` probes | VERIFIED (old exe) |
| Emblem artwork screen → white → black | earlier no-skip run (STATUS.md); suspected auto-exposure readback | HYPOTHESIS for the cause |

## Original guest functions (frontend script commands)

- **How they were found:** from the command-name table (TOC `0x0109FBF0`). Each entry is `{OPD, name_ptr}`: the wrapper's descriptor comes *before* its name (VERIFIED 2026-10-24: Set/Get pairs line up, e.g. SetGarageType `0x00014698` stores `[+0x70]` and GetGarageType `0x000146A0` reads it; MainMenuMotorStoreGuard resolves to `0x00016758`, the function that references `mainmenu.gui`). Each wrapper is a pointer-to-member trampoline (`lwz r11, off(r2)` → TOC slot → OPD); the handler is the real target. An earlier version of this table read `{name_ptr, next OPD}` and was shifted by one entry. Resolver: `generated/analysis/garage_menu/cmdmap2.py`.
- **Command dispatch chain (VERIFIED static):** dispatcher `func_0059DC60` / `func_0059F2F8` → scanner `func_005B24D8` → `func_001E8058` / `func_001F5658`.

| Command | Wrapper | Handler |
|---|---|---|
| FrontendVideoCanStart | `0x0076C8D8` | `0x00014AF8` |
| SetIntroVideoSeen | `0x007727A0` | `0x000147F0` |
| GotoGarage | `0x0076EAE0` | `0x0002DE08` |
| LeaveGarage | `0x0076EB48` | `0x0005C0B0` |
| GarageInput | `0x0076EBB0` | `0x0002B410` |
| HowManyPads | `0x0076E598` | `0x00013F18` |
| FirstGarageVisit / SetFirstGarageVisit | `0x0076F3E0` / `0x0076F448` | `0x000146A8` / `0x00017EC0` |
| PrepareLoadingScreen / PopulateLoadingScreen | `0x0077F798` / `0x0077F800` | `0x00018060` / `0x0002AAF8` |
| Preload / PreloadDone | `0x0077F868` / `0x0077F8D0` | `0x00013E58` / `0x00013EE8` |
| MainMenuMotorStoreGuard | `0x00775B10` | `0x00016758` |
| SetExitOnline | `0x00781E78` | not a PMF trampoline; UNKNOWN statically |

- These handlers have not been confirmed at runtime. A bounded call trace (`PS3_FTRACE` on these addresses) would confirm the order. That trace needs a run, which is not authorized.
