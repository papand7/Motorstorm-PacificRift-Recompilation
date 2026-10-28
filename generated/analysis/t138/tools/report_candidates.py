"""T138: which generated/analysis reports and scripts pass `audit_public.py --private-reports`."""
import collections
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
from audit_public import inspect_blob  # noqa: E402

files = sorted(glob.glob(str(ROOT / 'generated/analysis/*/*.md')) +
               glob.glob(str(ROOT / 'generated/analysis/*/tools/*.py')))
reasons = collections.Counter()
passed, blocked = [], {}
for f in files:
    rel = Path(f).relative_to(ROOT).as_posix()
    if '.before_' in rel:
        continue
    r = inspect_blob(rel, Path(f).read_bytes(), private_reports=True)
    if r:
        blocked[rel] = r
        reasons.update(r)
    else:
        passed.append(rel)
out = {'candidates': len(passed) + len(blocked), 'pass': len(passed), 'blocked': len(blocked),
       'reasons': dict(reasons), 'blocked_files': blocked}
print(json.dumps({k: v for k, v in out.items() if k != 'blocked_files'}))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1), encoding='utf-8')
