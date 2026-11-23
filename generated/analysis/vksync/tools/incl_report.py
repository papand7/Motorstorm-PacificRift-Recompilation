"""Inclusive guest-function report from thread_sampler_incl.py JSON: the thread that runs the guest
main loop (func_00082358), its lifted functions by inclusive share of running samples, named from
T132b's main-loop call graph and retail_devnames.json (developer-build signature matches).

usage: py -3 incl_report.py <sample.json> [top=60] [--host]  (--host: also list host runtime functions)"""
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[4]
KNOWN = {
    0x82358: 'main loop', 0x216008: 'World::Update', 0x214250: 'World: vehicle update',
    0x8CF1C0: 'ms2Physics::Update', 0x30B710: 'Havok step', 0x4158D0: 'physics: per-subsystem updates',
    0x31BA20: 'physics: 60 Hz tick converter', 0x238570: 'GameParticleSystem update',
    0x3463F8: 'ms2Rendering::BeginFrame', 0x50D4B8: 'RenderSystemATG::Begin', 0x346A40: 'ms2Rendering::EndFrame',
    0x50B8B0: 'RenderSystemATG::End', 0x5226A8: 'DisplayATG::Present', 0x348A30: 'ms2Rendering: per-view render',
    0x331240: 'scene: visibility/cull kick', 0x7C9F70: 'Ms2Audio update', 0x810D8: 'GUI/frontend',
    0x19AC0: 'input', 0x6CC98: 'race state update', 0x2FE80: 'control input', 0x436420: 'evo::kernel::frameStart',
    0x4AACA0: 'JobBatchInternal::Wait', 0x5F74B0: 'PVSComputerImpl::WaitForCompletion',
    0x50C818: 'Wws job busy-wait (T152)', 0x12A038: 'per-competitor update A', 0x152B98: 'per-competitor update B',
    0x44DD10: 'particles/trails', 0x3309C0: 'scene pre-update', 0x435F28: 'Timer::Step',
    0x4AAF70: 'CleanupPerFrameJobMemory', 0x238998: 'particles frame begin', 0x238900: 'particles frame end',
    0x23BA38: 'particles: camera bounds', 0x1E6270: 'per-view update', 0x346228: 'finish views',
    0x359BF8: 'finish views (alt)', 0x330940: 'scene-list maintenance', 0x72E518: 'GcKernel::Present',
}
dev = {int(k, 16): v[1][0] for k, v in json.loads((R / 'generated/analysis/t132b/retail_devnames.json').read_text()).items()
       if v and v[1]}
rx = re.compile(r'func_([0-9A-F]{8})')


# --v103: the sample is from the 1.03 build; KNOWN is re-keyed by the 1.03 address (masked-word match, find_sites_masked.py,
# 26 of 38 sites map uniquely) and the main-loop thread is the one whose stacks hold the most known functions.
V103 = {'0x8cf1c0': '0x8b7e18', '0x30b710': '0x2f4478', '0x4158d0': '0x3ea5d0', '0x238570': '0x224688', '0x346a40': '0x32ddb8', '0x50b8b0': '0x4d9c48', '0x5226a8': '0x4f0110', '0x348a30': '0x32fdc0', '0x7c9f70': '0x793988', '0x810d8': '0x68780', '0x19ac0': '0x186f0', '0x6cc98': '0x67f60', '0x436420': '0x4084b8', '0x4aaca0': '0x47a328', '0x5f74b0': '0x5c2558', '0x44dd10': '0x41e828', '0x3309c0': '0x318480', '0x435f28': '0x407d18', '0x4aaf70': '0x47a5f8', '0x238998': '0x224ab0', '0x238900': '0x224a18', '0x23ba38': '0x226d10', '0x1e6270': '0x1cd1b8', '0x359bf8': '0x340f80', '0x330940': '0x318398', '0x72e518': '0x6f79d0'}
if '--v103' in sys.argv:
    KNOWN = {int(V103[hex(k)], 16): v for k, v in KNOWN.items() if hex(k) in V103}
    dev = {}

def label(name):
    m = rx.search(name)
    if not m:
        return None, name
    a = int(m.group(1), 16)
    return a, KNOWN.get(a) or dev.get(a, '')


d = json.loads(Path(sys.argv[1]).read_text())
top = int(next((x for x in sys.argv[2:] if x.isdigit()), 60))
def _is_main(t):
    names = ' '.join(n for n, _, _ in t['incl'])
    if '--v103' in sys.argv:
        return sum(1 for a in KNOWN if f'func_{a:08X}' in names) >= 3
    return 'func_00082358' in names


for t in d['threads']:
    if not _is_main(t):
        continue
    print(f"thread {t['tid']}: {t['cpu_fraction']:.0%} CPU, {t['samples']} samples, {t['running']} running "
          f"({t['running'] / max(1, t['samples']):.0%}), {t['mean_frames']} frames a sample, "
          f"{t.get('broken_walks', '?')} broken walks")
    k = 0
    for n, c, f in t['incl']:
        a, lab = label(n)
        if a is None and '--host' not in sys.argv:
            continue
        print(f'  {f:6.1%}  {n[:60]:60s} {lab[:70]}')
        k += 1
        if k >= top:
            break
    print('  self (leaf) top:')
    for n, c, f in t['self'][:25]:
        a, lab = label(n)
        print(f'  {f:6.1%}  {n[:60]:60s} {lab[:60] if a is not None else ""}')
    if t.get('waiting'):
        print(f"  waiting samples {t['waiting']} ({t['waiting'] / max(1, t['samples']):.0%}); where (inclusive, guest):")
        k = 0
        for n, c, f in t['incl_wait']:
            a, lab = label(n)
            if a is None and '--host' not in sys.argv:
                continue
            print(f'  {f:6.1%}  {n[:60]:60s} {lab[:70]}')
            k += 1
            if k >= top // 2:
                break
        print('  wait leaf:')
        for n, c, f in t['self_wait'][:8]:
            print(f'  {f:6.1%}  {n[:90]}')
