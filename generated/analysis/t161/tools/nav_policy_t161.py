#!/usr/bin/env python3
"""T161: menu-navigation pacing for the race-benchmark controller (pure logic, no game).

The T154-T158 runners press CROSS once the route signature (route-function entries + GUI page
loads) has been quiet for SETTLE = 6.5 s, require a transition within 6 s, and otherwise give up
(nav_manual). In every logged run each page loaded 0.1-0.5 s after its press, so the four route
presses cost ~4 x 6.5 s of pure waiting (T161 FAST_RACE_BENCHMARK.md section 2).

NavPolicy keeps the same route and the same inputs (CROSS with default focus, at most 9 presses,
none after the race loader is entered) and changes only *when* a press is sent:
  - settle_s: quiet time before a press (default 1.5 s);
  - confirm_s: time a press has to produce a route transition (default 6 s, as before);
  - retries: a press with no transition is re-sent after another settle, at most this many times
    per step (default 2), before nav_manual. A screen that was still animating in and dropped the
    first press therefore costs one more settle, not the run.
Each retry counts against max_presses, so the total input stays bounded.
"""


class NavPolicy:
    def __init__(self, settle_s=1.5, confirm_s=6.0, retries=2, max_presses=9):
        self.settle_s, self.confirm_s, self.retries, self.max_presses = settle_s, confirm_s, retries, max_presses
        self.presses = 0          # CROSS presses sent
        self.step = 0             # route steps confirmed
        self.fails = 0            # unconfirmed presses on the current step
        self.manual = False
        self.quiet_t = None       # when the signature last changed
        self.sig = None

    def due(self, now, sig, menu_seen, in_loader):
        """True when a CROSS press should be sent now."""
        if self.manual or in_loader or not menu_seen or self.presses >= self.max_presses:
            return False
        if self.quiet_t is None or sig != self.sig:
            self.quiet_t, self.sig = now, sig
            return False
        return now - self.quiet_t >= self.settle_s

    def pressed(self):
        self.presses += 1

    def result(self, now, sig_after, changed):
        """Record whether the press produced a route transition within confirm_s.
        Returns 'ok', 'retry' or 'manual'."""
        if changed:
            self.step += 1
            self.fails = 0
            self.quiet_t, self.sig = now, sig_after
            return 'ok'
        self.fails += 1
        if self.fails > self.retries or self.presses >= self.max_presses:
            self.manual = True
            return 'manual'
        self.quiet_t = now        # wait another settle before re-sending
        return 'retry'


def simulate(page_ready_after, settle_s=1.5, confirm_s=6.0, retries=2, max_presses=9,
             drop_first=(), dt=0.05, t_menu=0.0, n_steps=4, horizon=200.0):
    """Offline model of the route: step i's screen accepts input page_ready_after[i] s after the
    previous transition (presses before that are dropped, as are the first presses of the steps in
    drop_first); an accepted press changes the signature 0.1 s later. Returns (t_loader, policy, log)."""
    pol = NavPolicy(settle_s, confirm_s, retries, max_presses)
    t, sig, log = t_menu, 0, []
    ready_t = t_menu + page_ready_after[0]
    dropped = set()
    while t < horizon and pol.step < n_steps and not pol.manual:
        if pol.due(t, sig, True, False):
            pol.pressed()
            i = pol.step
            accepted = t >= ready_t and not (i in drop_first and i not in dropped)
            if i in drop_first and t >= ready_t:
                dropped.add(i)
            if accepted:
                t += 0.1
                sig += 1
                r = pol.result(t, sig, True)
                if pol.step < n_steps:
                    ready_t = t + page_ready_after[pol.step]
            else:
                t += confirm_s
                r = pol.result(t, sig, False)
            log.append((round(t, 2), i, r))
            continue
        t += dt
    return (t if pol.step >= n_steps else None), pol, log
