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
"%PYTHON%" ps3recomp\tools\gen_hle_nids.py --all --out generated\ppu\ppu_hle_nids.cpp || exit /b 1
"%PYTHON%" tools\build_wws_pm.py || exit /b 1
"%PYTHON%" tools\build_spu_overlay.py --input-dir generated\overlays\spu38790\versions --sha256 bc5bbdfbe5e7069dc7e7e00e067a1bf08ece96f217574dd5121851451d6cc9e4 --out generated\overlays\spu38790\lift --base 0x35F00 --entry 0x38790 --extra-funcs 0x38AD0,0x35F18,0x35F10,0x36B40 --size 0x3000 || exit /b 1
"%PYTHON%" tools\build_spu_overlay.py --input-dir generated\overlays\spu38790\versions --sha256 7ddb23d4b7882d7bff7771eca8e59167c1e9eb014a2ca6b1876a3a75f --out generated\overlays\spu38790\variant2\lift --base 0x35F00 --entry 0x35F10 --extra-funcs 0x35F18,0x35F70,0x36390,0x36E70,0x37110,0x37170 --size 0x3000 || exit /b 1
cmake -S port -B build\motorstorm -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl -DPython3_EXECUTABLE="%PYTHON%" -DPS3RECOMP_DIR="%CD%\ps3recomp" -DRECOMP_DIR="%CD%\generated\ppu" -DPORT_SPU_INPUTS="%CD%\generated\decrypted\EBOOT.elf" || exit /b 1
cmake --build build\motorstorm --config Release --parallel 2 || exit /b 1
