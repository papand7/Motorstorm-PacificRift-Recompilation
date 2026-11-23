"""The rider's eye for the cockpit camera, from the vehicle's own node table (make_cockpit_overlay.py --eye).

Code only, no game data: it reads the player's /packed_vehicles/<veh>.rpk on their PC. A vehicle package holds a node
block: N names ("|BODY_COL", "|BODY_COL|BODY", ..., the parent is the path before the last '|'), right after N 4x4
local matrices (big-endian floats, row-major, translation in the last row, last element 1.0). Among the nodes are
"left_hand" / "right_hand", where the rider's hands hold the bars or the wheel (99 of the 111 vehicles).

Frames (measured on the 8 in-game tuned vehicles): node +x is the driver's side, +z forward, and the node origin sits
BODY_COL's y below the camera lists' origin. Camera list: x = -node x, y = node y - BODY_COL y, z = -node z.
The eye is placed `up` above and `back` behind the middle of the two hands, at their x (the seat): with the camera
inside the rider's head the head's own faces point away and are culled, so the body and head stay out of view and the
arms reach forward to the hands. HYPOTHESIS: the offsets are estimates; tune with --eye-car / --eye-bike.
"""
import re
import struct

ONE = b'\x3f\x80\x00\x00'


def _mul(a, b):
    return tuple(sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4))


def node_positions(d):
    """{path: (x, y, z)} world positions of the first node block in the package bytes `d`, or {} if none."""
    for m in re.finditer(rb'\|BODY_COL\x00', d):
        i = j = m.start()
        while j < len(d) and (32 <= d[j] < 127 or d[j] == 0):
            j += 1
        names = [n.decode('latin1') for n in d[i:j].split(b'\x00') if n]
        names = names[:next((k for k, x in enumerate(names) if x.startswith('>')), len(names))]   # the table's header ends it
        if not names or names[0] != '|BODY_COL':
            continue
        # one matrix per node: the names are in order and the matrices end shortly before them (a hash table between).
        # Some packages have one stray name after the nodes; then the matrices cover the first n - 1 names.
        start = None
        for n in (len(names), len(names) - 1):
            for end in range(i, max(0, i - 0x4000), -4):
                s = end - 64 * n
                if s < 0:
                    break
                if all(d[s + 64 * k + 60:s + 64 * k + 64] == ONE for k in range(n)):
                    start = s
                    break
            if start is not None:
                names = names[:n]
                break
        if start is None:
            continue
        world = {}
        for k, nm in enumerate(names):
            mat = struct.unpack('>16f', d[start + 64 * k:start + 64 * k + 64])
            par = nm.rsplit('|', 1)[0]
            world[nm] = _mul(mat, world[par]) if par in world else mat
        return {nm: (w[12], w[13], w[14]) for nm, w in world.items()}
    return {}


def eye_camera(pos, up, back):
    """The eye in camera-list coordinates (x, y, z) from node_positions(), or None without both hands."""
    hands = [v for k, v in pos.items() if k.endswith('|left_hand') or k.endswith('|right_hand')]
    root = pos.get('|BODY_COL')
    if len(hands) != 2 or root is None:
        return None
    hx = (hands[0][0] + hands[1][0]) / 2
    hy = (hands[0][1] + hands[1][1]) / 2
    hz = (hands[0][2] + hands[1][2]) / 2
    return (-hx, hy - root[1] + up, -(hz - back))
