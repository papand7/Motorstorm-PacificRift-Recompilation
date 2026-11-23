"""Queue the otherport arms in generated/analysis/vksync/ab2/run_vk.py (no launch). Inserts the tags before
'Klt5t' in ORDER and their K_BY_TAG entries before the __main__ guard; refuses if ORDER[:len(launches_used)]
would stop matching the launched list. Idempotent (does nothing if the tags are already there)."""
import json, pathlib, re, sys

AB2 = pathlib.Path(__file__).resolve().parents[2] / 'vksync' / 'ab2'
RV = AB2 / 'run_vk.py'


def abba(p, n=6):   # a1 b1 b2 a2 a3 b3 b4 a4 ...
    out = []
    for i in range(1, n + 1):
        out += [f'{p}a{i}', f'{p}b{i}'] if i % 2 else [f'{p}b{i}', f'{p}a{i}']
    return out


TAGS = abba('hf') + abba('jp') + abba('hl') + ['fxs0', 'fxs1']
SLOT = 'ot'   # exe_ot/ = build/otherport-link (sha in exe_ot.sha256)
DEFS = r'''
# otherport (generated/analysis/otherport/IMPLEMENT.md): exe_ot = build/otherport-link, sha256 d3360b8c (the
# ppucc2 objects + PS3_SPU_HWFLOAT, PS3_JOBPOLL_US/PS3_USLEEP_CAP, PS3_SPU_HOST_LANES, MSPR_CAM_SPRING; all off
# by default). Timing pairs on _TX (the Kksr timing configuration, vfps + pace 60), same exe both arms, ABBA order;
# decide with roadto60_next/tools/ab_compare.py --a <a tags> --b <b tags> --a-sha d3360b8c --b-sha d3360b8c.
_OT_HF = {**_TX, 'PS3_SPU_TASK_STATS': '1000'}
for _i in range(1, 7):
    K_BY_TAG[f'hfa{_i}'] = ('ot', {**_OT_HF, 'PS3_SPU_HWFLOAT': '0'})   # Khfa: item 1 off (exact SPU float helpers)
    K_BY_TAG[f'hfb{_i}'] = ('ot', {**_OT_HF, 'PS3_SPU_HWFLOAT': '1'})   # Khfb: item 1 on (MXCSR toward-zero/FTZ/DAZ)
    K_BY_TAG[f'jpa{_i}'] = ('ot', dict(_TX))                             # Kjpa: item 2 off (JobBatchHandler usleep(200) on the timer)
    K_BY_TAG[f'jpb{_i}'] = ('ot', {**_TX, 'PS3_JOBPOLL_US': '50'})       # Kjpb: item 2 on (lr 0x004AF6D0 capped to 50 us, spun)
    K_BY_TAG[f'hla{_i}'] = ('ot', dict(_TX))                             # Khla: item 3 off (5 host lanes)
    K_BY_TAG[f'hlb{_i}'] = ('ot', {**_TX, 'PS3_SPU_HOST_LANES': '6', 'PS3_SPU_HOST_LANES_WIDE': '1'})   # Khlb: item 3 on (6 lanes, guest sees 5)
_OT_FX = {**_TX, 'MSPR_PATCH': 'drs,60fps,audiothread', 'PS3_SIM_PACE_HZ': '60', 'MSPR_CAM_MODE': '1',
          'RSX_VEHLOG': '0:15000', 'MSPR_DT_LOG': '30000', 'MSPR_CAM_SPRING_LOG': '600'}
K_BY_TAG['fxs0'] = ('ot', {**_OT_FX, 'MSPR_CAM_SPRING': '0'})   # Kfxs0: item 4a Fixed 60 (game's 1/60 step, no vfps), springs every update
K_BY_TAG['fxs1'] = ('ot', {**_OT_FX, 'MSPR_CAM_SPRING': '1'})   # Kfxs1: item 4b Fixed 60 + chase springs at 30 Hz of the frame clock
'''


def main():
    s = RV.read_bytes().decode('utf-8')   # line endings kept as they are
    used = [json.loads(l)['tag'] for l in (AB2 / 'launches_used.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    m = re.search(r"^ORDER = (\[.*?\])", s, re.M)
    order = eval(m.group(1))
    assert order[:len(used)] == used, 'ORDER and launches_used.jsonl already disagree; not touching it'
    if 'K' + TAGS[0] in order:
        print('already queued'); return
    i = order.index('Klt5t')
    assert i >= len(used), 'Klt5t already launched'
    new = order[:i] + ['K' + t for t in TAGS] + order[i:]
    assert new[:len(used)] == used
    s = s[:m.start(1)] + repr(new) + s[m.end(1):]
    eol = '\r\n' if '\r\n' in s else '\n'
    j = s.index(eol + "if __name__ == '__main__':")
    s = s[:j] + eol + DEFS.strip('\n').replace('\n', eol) + eol + s[j:]
    RV.write_bytes(s.encode('utf-8'))
    print(f'queued {len(TAGS)} arms before Klt5t (position {i}); launched so far {len(used)}; next authorized {new[len(used)]}')


if __name__ == '__main__':
    main()
