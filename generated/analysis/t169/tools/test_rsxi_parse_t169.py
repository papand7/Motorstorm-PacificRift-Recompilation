"""T169: regression test for rsxi_parse_t169: tokens fixed, strings untouched, rejects counted."""
import json, math, os, tempfile
from rsxi_parse_t169 import normalise, read_events

assert math.isnan(json.loads(normalise('[0.5,-nan,nan]'))[1])
assert json.loads(normalise('[-inf,inf]')) == [-math.inf, math.inf]
assert math.isnan(json.loads(normalise('[-nan(ind)]'))[0])
assert json.loads(normalise('{"s":"-nan inf nan \\" -nan"}'))['s'] == '-nan inf nan " -nan'
assert json.loads(normalise('{"nan":1,"inflate":"x","n":1e5}')) == {'nan': 1, 'inflate': 'x', 'n': 1e5}
with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as f:
    f.write('{"a":-nan}\n{"b":1}\n{broken\n\n{"s":"-nan"}\n')
st = {}
ev = list(read_events(f.name, st))
os.unlink(f.name)
assert len(ev) == 3 and ev[2]['s'] == '-nan'
assert st['total'] == 4 and st['parsed'] == 3 and st['rejected'] == 1 and st['repaired'] == 1 and st['rejected_lines'] == [3]
print('rsxi_parse: all checks passed')
