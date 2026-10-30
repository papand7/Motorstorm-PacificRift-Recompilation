#!/usr/bin/env python3
"""T167: the authorized A/B: one launch of A, then one of B, no retries. Waits for a local-console or disconnected session.

  py -3 ab_seq_t167.py run --sha <sha256> [--wait-s 14400] [--log <file>]
  py -3 ab_seq_t167.py dry --sha <sha256>

A launch starts only if the session is local or disconnected, no game process runs, and run_guard's pre check passes. The session is
sampled every second during a launch. B starts only if A left the session class unchanged, had no second game process, and passed
run_guard's post check; B must find the same class as A. Windows: SM_REMOTESESSION can stay set in a disconnected session, so the
state comes from WTSQuerySessionInformation."""
import argparse, ctypes, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_guard_t167 as G

AB = HERE.parent / 'ab'
EXE = AB / 'exe_g' / 'MotorStormPacificRiftRecomp.exe'
NAME = EXE.name
HOST_MARGIN_S = 240   # the runner's own host cap is 210 s; this only stops a hung wrapper
NL = chr(10)


def session_class():
    """'local', 'disconnected', 'remote' or 'other' for this process's session."""
    wts = ctypes.windll.wtsapi32

    def query(info):
        buf, n = ctypes.c_void_p(), ctypes.c_ulong()
        if not wts.WTSQuerySessionInformationW(None, 0xFFFFFFFF, info, ctypes.byref(buf), ctypes.byref(n)):
            return None
        v = ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint16 if info == 16 else ctypes.c_uint32)).contents.value
        wts.WTSFreeMemory(buf)
        return v
    state, proto = query(8), query(16)    # WTSConnectState (0 active, 4 disconnected), WTSClientProtocolType (0 console, 2 RDP)
    if state == 4:
        return 'disconnected'
    if state == 0:
        return 'local' if proto == 0 else 'remote'
    return 'other'


def game_count():
    t = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {NAME}', '/NH'], capture_output=True, text=True).stdout
    return t.lower().count(NAME.lower())


def launch(arm, tag):
    r = subprocess.run([sys.executable, str(AB / 'run_t167.py'), 'launch', arm, tag], capture_output=True, text=True, errors='replace',
                       timeout=HOST_MARGIN_S)
    (AB / f'launch_{tag}.txt').write_text(r.stdout + r.stderr, encoding='utf-8')
    return r.returncode


def newest_rt(tag):
    d = sorted(AB.glob(f'runtime-{tag}-*'))
    return d[-1] if d else None


def post_check(tag, code):
    rt = newest_rt(tag)
    if not rt:
        return ['no runtime directory']
    log = (rt / 'wrapper.log').read_text(encoding='utf-8', errors='replace')
    i = log.rfind('run_dir=')
    if i < 0:
        return ['no run_dir in wrapper.log']
    run = log[i + 8:].split(' leftover_process')[0].strip()
    return G.post_failures(run, rt / 'controller.log', code, min_race=500, min_heavy=0)


def sequence(sha, wait_s, log, state=session_class, games=game_count, launcher=launch, post=post_check, pre=G.pre_failures, exe=EXE,
             sleep=time.sleep, step=20.0):
    """Returns the arms launched. Nothing here retries."""
    waited = 0.0
    while state() not in ('local', 'disconnected') or games():
        if waited >= wait_s:
            log(f'gave up after {waited:.0f} s: session {state()}, game processes {games()}; nothing launched')
            return []
        sleep(step)
        waited += step
    sleep(step)     # let a fresh disconnect settle
    cls, done = state(), []
    log(f'session {cls}')
    for arm, tag in (('A', 'A1'), ('B', 'B1')):
        now = state()
        fails = pre(exe, sha, True, allow_remote=True)
        if now != cls:
            fails.append(f'session {now}, the sequence started in {cls}')
        if now not in ('local', 'disconnected'):
            fails.append(f'session {now}')
        if games():
            fails.append('another game process')
        if fails:
            log(f'{arm}: not launched: {fails}')
            return done
        seen, conc, stop = set(), [0], threading.Event()

        def watch():
            while not stop.wait(1.0):
                seen.add(state())
                conc[0] = max(conc[0], games())
        th = threading.Thread(target=watch, daemon=True)
        th.start()
        log(f'{arm}: launch')
        code = launcher(arm, tag)
        stop.set()
        th.join()
        seen.add(state())
        done.append(arm)
        fails = post(tag, code)
        if seen != {cls}:
            fails.append(f'session changed during the launch: {sorted(seen)}')
        if conc[0] > 1:
            fails.append(f'{conc[0]} game processes at once')
        log(f'{arm}: exit {code}; post: {fails or "ok"}')
        if fails:
            log('sequence stopped')
            return done
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('run', 'dry'))
    ap.add_argument('--sha', required=True)
    ap.add_argument('--wait-s', type=float, default=14400.0)
    ap.add_argument('--log', default=str(AB / 'seq.log'))
    a = ap.parse_args()

    def log(s):
        line = f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {s}'
        print(line, flush=True)
        with open(a.log, 'a', encoding='utf-8') as f:
            f.write(line + NL)
    if a.mode == 'dry':
        print('session', session_class(), 'game processes', game_count(), 'pre', G.pre_failures(EXE, a.sha, True, allow_remote=True))
        for arm in 'AB':
            r = subprocess.run([sys.executable, str(AB / 'run_t167.py'), 'dryrun', arm], capture_output=True, text=True, errors='replace')
            print(arm, 'rc', r.returncode, r.stdout, r.stderr[-400:])
            if r.returncode:
                return 1
        return 0
    done = sequence(a.sha, a.wait_s, log)
    log(f'launched {done}')
    return 0 if done == ['A', 'B'] else 1


if __name__ == '__main__':
    sys.exit(main())
