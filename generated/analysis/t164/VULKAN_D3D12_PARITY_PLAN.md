# T164: D3D12 comparison and parity plan

**No D3D12 result exists. The comparison was not run, so no claim is made about which backend is faster.** The D3D12 backend was not changed.

## Can this environment run it?

| Requirement | State |
|---|---|
| `d3d12.dll`, `D3DCompiler_47.dll` | Present |
| `rsx_d3d12_backend.c`, `rsx_live_draw.c` compile | Yes: objects exist in `build/t164-vulkan` |
| RTX 5060, Radeon iGPU | Present |
| Host can select D3D12 | **No.** `host_posix.c` selects Metal, Vulkan or null |
| Windowless operation | **No.** `rsx_d3d12_backend_init(w,h,title)` creates a window and swap chain |
| Same FIFO path | **No.** D3D12 draws through `rsx_live_draw`, not `rsx_draw_engine`, so the same stream reaches different code |

So the blocker is the harness, not the machine. Running it means adding a D3D12 branch to the host, which can be done without changing the backend. It was left out because the batching work took priority and the result would need its own correctness pass.

## Harness

`tools/run_d3d12_compare_t164.py`: preflight now, runner later. It uses the same workloads, 5 repeats and 30 frames, and never launches a game. It exits 2 and writes no timings until the host can select D3D12.

Current output: all checks true except `host_selects_d3d12`, `NOT RUN`, exit 2.

### Dependencies

- Visual Studio 18 Community (`vcvars64.bat`), clang-cl LLVM 23.1.3, Ninja, CMake
- Vulkan-Headers v1.4.341 and the installed LunarG SDK, for the Vulkan side
- Windows D3D12 and D3DCompiler 47 (system)
- An interactive desktop, because the backend creates a window

### Commands

```
generated\analysis\t164\tools\build_vk_t164.cmd
python generated/analysis/t164/tools/run_bench_t164.py
python generated/analysis/t164/tools/run_d3d12_compare_t164.py
python generated/analysis/t164/tools/perf_tables_t164.py
```

`build_vk_t164.cmd` is private (gitignored). Its CMake line:

```
cmake -S ps3recomp-t164-vulkan -B build\t164-vulkan -G Ninja -DCMAKE_BUILD_TYPE=Release
  -DCMAKE_C_COMPILER=<llvm>/clang-cl.exe -DCMAKE_CXX_COMPILER=<llvm>/clang-cl.exe
  -DCMAKE_LINKER=<llvm>/lld-link.exe -DPS3RECOMP_RSX_VULKAN=ON
  -DPS3RECOMP_VULKAN_INCLUDE_DIR=<vulkan-headers>/include -DPS3RECOMP_VULKAN_SDK=<sdk>
cmake --build build\t164-vulkan --target ps3recomp_host -j 6
```

### Work needed

1. Add `RSX_BACKEND=d3d12` to the host: call `rsx_live_draw_init` with a hidden window and read frames with `rsx_live_draw_debug_dump_surface`.
2. Make frame capture comparable. Hashes won't match across APIs on filtering, so use a pixel tolerance rather than byte equality.
3. Compare frame wall time first. Queue, wait and GPU counters would need separate D3D12 instrumentation, in a build kept apart from the shipping backend.
4. Report each GPU separately. Don't compare across different scene coverage: the two backends take different paths through the RSX state.

## Vulkan's remaining gaps before any game run

| Gap | Effect | Needed |
|---|---|---|
| `NV406E_SET_REFERENCE`, semaphores | `rsx_draw_engine_flush` has no caller in `libs/` or `runtime/`, so guest-visible sync isn't connected on this path | Decide and connect: **first item**, because the batched path makes the answer matter |
| `RSX_BACKEND` selection | The game can't choose Vulkan | Switch, off by default |
| Windows surface | Headless only | Swapchain present |
| Vertex constants above the UBO cap, vertex textures | Existing gaps | Fill or report |
| Vtable path | Stays synchronous under the switch | Keep, or move callers to the engine |
| Two-sided stencil | No test | Add a scene |

## Game validation plan (not authorized in T164)

Only after the first three gaps close, and only with a task that authorizes a launch:

1. Reference path to the title, compared visually with D3D12.
2. `RSX_VK_BATCHED_SUBMIT=1` on the same path, with validation on.
3. Timed A/B with `RSX_VK_STATS=1` off, separately for each GPU, coordinated with other A/B sessions.

Until step 3 exists, no in-game improvement can be claimed.
