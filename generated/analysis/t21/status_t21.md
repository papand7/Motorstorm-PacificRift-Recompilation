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
    - `PS3_FTRACE_USLEEP_REG=31`: r31 at each usleep. At `0x94CCA8` that is the condition-variable gate address, so it shows which condition main waits on and whether it changes across frames. Verified at `0x4B64B4`, where the `sc` is inline and r31 holds the lock address. The `0x536xxx` sleeps go through the `SystemTimeSleep` wrapper, so r31 there is not reliable;
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

