"""Make tools/build_samp.cmd from ppucc2/tools/build_all_100_ppucc2.cmd (overlap60).
Only PS3RECOMP_DIR (isolated D:\\motorstorm\\ps3recomp-samp), the build dir, the LTO cache and RECOMP_DIR (arg 3) differ."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, '..', '..', 'ppucc2', 'tools', 'build_all_100_ppucc2.cmd')
s = open(src).read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)


rep(r'rem ppucc2: copy of vksync/tools/build_all_100_next.cmd;',
    r'rem overlap60: copy of ppucc2/tools/build_all_100_ppucc2.cmd. PS3RECOMP_DIR = D:\motorstorm\ps3recomp-samp (PS3_SAMPLE_EXACT);'
    r' build dir and LTO cache on D:. Arg 3: main (ppu-v100-twin) or cc2 (ppu-v100-ppucc2).' + '\nrem ppucc2 (original note):')
rep(r'set "PR=ps3recomp-vkgame" & set "PO=port-vkgame"', r'set "PO=port-vkgame" & set "WHICH=%~3"')
rep(r'if not defined T158_JOBS set "T158_JOBS=6"',
    'if not defined T158_JOBS set "T158_JOBS=6"\n'
    r'if /i "%WHICH%"=="main" ( set "RD=%CD%\generated\ppu-v100-twin" ) else if /i "%WHICH%"=="cc2" ( set "RD=D:\motorstorm\ppucc2\ppu-v100-ppucc2" ) else ( echo arg 3: main or cc2 & exit /b 2 )')
rep(r'  set "BD=motorstorm-vkgame-100-ppucc2"', r'  set "BD=D:\motorstorm\build-samp-%WHICH%"')
rep(r'/lldltocache:D:\motorstorm\ppucc2\lto-cache', r'/lldltocache:D:\motorstorm\lto-samp-%WHICH%')
rep(r'if not exist build\%BD%\build.ninja (', r'if not exist %BD%\build.ninja (')
rep(r'cmake -S %PO% -B build\%BD% -G Ninja', r'cmake -S %PO% -B %BD% -G Ninja')
rep(r'-DPS3RECOMP_DIR="%CD%\%PR%" -DRECOMP_DIR="D:\motorstorm\ppucc2\ppu-v100-ppucc2"',
    r'-DPS3RECOMP_DIR="D:\motorstorm\ps3recomp-samp" -DRECOMP_DIR="%RD%"')
rep(r'cmake --build build\%BD% --parallel %T158_JOBS%', r'cmake --build %BD% --parallel %T158_JOBS%')
open(os.path.join(HERE, 'build_samp.cmd'), 'w').write(s)
print('written')
