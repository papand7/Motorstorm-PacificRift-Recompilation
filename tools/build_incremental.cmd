@echo off
setlocal
call "%~dp0resolve_env.cmd" || exit /b 1
if not exist "%VCVARS%" exit /b 1
call "%VCVARS%" || exit /b 1
set "LLVM_BIN=%CD%\build\llvm\clang+llvm-23.1.3-x86_64-pc-windows-msvc\bin"
if exist "%LLVM_BIN%\clang-cl.exe" set "PATH=%LLVM_BIN%;%PATH%"
where clang-cl >nul 2>nul || exit /b 2
cmake --build build\motorstorm --config Release --parallel 2 || exit /b 1
