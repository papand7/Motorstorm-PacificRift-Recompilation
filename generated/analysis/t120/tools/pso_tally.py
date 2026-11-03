"""T120: per RSXI frame, draws by pipeline kind and the programs that fell back."""
import sys, collections, glob, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't113', 'tools'))
from ev import events
for f in sorted(glob.glob(sys.argv[1])):
    c = collections.Counter(); fb = collections.Counter()
    for e in events(f):
        if e.get('e') == 'draw':
            p = e.get('native', {}).get('pso'); c[p] += 1
            if p != 'guest_fp': fb[e['guest']['fp']] += 1
    print(os.path.basename(os.path.dirname(f)), dict(c), dict(fb))
