import sys, tempfile, subprocess, glob, os
for d in glob.glob('build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/lib/clang/*/lib/windows'): os.environ['PATH'] = os.path.abspath(d) + os.pathsep + os.environ['PATH']
from pathlib import Path
sys.path.insert(0, 'ps3recomp-t191/tools')
import test_spu_ib_fast as T
tmp = Path(tempfile.mkdtemp(prefix='t191san-'))
for flag in (sys.argv[1:] or ['-fsanitize=address', '-fsanitize=undefined']):
    try:
        exe = T.build(tmp, name='san', extra=(flag, '-g'))
    except subprocess.CalledProcessError as e:
        print(flag, 'BUILD FAILED'); continue
    for args in (['directed'], ['random', '3', '20000', '--tasks'], ['threads', '7', '5000']):
        rc, txt = T.run(exe, *args)
        last = [l for l in txt.splitlines() if 'checks,' in l]
        print(flag, args[0], 'rc', rc, last[-1] if last else txt[-200:])
