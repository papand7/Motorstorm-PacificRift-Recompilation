"""Private: per-vehicle cockpit camera overrides for make_cockpit_overlay.py (tuning numbers only, no game data).

positions JSON: {"<veh>": {"x": 0, "dy": 0.35, "dz": -0.9, "pitch": -6, "yaw": 0, "focal": 8.5}, ...}
(the in-game adjuster's F2 file). x is the seat (absolute, +x left); yaw is added to the bonnet camera's yaw.
<veh> is the vehicle's list name without "_cams.txt" (e.g. "buggy01"). Each key is optional; missing keys and
missing vehicles take the --car / --bike defaults for that vehicle's kind (FIXED_* or STABLE_*), x the --x seat
and yaw 0.
"""
import json
from pathlib import Path

FIELDS = ('x', 'dy', 'dz', 'pitch', 'yaw', 'focal')


def load_positions(path):
    """Read and validate the JSON; returns {veh: {field: float}}. Unknown fields are an error, not ignored."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('positions file must be a JSON object keyed by vehicle name')
    out = {}
    for veh, vals in data.items():
        if not isinstance(vals, dict):
            raise ValueError(f'{veh}: expected an object')
        bad = set(vals) - set(FIELDS)
        if bad:
            raise ValueError(f'{veh}: unknown field(s) {sorted(bad)}')
        out[veh] = {k: float(v) for k, v in vals.items()}
    return out


def camera_values(veh, kind, defaults, positions, seat_x=0.0):
    """(x, dy, dz, pitch_delta, yaw_delta, focal) for one vehicle: the override fields on top of the defaults.

    defaults: {'FIXED': (dy, dz, dp, focal), 'STABLE': (...)}; kind: 'FIXED' or 'STABLE'; seat_x: the --x default.
    """
    dy, dz, dp, focal = defaults[kind]
    base = {'x': seat_x, 'dy': dy, 'dz': dz, 'pitch': dp, 'yaw': 0.0, 'focal': focal}
    base.update(positions.get(veh, {}))
    return tuple(base[k] for k in FIELDS)
