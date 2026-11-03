# T185 Arm Q: top 5 findings, ranked by measured impact

- One launch, exe `ee2d6925d74e12e82555a84f91144e89a25eba7001f2a75c331ab5c26565019f`, race frame 68.63 ms (14.57 fps). Arm Q is instrumented, so its FPS is not a performance result.
- Details are in `ARM_Q_DIAGNOSTICS.md`.

| # | Finding | Measured | Class | Where |
|---|---|---|---|---|
| 1 | **Havok solver polls one ticket line for 64 % of its run time.** 32,912 GETLLAR per frame, 99 % unchanged, about 300 polls per episode (max 3,694). Each poll takes the global lock. | **34.4 ms/frame** of SPU thread time (6.7 of 10.5 ms per solver run) | A (cost) / B (critical path) | Solver image `341580667`, line EA `0x16218E80`, loop at LS `0x1781C` (PARTIAL: line-level match only); runtime `runtime/spu/spu_channels.c` `spu_mfc_atomic` |
| 2 | **Main thread sleeps through its waits.** `sys_timer_usleep` is called 672 times/s at 0.491 ms each; event-queue receive 99 ms/s. | **29.4 ms/frame blocked** | A (blocked time) / B (avoidable latency) | Guest `0x004B63F0` (spin, then sc 141), `0x00A4C590` (sc 130), `0x00322D78`/`0x00323228`; runtime `lv2_syscall` sleep path |
| 3 | **Frame-end busy wait for SPU Wws jobs.** | **11.94 ms/frame** | A | Guest `0x0050C818` |
| 4 | **`cellSpursCreateTask` cost is stdout logging, not locks.** 249.1 of 265.9 µs per call is the `printf`; lock wait is 0.1 µs. | **4.95 ms/frame** on tid 1 | A | `libs/spurs/cellSpurs.c` `create_task_impl` (`CT_LOG` stage) |
| 5 | **Post-Havok PPU time (22.96 ms) has no single hotspot.** Wait primitive 3.9 ms; vector math `0x0002FB60` 2.9, `0x00B500A0` 2.75, `0x00BCACE8` 1.06; about 9 ms flat tail under 0.2 ms per function. | distribution measured | A | `generated/ppu-t173-staging` lifted functions; possible VMX lowering cost in `runtime/ppu/ppu_vmx.h` (C) |

**Global lock-line lock.** One spinlock (`runtime/spu/spu_coherency.c` `g_lockline`) serves every address, at about 570,000 acquisitions per second. Its wait is negligible for PPU task creation. The wait on SPU threads was not measured.

**Fix first:** quiet logging (4.95 ms on the critical path, already exists). The first structural fix, generic and also relevant to Battlefield 1943, is reservation-aware waiting for unchanged GETLLAR polls, plus a per-line lock.

**Next run:** arm L, one launch.
