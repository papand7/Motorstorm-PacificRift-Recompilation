@echo off
rem Builds and runs the racing-wheel work's tests in the isolated trees (no hardware needed):
rem   ps3recomp-wheel\libs\input\tests\test_pad_wheel.c            mapping, profiles, settings.ini, FFB limits (simulated samples)
rem   ps3recomp-wheel\libs\input\tests\test_pad_trigger_getdata.c   cellPad.c still builds with the wheel code and the XInput path is unchanged
rem   port-wheel\tests\test_pc_settings.c / test_pc_keys.c          the PC Settings table with the eight wheel rows and the page table
rem   ps3recomp-wheel\libs\input\tests\test_pad_keyboard_map.c      keyboard layout (unchanged)
rem   wheel_probe.exe                                                the console tool (build only; run it on a machine with a wheel)
rem usage: <port folder>\tools\build_wheel_tests.cmd   (from anywhere; the repo root is two levels up)
rem        FW and PORT default to ps3recomp-wheel and port-wheel when they exist, else ps3recomp-vkgame and port-vkgame
setlocal
cd /d "%~dp0..\.."
set "PATH=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer;%PATH%"
if not defined VCVARS set "VCVARS=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
call "%VCVARS%" >nul 2>nul || exit /b 1
if not defined LLVM_BIN set "LLVM_BIN=%CD%\build\llvm\clang+llvm-23.1.3-x86_64-pc-windows-msvc\bin"
set "PATH=%LLVM_BIN%;%PATH%"
set "OUT=build\wheel_test"
if not defined FW (if exist ps3recomp-wheel (set "FW=ps3recomp-wheel") else (set "FW=ps3recomp-vkgame"))
if not defined PORT (if exist port-wheel (set "PORT=port-wheel") else (set "PORT=port-vkgame"))
set "INC=-I%PORT% -I%FW%\include -I%FW%\libs\input"
set "CF=-std=gnu17 -O2 -Wall -Wextra -D_CRT_SECURE_NO_WARNINGS"
if not exist %OUT% mkdir %OUT%
set RC=0
for %%T in (%FW%\libs\input\tests\test_pad_wheel %PORT%\tests\test_pc_settings %PORT%\tests\test_pc_keys %FW%\libs\input\tests\test_pad_keyboard_map) do (
  clang %CF% %INC% %%T.c -o %OUT%\%%~nT.exe || exit /b 1
  %OUT%\%%~nT.exe || set RC=1
)
clang -std=gnu17 -O1 -Wall -Wno-unused-function -D_CRT_SECURE_NO_WARNINGS -I%FW%\include -I%FW%\libs\input %FW%\libs\input\tests\test_pad_trigger_getdata.c -o %OUT%\test_pad_trigger_getdata.exe -luser32 || exit /b 1
%OUT%\test_pad_trigger_getdata.exe || set RC=1
clang %CF% %INC% %PORT%\tools\wheel_probe.c -o %OUT%\wheel_probe.exe -luser32 || exit /b 1
echo wheel_probe built: %OUT%\wheel_probe.exe
clang++ -std=c++17 -fsyntax-only -Wall -Wno-unused-function -D_CRT_SECURE_NO_WARNINGS %INC% -x c++ %PORT%\pc_pages.h || exit /b 1
echo c++ syntax ok
echo tests rc=%RC%
exit /b %RC%
