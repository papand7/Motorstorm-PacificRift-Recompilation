r"""run_vk.py: Kkveh60/Kkveh30 (2026-11-22, generated/analysis/vehfps). Vehicle-vs-camera frame measurement:
exe slot h (build/vehfps-link/diag, the ppucc2 objects + env-gated RSX_VEHLOG / MSPR_DT_LOG). Same env as Kksr117
(1.00 ppucc2, vfps, FSR 3.1, MSPR_CAM_MODE=1) with the user's patch list (drs,vfps,mblur,audiothread); only
PS3_SIM_PACE_HZ differs (60 / 30). Driven by tools/drive_veh.py <tag> (throttle from race entry + 6 s).
Further arms (Kkveh60b, Kkveh60f ...) are added with: py -3 add_arms_veh.py <tag> <slot> <hz> [KEY=VALUE ...]
usage: py -3 add_arms_veh.py   (adds veh60, veh30)"""
import pathlib
import sys

ab2 = pathlib.Path(__file__).resolve().parents[2] / 'vksync' / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
arms = [('veh60', 'h', '60', {}), ('veh30', 'h', '30', {})] if len(sys.argv) < 2 else \
    [(sys.argv[1], sys.argv[2], sys.argv[3], dict(a.split('=', 1) for a in sys.argv[4:]))]
add = ''
order = ''
for tag, slot, hz, extra in arms:
    if f"K_BY_TAG['{tag}']" in s:
        print('already there:', tag)
        continue
    ex = ''.join(f", {k!r}: {v!r}" for k, v in extra.items())
    add += (f"K_BY_TAG['{tag}'] = ('{slot}', {{**_TX, 'MSPR_PATCH': 'drs,vfps,mblur,audiothread', 'PS3_SIM_PACE_HZ': '{hz}', "
            f"'RSX_VEHLOG': '0:15000', 'MSPR_DT_LOG': '30000'{ex}}})   # K{tag}: vehicle vs camera per frame (vehfps)\n")
    order += f", 'K{tag}'"
if add:
    a = "\nif __name__ == '__main__':"
    assert s.count(a) == 1
    s = s.replace(a, '\n' + add + a)
    a = "'Yy1']"
    assert s.count(a) == 1
    s = s.replace(a, order[2:] + ", 'Yy1']")
    p.write_text(s, encoding='utf-8', newline='\n')
    print('edited', p.name, order)
