MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""misc1 (from t108/tools/make_tu.py): exact project compile lines for the changed TUs, from the T96I build
(build/motorstorm-t96i/build.ninja), retargeted at ps3recomp-t108 and
writing objects/logs under generated/analysis/t108/logs/tu. Writes tu_t108.cmd."""
import pathlib, re
M = pathlib.Path(MS_ROOT)
nin = (M / 'build/motorstorm-t96i/build.ninja').read_text(encoding='utf-8', errors='replace')
nin += chr(10) + (M / 'build/motorstorm-t96i/CMakeFiles/rules.ninja').read_text(encoding='utf-8', errors='replace')
want = ['libs/font/cellFont.c', 'libs/system/cellSaveData.c', 'runtime/ppu/ppu_fs.cpp']
import sys
TREE, TAG = sys.argv[1], sys.argv[2]   # ps3recomp-misc1 new, ps3recomp-t108 base
blocks = nin.split('\nbuild ')
out = ['@echo off', 'call "C:\\Program Files\\Microsoft Visual Studio\\18\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul || exit /b 1']
logs = M / 'generated/analysis/misc1/logs' / ('tu_' + TAG)
logs.mkdir(parents=True, exist_ok=True)
found = {}
for b in blocks:
    head = b.split('\n', 1)[0]
    for w in want:
        if (w.replace('/', '\\') + '.obj:') in head:
            found[w] = b
for w in want:
    b = found.get(w)
    assert b, w
    rule = re.match(r'(\S+): (\S+)', b).group(2)
    flags = re.search(r'\n  FLAGS = (.*)', b).group(1)
    defs = (re.search(r'\n  DEFINES = (.*)', b) or [None, ''])[1]
    incs = (re.search(r'\n  INCLUDES = (.*)', b) or [None, ''])[1]
    rr = re.search(r'\nrule ' + re.escape(rule) + r'\n  depfile.*?\n  command = (.*?)\n', nin, re.S) or \
         re.search(r'\nrule ' + re.escape(rule) + r'\n(?:  .*\n)*?  command = (.*?)\n', nin)
    cmd = rr.group(1)
    src = re.search(r'\S+\.(?:c|cpp)\b', b.split('\n', 1)[0].split(': ', 1)[1]).group(0)
    name = pathlib.Path(w).name
    obj = str(logs / (name + '.obj'))
    srcnew = str(M / TREE / w.replace('/', '\\'))
    c = cmd.replace('$DEFINES', defs).replace('$INCLUDES', incs).replace('$FLAGS', flags)
    c = c.replace('$out', obj).replace('$in', srcnew).replace('$DEP_FILE', obj + '.d')
    c = c.replace('${LAUNCHER}', '').replace('${CODE_CHECK}', '').replace('$TARGET_COMPILE_PDB', str(logs / 'tu.pdb'))
    c = re.sub(r'\$\w+', '', c)
    c = re.sub(r'ps3recomp-t96i', TREE, c)
    out.append(c + f' > "{logs / (name + ".log")}" 2>&1')
    out.append(f'echo {name} rc=%ERRORLEVEL%')
(M / 'generated/analysis/misc1/tools' / ('tu_' + TAG + '.cmd')).write_text('\n'.join(out) + '\n')
print('\n'.join(l[:300] for l in out[2:]))
