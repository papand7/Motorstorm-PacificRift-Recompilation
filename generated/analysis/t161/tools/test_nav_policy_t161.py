#!/usr/bin/env python3
"""T161: offline tests for nav_policy_t161.NavPolicy (py -3 test_nav_policy_t161.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nav_policy_t161 import NavPolicy, simulate

fails = 0
def check(c, msg):
    global fails
    if not c:
        fails += 1
        print('FAIL:', msg)

# 1. The T158 baseline: SETTLE 6.5, no retry, every page ready at once -> 4 x 6.5 s plus latency.
t_old, p_old, _ = simulate([0.5] * 4, settle_s=6.5, retries=0)
check(t_old is not None and 26.0 <= t_old <= 27.0, f'baseline 4 steps in ~26.4 s (got {t_old})')
# 2. Adaptive policy on the same route: ~4 x 1.5 s.
t_new, p_new, _ = simulate([0.5] * 4)
check(t_new is not None and t_new <= 6.6, f'1.5 s settle reaches the loader in <= 6.6 s (got {t_new})')
check(p_new.presses == 4 and not p_new.manual, 'exactly 4 presses, no manual')
# 3. A slow screen (ready 3 s after the transition): the first press is dropped, the retry lands.
t3, p3, log3 = simulate([0.5, 3.0, 0.5, 0.5])
check(t3 is not None and not p3.manual, f'slow screen recovered by a retry ({log3})')
check(p3.presses == 5 and [r for _, _, r in log3].count('retry') == 1, f'one retry, 5 presses ({log3})')
# The old policy (no retry) also survives that screen only because its settle is longer than 3 s.
t3o, p3o, _ = simulate([0.5, 3.0, 0.5, 0.5], settle_s=6.5, retries=0)
check(t3o is not None and t3o > t3, 'old policy slower on the same route')
# 4. A screen that drops its first accepted-time press too (e.g. focus animation): one retry.
t4, p4, log4 = simulate([0.5] * 4, drop_first={2})
check(t4 is not None and p4.presses == 5, f'dropped press retried once ({log4})')
# 5. A screen that never accepts: bounded, ends in manual after 1 + retries presses on that step.
t5, p5, log5 = simulate([0.5, 1e9, 0.5, 0.5])
check(t5 is None and p5.manual and p5.presses == 1 + 3, f'never-ready screen -> manual after 3 presses ({log5})')
# 6. max_presses bounds the total input even with retries left.
t6, p6, _ = simulate([0.5, 1e9], retries=50, max_presses=9)
check(p6.presses == 9 and p6.manual, f'never more than 9 presses (got {p6.presses})')
# 7. Guards: no press before the main menu, none once the loader is entered, none while the
#    signature keeps changing.
q = NavPolicy()
check(not q.due(0.0, 1, False, False) and not q.due(5.0, 1, False, False), 'no press before the menu')
q = NavPolicy()
q.due(0.0, 1, True, False)
check(not q.due(5.0, 1, True, True), 'no press inside the race loader')
q = NavPolicy()
for i in range(20):
    check(not q.due(i * 1.0, i, True, False), 'signature changing every 1 s -> never quiet for 1.5 s')
check(q.due(21.5, 19, True, False), 'press once quiet for 1.5 s')

# 8. The generated runner (if present) keeps the T158 route, inputs and caps; only nav() differs.
ab = Path(__file__).resolve().parents[1] / 'ab' / 'run_t161.py'
old = Path(__file__).resolve().parents[2] / 't158' / 'ab' / 'run_t158ab.py'
if ab.exists() and old.exists():
    new_s, old_s = ab.read_text(encoding='utf-8'), old.read_text(encoding='utf-8')
    for const in ("ROUTE_FNS = ('0076AF40', '00017420', '00033848', '000338C0', '0008EA00')",
                  'HARD_KILL_S = 200.0', 'RACE_STOP_S = 90.0', "self.press(f'cross {pol.presses}', CROSS, 20)"):
        check(const in new_s, f'runner keeps {const}')
    check('self.SETTLE' not in new_s and 'NavPolicy(max_presses=self.MAX_PRESSES' in new_s, 'nav() uses NavPolicy')
    env_new = new_s[new_s.index('COMMON = {'):new_s.index('ENV = {')]
    env_old = old_s[old_s.index('COMMON = {'):old_s.index('ARMS = {')]
    check(env_new == env_old, 'environment groups identical to T158')
    check("ENV = {**COMMON, **PERF, **TRACE, **T150, **WSTAT, **AOT}" in new_s, 'arms N/F use the T158 arm B environment')

print(f'test_nav_policy_t161: {fails} failure(s); baseline {t_old:.1f} s -> {t_new:.1f} s')
sys.exit(1 if fails else 0)
