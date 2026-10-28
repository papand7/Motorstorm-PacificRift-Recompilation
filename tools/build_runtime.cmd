@echo off
setlocal
call "%~dp0resolve_env.cmd" || exit /b 1
if not exist "%VCVARS%" (
  echo Missing Visual Studio vcvars64.bat: %VCVARS% 1>&2
  exit /b 1
)
call "%VCVARS%" || exit /b 1
set "LLVM_BIN=%CD%\build\llvm\clang+llvm-23.1.3-x86_64-pc-windows-msvc\bin"
if exist "%LLVM_BIN%\clang-cl.exe" set "PATH=%LLVM_BIN%;%PATH%"
where clang-cl >nul 2>nul
if errorlevel 1 (
  echo clang-cl is required by ps3recomp but unavailable. 1>&2
  exit /b 2
)
cmake -S ps3recomp -B build\runtime-clang -G Ninja -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl || exit /b 1
cmake --build build\runtime-clang --config Release || exit /b 1
