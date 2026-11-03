#!/usr/bin/env python3
"""T84B: self-test of vis_report.py on synthetic PT lines in the exact ppu_trace format (v1 and v2).
View 0 ("main") is kicked and waited on but never draws; view 1 ("reflection") draws 2 batches.
  py -3 -I test_vis_report.py"""
import subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
V1 = '''\
[PT] t=1 tid=1 ev=enter pc=00458558 lr=00331E2C depth=3 n=1 r3=10000000 r4=20000000 r6=00000001 m[r3+0x0]=-- m[r3+0x10]=-- m[r3+0x220]=-- m[r3+0x278]=-- m[r4+0x4]=0 m[r4+0x10]=0 m[r4+0x24]=0 m[r4+0x430]=00000000 r31=0
[PT] t=2 tid=1 ev=enter pc=0045CB30 lr=00457CD4 depth=5 n=1 r3=30000000 r4=0FFF0000 r6=00000001 m[r3+0x0]=20000000 m[r3+0x10]=00000000 m[r3+0x220]=31000000 m[r3+0x278]=32000000 m[r4+0x4]=0 m[r4+0x10]=0 m[r4+0x24]=0 m[r4+0x430]=-- r31=0
[PT] t=3 tid=1 ev=enter pc=00458558 lr=00331E94 depth=3 n=2 r3=10000000 r4=21000000 r6=00000001 m[r3+0x0]=-- m[r3+0x10]=-- m[r3+0x220]=-- m[r3+0x278]=-- m[r4+0x4]=0 m[r4+0x10]=0 m[r4+0x24]=0 m[r4+0x430]=00000001 r31=0
[PT] t=4 tid=1 ev=enter pc=0045CB30 lr=00457CD4 depth=5 n=2 r3=40000000 r4=0FFF0000 r6=00000001 m[r3+0x0]=21000000 m[r3+0x10]=00000000 m[r3+0x220]=41000000 m[r3+0x278]=42000000 m[r4+0x4]=0 m[r4+0x10]=0 m[r4+0x24]=0 m[r4+0x430]=-- r31=0
[PT] t=5 tid=2 ev=enter pc=0045CAA8 lr=00944C7C depth=4 n=1 r3=40000000 r4=0 r6=0 m[r3+0x0]=21000000 m[r3+0x10]=0 m[r3+0x220]=41000000 m[r3+0x278]=42000000 m[r4+0x4]=-- m[r4+0x10]=-- m[r4+0x24]=-- m[r4+0x430]=-- r31=0
[PT] t=6 tid=2 ev=enter pc=0050D868 lr=00944D7C depth=4 n=1 r3=0 r4=0FFE0000 r6=0 m[r3+0x0]=-- m[r3+0x10]=-- m[r3+0x220]=-- m[r3+0x278]=-- m[r4+0x4]=50000000 m[r4+0x10]=0000000C m[r4+0x24]=00000001 m[r4+0x430]=-- r31=0
[PT] t=7 tid=2 ev=enter pc=0050D868 lr=00944D7C depth=4 n=2 r3=0 r4=0FFE0000 r6=0 m[r3+0x0]=-- m[r3+0x10]=-- m[r3+0x220]=-- m[r3+0x278]=-- m[r4+0x4]=50000000 m[r4+0x10]=00000003 m[r4+0x24]=00000001 m[r4+0x430]=-- r31=0
[PT] t=8 tid=2 ev=enter pc=0045CAA8 lr=00944C7C depth=4 n=2 r3=30000000 r4=0 r6=0 m[r3+0x0]=20000000 m[r3+0x10]=0 m[r3+0x220]=31000000 m[r3+0x278]=32000000 m[r4+0x4]=-- m[r4+0x10]=-- m[r4+0x24]=-- m[r4+0x430]=-- r31=0
[PT] t=9 tid=2 ev=bb pc=00944DA0 lr=00000000 fn=00944C00 n=1 r3=0
'''
V2 = '''\
[PT] t=2 tid=1 ev=enter pc=0045CB30 lr=00457CD4 depth=5 n=1 r3=30000000 m[[r3+0x0]+0x430]=00000000 m[[r3+0x220]+0x0]=00000140 m[[r3+0x220]+0x4]=00000000 m[[r3+0x220]+0x8]=00000000 m[[r3+0x220]+0xC]=00000140 m[[r3+0x220]+0x10]=00000000 m[[r3+0x220]+0x14]=00000000 m[[r3+0x220]+0x18]=00000000 m[[r3+0x220]+0x1C]=00000000 m[[r3+0x278]+0x0]=00000000 m[[r3+0x278]+0x4]=00000000
[PT] t=4 tid=1 ev=enter pc=0045CB30 lr=00457CD4 depth=5 n=2 r3=40000000 m[[r3+0x0]+0x430]=00000001 m[[r3+0x220]+0x0]=00000140 m[[r3+0x220]+0x4]=0000000F m[[r3+0x220]+0x8]=00000000 m[[r3+0x220]+0xC]=00000000 m[[r3+0x220]+0x10]=00000131 m[[r3+0x220]+0x14]=00000000 m[[r3+0x220]+0x18]=00000000 m[[r3+0x220]+0x1C]=00000000 m[[r3+0x278]+0x0]=0000000C m[[r3+0x278]+0x4]=00000003
'''
EXPECT_V1 = ['view 0: kicks 1 over 1 scene lists; waits [unblended 1]; ExecutePushBuffer 0 batches / 0 entries',
             'view 1: kicks 1 over 1 scene lists; waits [unblended 1]; ExecutePushBuffer 2 batches / 15 entries',
             "bb visits {'00944DA0': 1}"]
EXPECT_V2 = ['PVS counters last [320, 0, 0, 320, 0, 0, 0, 0] max [320, 0, 0, 320, 0, 0, 0, 0]; visible pair last [0, 0]',
             'PVS counters last [320, 15, 0, 0, 305, 0, 0, 0] max [320, 15, 0, 0, 305, 0, 0, 0]; visible pair last [12, 3]']
fails = 0
with tempfile.TemporaryDirectory() as d:
    for name, text, expect in (('v1', V1, EXPECT_V1), ('v2', V2, EXPECT_V2)):
        p = Path(d) / f'{name}.log'
        p.write_text(text, encoding='utf-8')
        out = subprocess.run([sys.executable, '-I', str(HERE / 'vis_report.py'), str(p)],
                             capture_output=True, text=True).stdout
        for e in expect:
            ok = e in out
            fails += not ok
            print(f"[{'PASS' if ok else 'FAIL'}] {name}: {e}")
        if fails:
            print(out)
print(f'test_vis_report: {fails} failure(s)')
sys.exit(1 if fails else 0)
