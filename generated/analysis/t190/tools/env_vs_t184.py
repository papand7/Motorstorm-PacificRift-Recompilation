"""T190: the P and B env of run_t190.py against T184 arm P's recorded env (run manifest). No launch."""
import glob, json, sys, tempfile, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('r190', 'generated/analysis/t190/ab/run_t190.py'); r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
def env_of(arm):
    r.ARM = arm; v = r.build_argv(Path(tempfile.mkdtemp()), 'x', False)
    return dict(v[i + 1].split('=', 1) for i in range(len(v)) if v[i] == '--env')
man = json.load(open(glob.glob('generated/runs/*t183-Pp1')[-1] + '/manifest.json'))
def find(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ('env', 'environment', 'env_overrides') and isinstance(v, dict) and 'PS3_SPU_TASK_POOL' in v: return v
            x = find(v)
            if x: return x
    if isinstance(o, list):
        for v in o:
            x = find(v)
            if x: return x
ref = find(man)
if ref is None: sys.exit('no env in manifest: keys ' + str(list(man)))
for arm in ('P', 'B'):
    e = env_of(arm)
    d = {k: (ref.get(k), e.get(k)) for k in sorted(set(ref) | set(e)) if ref.get(k) != e.get(k)}
    print(f'T184 P -> T190 {arm}:', json.dumps(d, indent=0))
