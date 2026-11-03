"""T90: classify every run that pressed the intro skip. For each: the rsx-hb heartbeat ms values
around the press, the largest heartbeat gap spanning the press, and whether the bink intro was
skipped (the intro stream fd is followed by another .bik/.gui open soon, or decode stops early).
Skip evidence used: '[fs] open' of a path after the intro open, counted in heartbeat lines until it."""
import re, sys
from pathlib import Path
RUNS = Path(__file__).resolve().parents[3] / 'runs'
hb = re.compile(r'\[rsx-hb\] ms=(\d+) frames=(\d+) draw_frames=(\d+) last_draws=(\d+)')
for d in sorted(RUNS.iterdir()):
    f = d / 'stderr.log'
    if not f.is_file():
        continue
    lines = f.read_text(errors='replace').splitlines()
    ip = next((i for i, l in enumerate(lines) if '[pad-trigger] press' in l), None)
    if ip is None:
        continue
    ir = next((i for i in range(ip, len(lines)) if '[pad-trigger] release' in lines[i]), ip)
    before = [hb.search(l) for l in lines[:ip]]
    before = [m for m in before if m][-1:]
    after = [m for m in (hb.search(l) for l in lines[ir:ir + 40000]) if m][:6]
    if not before or not after:
        print(f'{d.name:45s} no heartbeat'); continue
    b = before[0]; a0 = after[0]
    gap = int(a0.group(1)) - int(b.group(1))
    fr = int(a0.group(2)) - int(b.group(2))
    ld = [int(m.group(4)) for m in after]
    # first open after the intro open, and how many heartbeats until it
    io = next(i for i in range(ip, -1, -1) if 'gui_intro_' in lines[i] and '[fs] open' in lines[i])
    nxt = next(((i, lines[i]) for i in range(io + 1, len(lines)) if '[fs] open' in lines[i]), (None, ''))
    nhb = sum(1 for l in lines[io:nxt[0]] if '[rsx-hb]' in l) if nxt[0] else -1
    name = re.sub(r".*open '([^']*)'.*", r'\1', nxt[1]).split('/')[-1]
    print(f'{d.name:45s} hbgap={gap:5d}ms frames={fr:3d} last_draws_after={ld} next_open=+{nhb}hb {name}')
