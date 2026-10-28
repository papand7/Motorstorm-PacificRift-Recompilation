@echo off
rem Build the trace-hooked native executable in its own tree, beside the
rem ordinary build: build\motorstorm-trace from generated\ppu-hooked-staging
rem (ppu_lifter.py --trace-hooks). The ordinary build\motorstorm and
rem generated\ppu are not touched. Tracing stays off unless PS3_TRACE is set.
setlocal
call "%~dp0resolve_env.cmd" || exit /b 1
if not exist "%VCVARS%" exit /b 1
call "%VCVARS%" || exit /b 1
set "LLVM_BIN=%CD%\build\llvm\clang+llvm-23.1.3-x86_64-pc-windows-msvc\bin"
if exist "%LLVM_BIN%\clang-cl.exe" set "PATH=%LLVM_BIN%;%PATH%"
where clang-cl >nul 2>nul || exit /b 2
if not exist generated\ppu-hooked-staging\ppu_recomp.h exit /b 3
"%PYTHON%" ps3recomp\tools\gen_hle_nids.py --all --out generated\ppu-hooked-staging\ppu_hle_nids.cpp || exit /b 1
if not exist build\motorstorm-trace\build.ninja (
  cmake -S port -B build\motorstorm-trace -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl -DPython3_EXECUTABLE="%PYTHON%" -DPS3RECOMP_DIR="%CD%\ps3recomp" -DRECOMP_DIR="%CD%\generated\ppu-hooked-staging" -DSPU_DIR="%CD%\generated\spu_lifted" -DPORT_SPU_INPUTS="%CD%\generated\decrypted\EBOOT.elf" || exit /b 1
)
cmake --build build\motorstorm-trace --config Release --parallel 2 || exit /b 1
