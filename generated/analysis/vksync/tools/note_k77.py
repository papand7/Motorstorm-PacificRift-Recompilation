r"""Adds the Kk77 (PGO + ISA build) result to PERF_60FPS.md, after the Kk71-Kk76 table notes.
Keeps the file's line endings (it is CRLF).
usage: py -3 note_k77.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'PERF_60FPS.md'
s = p.read_bytes().decode('utf-8')
nl = '\r\n' if '\r\n' in s else '\n'
anchor = 'clean races wait 4-5 ms a frame.' + nl
i = s.find(anchor)
assert i >= 0, 'anchor not found'
if 'PGO + ISA, Kk77' in s:
    raise SystemExit('already added')
add = r'''
**PGO + ISA, Kk77** (2026-11-05): `tools/build_pgo.cmd isa build/pgo/ms2.profdata` ->
`build/motorstorm-vkgame-pgoisa`, exe 1a5c5a60 (`.keep-1a5c5a60`): the PGO build plus AVX2, BMI1/2, LZCNT,
MOVBE, POPCNT and `-mtune=znver5`, with `-ffp-contract=off` and no `-mfma`, so float results don't change.
Own SPIR-V cache `ab2/spirv_cache_isa` (`set REWARM_BD=build\motorstorm-vkgame-pgoisa`, then
`tools/build_spirv_rewarm_pgo.cmd <dir>`: 296 of 296 translated); arm from `tools/add_arm_k77.py`.

| Run | Exe | Mcycles/flip | frame p50 (ms) | present wait (ms/frame) |
|---|---|---|---|---|
| Kk77 | PGO + ISA | 150.1 | 48.8 | 11.6 (NightfireDriving and bf1943_stageB started during the run) |

- **HYPOTHESIS (no gain):** under outside load like Kk76's (present wait 11.8), Kk77 is +12 % cycles on base
  Kk76 and +32 % on PGO Kk75. One contaminated run, but nothing in it argues for keeping the ISA flags. No
  unlifted SPU calls interpreted. Pin restored to base 9531e520.
'''
j = i + len(anchor)
p.write_bytes((s[:j] + add.replace('\n', nl) + s[j:]).encode('utf-8'))
print('ok')
