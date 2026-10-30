#!/usr/bin/env python3
"""T167: ab_seq_t167's decisions with stubs. No game is launched."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ab_seq_t167 as Q

fails = 0


def check(ok, what):
    global fails
    print(f"[{'PASS' if ok else 'FAIL'}] {what}")
    fails += not ok


def run(states=None, games=0, post=None, wait=100.0, pre=None):
    it = iter(states or [])
    last = ['disconnected']

    def state():
        last[0] = next(it, last[0])
        return last[0]
    calls, msgs = [], []
    r = Q.sequence('x', wait, msgs.append, state=state, games=lambda: games, launcher=lambda a, t: calls.append((a, t)) or 0,
                   post=post or (lambda t, c: []), pre=pre or (lambda *a, **k: []), exe='e', sleep=lambda s: None, step=20.0)
    return r, calls, msgs


r, c, _ = run()
check(r == ['A', 'B'] and c == [('A', 'A1'), ('B', 'B1')], 'clean: A then B, once each')
r, c, _ = run(states=['remote'] * 100, wait=40)
check(not c, 'an active remote session launches nothing')
r, c, _ = run(games=1, wait=40)
check(not c, 'another game process launches nothing')
r, c, _ = run(post=lambda t, code: ['GcKernel::Present() Timeout'] if t == 'A1' else [])
check(r == ['A'] and len(c) == 1, 'a failed A stops before B, no retry')
r, c, _ = run(post=lambda t, code: ['x'] if t == 'B1' else [])
check(r == ['A', 'B'] and len(c) == 2, 'a failed B is not retried')
r, c, m = run(pre=lambda *a, **k: ['executable hash mismatch'])
check(not c and any('hash' in x for x in m), 'a hash mismatch launches nothing')
r, c, m = run(states=['disconnected', 'disconnected', 'disconnected', 'remote'])
check(r == [] or len(c) < 2, 'a session change stops the sequence')
print(f'test_ab_seq_t167: {fails} failure(s)')
sys.exit(1 if fails else 0)
