"""T169: test_spurs_kick_wake on three revisions, interleaved so drift can't look like a revision effect, plus two forced conditions.
Records every kick median and p90, the timer resolution before each run, the power scheme and the busiest processes. Run under env_t169.cmd from the repo root.
usage: py -3 spurs_kick_matrix_t169.py <out.json>"""
import ctypes, io, json, multiprocessing as mp, os, re, subprocess, sys, tarfile, tempfile, time
from pathlib import Path

ROOT = Path.cwd()
REPO = ROOT / 'ps3recomp-t169'
REVS = {'current': '774c81d', 'prev_pass': '001a56f', 'baseline': 'b1eb158'}
RX = re.compile(r'\[(off|on)\] rc=(\d+) (.*)')
RK = re.compile(r'(\d+) kicks median (\d+) us p90 (\d+) us')


def timer_res():
    a, b, c = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
    ctypes.windll.ntdll.NtQueryTimerResolution(ctypes.byref(a), ctypes.byref(b), ctypes.byref(c))
    return {'coarsest_ms': a.value / 1e4, 'finest_ms': b.value / 1e4, 'current_ms': c.value / 1e4}


def spin(stop):
    while not stop.is_set():
        sum(range(2000))


def hold_timer(stop):
    ctypes.windll.winmm.timeBeginPeriod(1)
    stop.wait()


def run(src, cond):
    stop = mp.Event()
    ps = []
    if cond == 'timer_1ms':
        ps = [mp.Process(target=hold_timer, args=(stop,))]
    elif cond == 'cpu_load':
        ps = [mp.Process(target=spin, args=(stop,)) for _ in range(os.cpu_count())]
    for p in ps:
        p.start()
    time.sleep(1.0)
    rec = {'condition': cond, 'timer_before': timer_res(), 'wall': time.time()}
    t0 = time.time()
    r = subprocess.run([sys.executable, str(src / 'tools/test_spurs_kick_wake.py')], capture_output=True, text=True, errors='replace', timeout=900)
    rec.update(seconds=round(time.time() - t0, 1), rc=r.returncode, timer_after=timer_res())
    for l in r.stdout.splitlines():
        m = RX.match(l)
        if m:
            rec[m[1]] = [{'kicks': int(a), 'median_us': int(b), 'p90_us': int(c)} for a, b, c in RK.findall(m[3])]
        if l.startswith('inline kick'):
            rec['summary'] = l
    stop.set()
    for p in ps:
        p.join()
    return rec


if __name__ == '__main__':
    out = Path(sys.argv[1])
    data = {'cpu_count': os.cpu_count(), 'power': subprocess.run(['powercfg', '/getactivescheme'], capture_output=True, text=True).stdout.strip(),
            'revs': REVS, 'runs': []}
    with tempfile.TemporaryDirectory() as d:
        src = {}
        for k, rev in REVS.items():
            tar = subprocess.run(['git', '-C', str(REPO), 'archive', rev], capture_output=True, check=True).stdout
            src[k] = Path(d) / k
            src[k].mkdir()
            with tarfile.open(fileobj=io.BytesIO(tar)) as t:
                t.extractall(src[k], filter='data')
        data['tree_diff_current_prev'] = subprocess.run(['git', '-C', str(REPO), 'diff', '--stat', REVS['prev_pass'], REVS['current'], '--', 'libs/spurs', 'runtime', 'tests', 'tools/test_spurs_wws_stress.py', 'tools/test_spurs_kick_wake.py'], capture_output=True, text=True).stdout
        data['tree_diff_current_base'] = subprocess.run(['git', '-C', str(REPO), 'diff', '--stat', REVS['baseline'], REVS['current'], '--', 'libs/spurs', 'runtime', 'tests', 'tools/test_spurs_wws_stress.py', 'tools/test_spurs_kick_wake.py'], capture_output=True, text=True).stdout
        plan = [(k, 'idle') for _ in range(3) for k in REVS] + [('current', 'timer_1ms'), ('baseline', 'timer_1ms'), ('current', 'cpu_load'), ('baseline', 'cpu_load'), ('current', 'idle')]
        for k, cond in plan:
            rec = run(src[k], cond)
            rec['rev'] = k
            data['runs'].append(rec)
            out.write_text(json.dumps(data, indent=1))
            print(k, cond, 'rc', rec['rc'], rec.get('summary'), rec['timer_before'], flush=True)
