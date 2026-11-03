"""T169: RSXI events.jsonl reader. Replaces only bare non-finite numeric tokens (outside JSON strings) with NaN /
Infinity, keeps every valid record and counts what it rejects. usage: from rsxi_parse_t169 import read_events"""
import json, re, sys

_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|-?\b(?:nan(?:\(ind\)|\(snan\))?|inf(?:inity)?)(?![\w.])', re.I)


def _fix(m):
    t = m.group(0)
    if t[0] == '"':
        return t
    return ('-Infinity' if t[0] == '-' else 'Infinity') if 'inf' in t.lower() else 'NaN'


def normalise(line):
    return _TOKEN.sub(_fix, line)


def read_events(path, stats=None):
    """Yield events. stats (dict) gets total, parsed, repaired, rejected and the first 5 rejected lines' numbers."""
    s = stats if stats is not None else {}
    s.update(total=0, parsed=0, repaired=0, rejected=0, rejected_lines=[])
    with open(path, encoding='utf-8', errors='replace') as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            s['total'] += 1
            fixed = normalise(line)
            try:
                e = json.loads(fixed)
            except ValueError:
                s['rejected'] += 1
                if len(s['rejected_lines']) < 5:
                    s['rejected_lines'].append(n)
                continue
            s['parsed'] += 1
            s['repaired'] += fixed != line
            yield e


if __name__ == '__main__':
    st = {}
    for _ in read_events(sys.argv[1], st):
        pass
    print(st)
    sys.exit(1 if st['rejected'] else 0)
