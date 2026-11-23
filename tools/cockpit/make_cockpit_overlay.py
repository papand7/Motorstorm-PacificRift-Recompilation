"""Write the MSPR_CAM_COCKPIT overlay from the user's own MS2.PSARC (nothing of the game is stored here).

Code only: the launcher's source snapshot carries it as cockpit-tool/ (launcher/electron/source_bundles.js) with
cockpit_positions.default.json (camera offsets only); the install's cockpit step runs it on the player's PC. Its
output derives from the game's data and is never shipped.

For every /data/camera_config_files/<veh>_cams.txt it writes <out>/data/camera_config_files/<veh>_camz.txt:
the original text unchanged plus CAMERA 3 lines, an in-cockpit (driver's-eye) view placed relative to the
vehicle's own CAMERA 2 (bonnet) entry. The game keeps as many cameras as the highest CAMERA number and SELECT
cycles through them (port-vkgame/main.cpp mspr_cam_cockpit_init). Line format (1.00 parser 0x0037D640,
"%s%d%s%f%f%f%f%f%f%f"): CAMERA n TYPE focal x y z yaw pitch roll; +x left, +y up, +z forward (from the
LEFT/RIGHT/REAR entries). The eye offsets below are estimates (HYPOTHESIS), tune them and re-run, no rebuild.

usage: py -3 -I make_cockpit_overlay.py --out <overlay dir> [--psarc MS2.PSARC]
       [--car dy,dz,dpitch,focal] [--bike dy,dz,dpitch,focal] [--x <seat x>] [--positions cockpit_positions.json]
"""
import argparse, re, struct, sys, zlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cockpit_positions import camera_values, load_positions
from rider_eye import eye_camera, node_positions

_here = Path(__file__).resolve()
ROOT = _here.parents[2] if len(_here.parents) > 2 else _here.parent   # tools/cockpit -> the checkout (developers)
ap = argparse.ArgumentParser()
ap.add_argument('--psarc', default=str(ROOT / 'original/game/PS3_GAME/USRDIR/MS2.PSARC'))
ap.add_argument('--out', required=True)
# The vehicle frame faces -z (measured in game: the stored z grows backwards), so "behind the bonnet camera" is +dz.
# CAMERA 2 FORWARD per class (MS2.PSARC, y / z median): buggy 0.93/-0.40, rallycar 1.00/-0.50, racetruck 1.15/-0.90,
# mudplugger 1.25/-0.89, monster 1.70/-1.60, bigrig 2.00/-3.05 (a hood camera: forward of the origin, which is about
# the centre, and the driver sits 0.6-0.9 behind it), bike 1.60/+1.50 and atv 1.60/+1.40 (already at the rider).
# Cars/trucks: the old -0.9 put the eye a metre forward of the hood camera ("far ahead of the vehicle"); +0.6 puts it at
# the seat for every class (eye z: buggy 0.2, rallycar 0.1, racetruck/mudplugger -0.3, monster -1.0, bigrig -2.45).
# Bikes/ATV: the in-game tuned ATV view (dy 0.10, dz -1.04, pitch +4, focal 6.4 from the bonnet camera) rounded.
ap.add_argument('--car', default='0.15,0.6,0,8.5', help='FIXED_* vehicles: dy,dz from CAMERA 2 (+dz = back), pitch delta, focal')
ap.add_argument('--bike', default='0.1,-1.0,4,6.5', help='STABLE_* (bike/ATV): dy,dz from CAMERA 2 (+dz = back), pitch delta, focal')
ap.add_argument('--x', type=float, default=0.0, help='seat x (+left)')
ap.add_argument('--positions', help='JSON of per-vehicle overrides {"<veh>": {"x","dy","dz","pitch","yaw","focal"}} '
                '(the in-game F2 file cockpit_positions.json); defaults unchanged')
# The rider's eye (rider_eye.py): x, dy and dz from the vehicle's hand nodes, for every vehicle the positions file does
# not place (its x/dy/dz win); vehicles without hand nodes keep --car / --bike.
ap.add_argument('--eye', type=int, default=1, help='1: place the eye from the rider\'s hands (default), 0: --car/--bike only')
ap.add_argument('--eye-car', default='0.45,0.45', help='FIXED_* eye: up, back from the middle of the hands')
ap.add_argument('--eye-bike', default='0.5,0.4', help='STABLE_* eye: up, back from the middle of the hands')
a = ap.parse_args()
eye_off = {'FIXED': [float(v) for v in a.eye_car.split(',')], 'STABLE': [float(v) for v in a.eye_bike.split(',')]}
car = [float(v) for v in a.car.split(',')]
bike = [float(v) for v in a.bike.split(',')]
defaults = {'FIXED': car, 'STABLE': bike}
positions = load_positions(a.positions) if a.positions else {}

src = Path(a.psarc)
with src.open('rb') as f:
    h = f.read(32)
    assert h[:4] == b'PSAR'
    _, el, count, bs, _ = struct.unpack('>5I', h[12:32])
    toc = f.read(count * el)

    def entry(i, limit=None):
        e = toc[i * el:(i + 1) * el]
        z, size, off = int.from_bytes(e[16:20], 'big'), int.from_bytes(e[20:25], 'big'), int.from_bytes(e[25:30], 'big')
        f.seek(32 + el * count + 2 * z)
        lens = [int.from_bytes(f.read(2), 'big') for _ in range((size + bs - 1) // bs)]
        if limit is not None:   # only the first blocks (a vehicle package's node table is near its start)
            lens = lens[:(limit + bs - 1) // bs]
        f.seek(off)
        d = bytearray()
        for ln in lens:
            c = f.read(ln or bs)
            try:
                c = zlib.decompress(c)
            except zlib.error:
                pass
            d.extend(c)
        return bytes(d[:size])

    names = entry(0).decode('latin1').split('\n')
    packed = {n.strip().lower(): k + 1 for k, n in enumerate(names)}

    def eye_of(veh, kind):
        """the rider's eye (camera list x, y, z) of a vehicle, or None"""
        k = packed.get(f'/packed_vehicles/{veh}.rpk')
        if k is None:
            return None
        pos = node_positions(entry(k, 1 << 20)) or node_positions(entry(k))
        return eye_camera(pos, *eye_off[kind])
    n_eye = 0
    out = Path(a.out) / 'data' / 'camera_config_files'
    out.mkdir(parents=True, exist_ok=True)
    pat = re.compile(r'^/data/camera_config_files/([^/]+)_cams\.txt$', re.I)
    line = re.compile(r'^CAMERA\s+2\s+(FIXED|STABLE)_(FORWARD|LEFT|RIGHT|REAR)\s+(.*)$')
    n_ok = n_skip = 0
    seen = {}
    for k, n in enumerate(names):
        m = pat.match(n.strip())
        if not m:
            continue
        text = entry(k + 1).decode('latin1')
        cam2 = {}
        for ln in text.splitlines():
            mm = line.match(ln.strip())
            if mm:
                cam2[mm.group(2)] = (mm.group(1), [float(v) for v in mm.group(3).split()[:7]])
        if 'FORWARD' not in cam2 or re.search(r'^CAMERA\s+3\s', text, re.M):
            n_skip += 1
            continue
        kind, (fl, x, y, z, yaw, pitch, roll) = cam2['FORWARD']
        veh = m.group(1).lower()
        pv = positions
        if a.eye and not {'x', 'dy', 'dz'} <= set(positions.get(veh, {})):
            e = eye_of(veh, kind)
            if e is not None:   # the tuned fields (the F2 file) still win over the eye
                pv = {**positions, veh: {'x': e[0], 'dy': e[1] - y, 'dz': e[2] - z, **positions.get(veh, {})}}
                n_eye += 1
        sx, dy, dz, dp, dyaw, focal = camera_values(veh, kind, defaults, pv, a.x)
        add = ['', '#### MSPR_CAM_COCKPIT: in-cockpit (driver\'s-eye) view, generated',
               f'CAMERA 3 {kind}_FORWARD {focal:g}\t\t{sx:g} {y + dy:.3f} {z + dz:.3f} {yaw + dyaw:g} {pitch + dp:g} {roll:g}']
        for side in ('LEFT', 'RIGHT', 'REAR'):   # look-around: the vehicle's own bonnet look-around views
            if side in cam2:
                k2, v = cam2[side]
                add.append(f'CAMERA 3 {k2}_{side} ' + ' '.join(f'{t:g}' for t in v))
        body = text if text.endswith('\n') else text + '\n'
        (out / f'{m.group(1)}_camz.txt').write_bytes((body + '\n'.join(add) + '\n').encode('latin1'))
        n_ok += 1
        cls = re.sub(r'\d+$', '', m.group(1).lower())
        seen.setdefault(cls, []).append((kind, y, z, y + dy, z + dz, sx, dp, focal))
print(f'wrote {n_ok} camera lists to {out} ({n_skip} skipped: no CAMERA 2 FORWARD or already a CAMERA 3; '
      f'{n_eye} at the rider\'s eye)')
for cls, v in sorted(seen.items()):   # the resulting eye per class (vehicle frame, -z forward): median bonnet and eye
    med = lambda i: sorted(r[i] for r in v)[len(v) // 2]
    print(f'  {cls:11s} n={len(v):2d} {v[0][0]:6s} bonnet y {med(1):5.2f} z {med(2):5.2f} -> eye y {med(3):5.2f} z {med(4):5.2f} '
          f'x {med(5):4.2f} pitch +{med(6):g} focal {med(7):g}')
