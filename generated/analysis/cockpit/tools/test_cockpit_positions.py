"""py -3 -I test_cockpit_positions.py: positions merge (defaults unchanged without overrides)."""
import json, os, tempfile, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cockpit_positions import camera_values, load_positions

DEF = {'FIXED': (0.35, -0.9, -6.0, 8.5), 'STABLE': (0.1, -1.8, 4.0, 7.0)}
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, 'pos.json')
    Path(p).write_text(json.dumps({'buggy01': {'dy': 0.5, 'focal': 9}, 'bike03': {'dz': -2.0, 'pitch': 1.5}}), encoding='utf-8')
    pos = load_positions(p)
    assert pos == {'buggy01': {'dy': 0.5, 'focal': 9.0}, 'bike03': {'dz': -2.0, 'pitch': 1.5}}

    # overridden fields win, the rest keep the kind's default
    # (x, dy, dz, pitch delta, yaw delta, focal): overridden fields win, the rest keep the kind's default
    assert camera_values('buggy01', 'FIXED', DEF, pos) == (0.0, 0.5, -0.9, -6.0, 0.0, 9.0)
    assert camera_values('bike03', 'STABLE', DEF, pos) == (0.0, 0.1, -2.0, 1.5, 0.0, 7.0)
    # vehicles without an entry are exactly the defaults (no change for the rest of the fleet); x is the --x seat
    assert camera_values('truck07', 'FIXED', DEF, pos) == (0.0, 0.35, -0.9, -6.0, 0.0, 8.5)
    assert camera_values('truck07', 'STABLE', DEF, {}, 0.2) == (0.2, 0.1, -1.8, 4.0, 0.0, 7.0)
    # no positions file: defaults unchanged
    assert camera_values('buggy01', 'FIXED', DEF, {}) == (0.0, 0.35, -0.9, -6.0, 0.0, 8.5)
    # the in-game F2 file (all six fields)
    Path(p).write_text(json.dumps({'atv22': {'x': 0.25, 'dy': 0.14, 'dz': -1.82, 'pitch': 3.5, 'yaw': -2.0, 'focal': 8.5}}),
                       encoding='utf-8')
    assert camera_values('atv22', 'STABLE', DEF, load_positions(p)) == (0.25, 0.14, -1.82, 3.5, -2.0, 8.5)

    # unknown field and non-object files are refused, not silently ignored
    Path(p).write_text(json.dumps({'buggy01': {'roll': 1}}), encoding='utf-8')
    try:
        load_positions(p); raise SystemExit('unknown field accepted')
    except ValueError:
        pass
    Path(p).write_text(json.dumps([1, 2]), encoding='utf-8')
    try:
        load_positions(p); raise SystemExit('list accepted')
    except ValueError:
        pass
print('test_cockpit_positions: OK')
