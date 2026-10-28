@echo off
rem Resolve host tool locations for the build scripts. Called from a caller's
rem setlocal scope. Override by presetting VCVARS or PYTHON.
if not defined VCVARS (
  set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
)
if not defined VCVARS if exist "%VSWHERE%" (
  for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -prerelease -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VCVARS=%%i\VC\Auxiliary\Build\vcvars64.bat"
)
if not defined VCVARS set "VCVARS=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
if not defined PYTHON if exist "C:\Program Files\PyManager\python.exe" set "PYTHON=C:\Program Files\PyManager\python.exe"
if not defined PYTHON (
  for /f "usebackq delims=" %%i in (`py -3 -c "import sys;print(sys.executable)" 2^>nul`) do set "PYTHON=%%i"
)
if not defined PYTHON (
  echo Python 3 not found; set PYTHON to python.exe. 1>&2
  exit /b 1
)
exit /b 0
