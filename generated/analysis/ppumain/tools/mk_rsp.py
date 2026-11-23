#!/usr/bin/env python3
"""Write the exe link response file of a CMake/Ninja build dir from build.ninja (no cmake re-run)."""
import re, sys
from pathlib import Path
bd = Path(sys.argv[1])
txt = (bd / 'build.ninja').read_text(encoding='utf-8', errors='replace').split('\n')
i = next(k for k, l in enumerate(txt) if l.startswith('build MotorStormPacificRiftRecomp.exe:'))
line = txt[i]
def split(s):
    out, cur, j = [], '', 0
    while j < len(s):
        ch = s[j]
        if ch == '$' and j + 1 < len(s):
            cur += s[j + 1]; j += 2; continue
        if ch == ' ':
            if cur: out.append(cur)
            cur = ''
        else:
            cur += ch
        j += 1
    if cur: out.append(cur)
    return out
toks = split(line.split(':', 1)[1] if False else line[len('build MotorStormPacificRiftRecomp.exe: '):])
rule, toks = toks[0], toks[1:]
ins = []
for t in toks:
    if t in ('|', '||', '|@'): break
    ins.append(t)
vars_ = {}
for l in txt[i + 1:]:
    if not l.startswith('  '): break
    k, v = l.strip().split(' = ', 1) if ' = ' in l else (l.strip().rstrip(' ='), '')
    vars_[k] = v
rsp = '\n'.join(ins) + ' ' + vars_.get('LINK_PATH', '') + ' ' + vars_.get('LINK_LIBRARIES', '')
(bd / 'CMakeFiles' / 'MotorStormPacificRiftRecomp.rsp').write_text(rsp, encoding='utf-8')
print(rule, len(ins), 'inputs;', 'LINK_FLAGS', vars_.get('LINK_FLAGS'))
