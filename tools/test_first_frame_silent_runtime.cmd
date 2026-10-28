@echo off
setlocal
call "%~dp0resolve_env.cmd" || exit /b 1
if not exist "%VCVARS%" exit /b 2
call "%VCVARS%" >nul || exit /b 2
set "LLVM_BIN=%CD%\build\llvm\clang+llvm-23.1.3-x86_64-pc-windows-msvc\bin"
if exist "%LLVM_BIN%\clang-cl.exe" set "PATH=%LLVM_BIN%;%PATH%"
clang-cl /nologo /MD /O2 /Gy /Gw /D_CRT_SECURE_NO_WARNINGS /I ps3recomp\include /Fe:build\first_frame_silent_runtime.exe ps3recomp\libs\audio\tests\test_first_frame_silent_runtime.c /link /OPT:REF ole32.lib uuid.lib winmm.lib user32.lib gdi32.lib bcrypt.lib ws2_32.lib || exit /b 1
build\first_frame_silent_runtime.exe || exit /b 1
