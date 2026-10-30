# T163: recovery implementation

**Branch:** ps3recomp `agent/t163-vulkan-recovery` (worktree `ps3recomp-t163-vulkan`), base `afdcabd`, commit **`cc343a0`**. Not merged, not pushed.

**Change (64 insertions, 6 deletions; CRLF preserved):**
- `CMakeLists.txt`: `PS3RECOMP_RSX_VULKAN` allowed on Windows (default stays OFF); `ps3recomp_host` built when it is ON.
- `rsx_vulkan_backend.c`: loads `vulkan-1.dll` through the same run-time path; SRW lock for its two mutexes; SDL calls replaced on Windows by stubs that fail, so `PS3RECOMP_VK_WINDOW=1` drops to headless with a message.
- `host_posix.c`, `host_stubs.c`: Windows `Sleep`, no pthread include, and an empty `function_table` for the crash backtrace reference.

**Default behaviour:** unchanged by construction. With the option OFF, the backend stays excluded and the host isn't built on Windows. D3D12, gameplay and the game exe are not touched. The full suite was **not** rerun because no default-path file changed.

**Build:**
- Vulkan-Headers `v1.4.341` (`b5c8f99`), clone at `build/t163-vkheaders/src`
- clang-cl LLVM 23.1.3, Ninja, Release
- `cmake -S ps3recomp-t163-vulkan -B build/t163-vulkan -G Ninja -DCMAKE_BUILD_TYPE=Release -DPS3RECOMP_RSX_VULKAN=ON -DPS3RECOMP_VULKAN_INCLUDE_DIR=<headers>`, then `--target ps3recomp_host`
- Result: rc 0. CMake reports `glslang not found; guest programs unavailable`.

**Requirements found:** Vulkan 1.0 entry points (backend header); glslang and spirv-tools for guest programs; the validation layer for validation. A full list of device features was not derived.

**Not implemented:** `RSX_BACKEND`, residency, batching, stencil fixes. They need the guest-program path running first; changing them blind would be speculation.
