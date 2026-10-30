#!/usr/bin/env python3
"""T167: [shader-compile] lines of validate_t167's compile runs, per run: compiles, unique variants (by the line's hash), duplicates,
failures, total and worst ms, and how much of it ran on the worker (async=1) and not on the render thread.

  py -3 compile_summary_t167.py <runs/c>
"""
import re, sys
from pathlib import Path

print('run calls unique dup failed total_ms worst_ms render_thread_ms worker_ms')
for d in sorted(Path(sys.argv[1]).iterdir()):
    ls = re.findall(r'\[shader-compile\] .*', (d / 'err.txt').read_text(encoding='utf-8', errors='replace'))
    ms = [float(re.search(r' ms=([\d.]+)', l).group(1)) for l in ls]
    key = [(re.search(r'stage=(\d+)', l).group(1), l.split(' hr=')[1].split(' ', 1)[1].replace(' async=1', '')) for l in ls]
    worker = sum(m for m, l in zip(ms, ls) if ' async=1' in l)
    print(d.name, len(ls), len(set(key)), len(key) - len(set(key)), sum(' hr=0x00000000' not in l for l in ls),
          f'{sum(ms):.0f} {max(ms, default=0):.1f} {sum(ms) - worker:.0f} {worker:.0f}')
