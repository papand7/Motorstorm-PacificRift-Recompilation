#!/usr/bin/env python3
"""T167: every stop condition of run_guard_t167 on synthetic run directories, then, if present, the real T162 runs
(A1 has too few heavy frames for the default but no failure, B1 stops on the Present timeout). No game is launched."""
import glob, os, sys, tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_guard_t167 as G

fails = 0


def check(ok, what):
    global fails
    print(f"[{'PASS' if ok else 'FAIL'}] {what}")
    fails += not ok


def frame(g, draws=2000, wait=0.1):
    return f'[rsx-frame-perf] gframe={g} pass={g} wall_ms=33.0 | passes=1 draw_calls={draws} | submit_ms=0.1 wait_ms={wait} present_ms=0.1 | other_ms=1'


def make(root, name, err=None, out='', summary='termination: timeout (wall-clock timeout 195.0 s)\n', ctl='[  130.00] race_entry {}\n'):
    d = Path(root) / name
    d.mkdir()
    (d / 'stderr.log').write_text('\n'.join(frame(i) for i in range(800)) + '\n' if err is None else err)
    (d / 'stdout.log').write_text(out)
    (d / 'summary.md').write_text(summary)
    (d / 'controller.log').write_text(ctl)
    return d


def post(d, code=0):
    return G.post_failures(d, d / 'controller.log', code)


def has(fl, s):
    return any(s in x for x in fl)


with tempfile.TemporaryDirectory() as t:
    check(post(make(t, 'good')) == [], 'a clean run passes')
    check(has(post(make(t, 'rc'), 3), 'exit code 3'), 'nonzero exit code')
    check(has(post(make(t, 'term', summary='termination: stop_line (x)\n')), 'termination'), 'termination by a stop line')
    check(has(post(make(t, 'noterm', summary='')), 'no termination'), 'no termination line')
    check(has(post(make(t, 'gc', out='Gc ERROR: GcKernel::Present() Timeout!\n')), 'Present() Timeout'), 'GcKernel::Present() Timeout')
    check(has(post(make(t, 'ctl', ctl='[  130.00] race_entry {}\n[  131.00] error {"x": 1}\n')), 'controller error'), 'controller error')
    check(has(post(make(t, 'tb', ctl='[  130.00] race_entry {}\nTraceback (most recent call last):\n')), 'controller error'), 'controller traceback')
    check(has(post(make(t, 'rm', out='[D3D12] FENCE STUCK 2s: want 5 got 4 removed=0x887A0006\n')), 'device removal'), 'device removal')
    check(not has(post(make(t, 'rm0', out='[D3D12] FENCE STUCK 2s: want 5 got 4 removed=0x00000000\n')), 'device removal'), 'removed=0 is not a removal')
    check(has(post(make(t, 'pf', out='[D3D12] Present failed hr=0x1\n')), 'Present failed'), 'Present failed')
    check(has(post(make(t, 'fifo', out='FIFO resync (unmapped-JUMP) at io 0x1\n')), 'FIFO resync'), 'FIFO resync')
    check(has(post(make(t, 'mark', ctl='')), 'race_entry'), 'missing race_entry marker')
    check(has(post(make(t, 'noerr', err='')), 'no stderr'), 'missing log')
    few = '\n'.join(frame(i) for i in range(300)) + '\n'
    check(has(post(make(t, 'race', err=few)), 'race frames'), 'missing race frames')
    short = '\n'.join(frame(i) for i in range(650)) + '\n'
    check(has(post(make(t, 'heavy', err=short)), 'heavy frames'), 'too few heavy frames')
    menu = '\n'.join(frame(i, draws=10) for i in range(800)) + '\n'
    check(has(post(make(t, 'menu', err=menu)), 'race frames'), 'frames, but no race')
    slow = '\n'.join(frame(i, wait=84.0 if i < 100 else 0.1) for i in range(800)) + '\n'
    check(has(post(make(t, 'slow', err=slow)), '84 ms'), 'the 84 ms mode invalidates a run')
    def spurs(rates):
        out = [frame(i) for i in range(800)]
        for k, r in enumerate(rates):
            out.append(f'[rsx-hb] ms={k * 10000} frames=1')
            out.append(f'[spurs-busy] sn=0 runs={r} busy_ms=1.0')
        return NL.join(out) + NL
    NL = chr(10)
    check(G.spurs_collapse(spurs([3800] * 6)) == [], 'steady SPURS rate: no collapse')
    check(G.spurs_collapse(spurs([3800, 3800, 3800, 30000, 80000, 3000])) == [], 'a rising SPURS rate at race entry is no collapse')
    check(G.spurs_collapse(spurs([3800] * 4 + [255] * 3 + [100])) == [40, 50, 60], 'the T167 A1 collapse is found, the partial last window is not')
    check(has(post(make(t, 'coll', err=spurs([3800] * 4 + [255] * 3 + [100]))), 'SPURS rate collapsed'), 'a collapse invalidates a run')
    check(has(post(make(t, 'tres', err=few + '[timer-res] ms=1 sleep1_ms=15.60 coarse=1 iconic=1 visible=1 foreground=0' + NL)), 'host timer coarse'), 'a coarse timer invalidates a run')
    check(not has(post(make(t, 'tres0', err='[timer-res] ms=1 sleep1_ms=1.60 coarse=0 iconic=0 visible=1 foreground=1' + NL + few)), 'host timer coarse'), 'a fine timer does not')
    check(has(post(make(t, 'nosum', summary='')), 'no summary.md'), 'missing summary.md')
    check(has(post(make(t, 'noctl', ctl='')), 'no controller log'), 'missing controller log')
    late = make(t, 'late', ctl='[  180.00] race_entry {}' + NL)
    check(has(G.post_failures(late, late / 'controller.log', 0, race_deadline_s=175.0), 'deadline'), 'a late race entry invalidates a run')
    check(not has(G.post_failures(late, late / 'controller.log', 0), 'deadline'), 'no deadline unless asked')
    exe = Path(t) / 'x.exe'
    exe.write_bytes(b'abc')
    good = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    check(G.pre_failures(exe, good, False) == [], 'pre: the pinned hash passes')
    check(has(G.pre_failures(exe, '00' * 32, False), 'hash mismatch'), 'pre: hash mismatch')
    check(has(G.pre_failures(Path(t) / 'no.exe', good, False), 'missing'), 'pre: missing executable')
    check(has(G.pre_failures(exe, good, True), 'remote session'), 'pre: remote session')
    check(G.pre_failures(exe, good, True, allow_remote=True) == [], 'pre: a remote session can be allowed explicitly')

GEN = Path(__file__).resolve().parents[3]
runs = str(GEN / 'runs') + '/'
ctl = str(GEN / 'analysis/t162/ab') + '/'
b1, a1 = glob.glob(runs + '*-t162-BB1'), glob.glob(runs + '*-t162-AA1')
if b1 and a1:
    fb = G.post_failures(b1[0], glob.glob(ctl + 'runtime-B1-*/controller.log')[0], 0)
    fa = G.post_failures(a1[0], glob.glob(ctl + 'runtime-A1-*/controller.log')[0], 0)
    print('real B1:', fb)
    print('real A1:', fa)
    check(has(fb, 'Present() Timeout') and has(fb, 'race_entry') and has(fb, 'termination'), 'the real B1 stops the sequence')
    check(has(fa, 'heavy frames') and not has(fa, 'Timeout') and not has(fa, '84 ms'), 'the real A1: too few heavy frames, nothing else')
else:
    print('skip: no T162 runs here')
print(f'test_run_guard_t167: {fails} failure(s)')
sys.exit(1 if fails else 0)
