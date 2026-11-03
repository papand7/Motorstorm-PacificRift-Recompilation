"""T113: lenient RSXI events.jsonl reader (the writer prints C nan/inf in vp_consts)."""
import json, re
_BAD = re.compile(r'(?<=[\[,])\s*-?(nan|inf)(?=[,\]])', re.I)
def events(path):
    for l in open(path, encoding='utf-8', errors='replace'):
        l = l.strip()
        if not l: continue
        try: yield json.loads(l)
        except Exception:
            try: yield json.loads(_BAD.sub('null', l))
            except Exception: pass
