# T169: resource lifetime and synchronisation

**No resource recreation or GPU wait caused by a colour, sampler or depth mismatch was found. That comes from code reading and earlier measurements, not from a new in-game run.**

| Item | Finding | Source | Label |
|---|---|---|---|
| ~84 ms GPU wait | Remote-session `Present(1,0)` holding the queue; not from rendering state | T167 | VERIFIED there |
| Pass-start `wait_for_gpu()` | Every pass; fence wait about 0 | T153–T155 | VERIFIED there |
| RT binds | 32 per frame; RT pool stable in B3, `rt_lifecycle_total` 28 | B3 | VERIFIED; no recreation evidence |
| Sampler heap | Append-only, 27 of 2,032 used in B3; nothing to fence | B3, code | VERIFIED |
| Mips | Same upload path; no new wait (T133) | Code | VERIFIED; memory up 29.6 % |
| Transfers | PSO variants only; no resources | Code | VERIFIED |
| Depth state | Keeps the guest's zeta bound where the legacy path could drop it | Code | Behaviour change, untimed |
| Depth-as-colour | `zconv` rebuilds an RGBA8 copy per zeta on demand (19 sampled bindings in B3) | Code, B3 | Cost unmeasured |
| MSAA | Doubles targets; adds a sample-expand copy; touches pool | T137 | Cost unmeasured on this base |
| RT feedback | One extra copy per self-sampling draw | T141 | Cost unmeasured |

**sRGB views:** the backend uses no `_SRGB` view or resource format. Both transfers are in shaders, so blending isn't affected by a view, and no aliasing issue arises from views.

**Barriers:** 29 `ResourceBarrier` sites; `RSX_GPU_PROF` counts them per pass. No capture has run with profile bits on, so no comparison exists.

**T167 overlap:** T167 owns the wait and compile work on its own branch. `D3DCompile`'s diagnostic counter here isn't thread-safe for T167's background compile. If merged with T167 it must become atomic. `rsx_d3d12_backend.c` will conflict textually at the sites listed in `INTEGRATION_READINESS.md`.
