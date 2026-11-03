"""T161: startup / race-entry timeline of one MotorStorm run from existing logs (no new instrumentation).
  py -3 startup_timeline_t161.py <run_dir> <runtime_dir>      prints JSON
Phases come from the controller's page_load / press / marker events (runtime_dir/controller.log, host s from
wrapper start). Per phase, from stderr.log with the 1 s [rsx-hb] ms= heartbeat as clock (host ms since process
start, about 1 s behind the controller clock): wall s, RSX passes rendered, [sc-wait] per guest thread
(ms blocked per s and the dominant syscall), [spurs-busy] busy workers, and process CPU cores from
performance.json (5 s samples, cumulative user+kernel)."""
import json, re, sys
from collections import defaultdict, Counter
from pathlib import Path

rd, rt = Path(sys.argv[1]), Path(sys.argv[2])
ev = []
for l in open(rt / 'controller.log', encoding='utf-8', errors='replace'):
    m = re.match(r'^\[\s*([0-9.]+)\] (\S+) (.*)$', l)
    if not m: continue
    t, k, rest = float(m[1]), m[2], m[3]
    if k == 'page_load':
        ev.append((t, 'page ' + json.loads(rest)['page']))
    elif k in ('press', 'intro_skip', 'marker', 'race_loaded_corroborated', 'race_entry'):
        ev.append((t, k + (' ' + json.loads(rest).get('name', json.loads(rest).get('step', '')) if k in ('marker', 'press') else '')))
# phase boundaries: first occurrence of a few anchors
def first(pred, after=0.0):
    return next((t for t, n in ev if t >= after and pred(n)), None)
A = {}
A['first_gui'] = first(lambda n: n.startswith('page gui/'))
A['logos_start'] = first(lambda n: n == 'page gui/sonylogo')
A['mainmenu'] = first(lambda n: n == 'page gui/mainmenu')
A['press1'] = first(lambda n: n.startswith('press cross 1'))
A['loadscreen'] = first(lambda n: n == 'page gui/loadscre')
A['track'] = first(lambda n: n == 'page worlds/track')
A['env'] = first(lambda n: n.startswith('page env/'))
A['vehicles'] = first(lambda n: n.startswith('page split_vehicl'))
A['characters'] = first(lambda n: n.startswith('page characters/'))
A['postlevelload'] = first(lambda n: n.startswith('marker LOAD RACE'))
A['race_loaded'] = first(lambda n: n.startswith('race_loaded'))
A['race_entry'] = first(lambda n: n == 'race_entry')
last_vehicle_before_chars = max((t for t, n in ev if n.startswith('page split_vehicl') and t < (A['characters'] or 1e9)), default=None)
A['vehicles_last_before_chars'] = last_vehicle_before_chars
order = [('exe init -> first GUI page', 0.0, A['first_gui']),
         ('boot GUI (festival/texturer/gamesave) -> logos', A['first_gui'], A['logos_start']),
         ('logos + intro video -> main menu', A['logos_start'], A['mainmenu']),
         ('main menu -> first Cross (intro skip, controller settle)', A['mainmenu'], A['press1']),
         ('menu navigation (4 Cross presses, controller pacing)', A['press1'], A['loadscreen']),
         ('load screen -> world/track', A['loadscreen'], A['track']),
         ('track world load', A['track'], A['env']),
         ('environment load', A['env'], A['vehicles']),
         ('vehicle loads (first batch)', A['vehicles'], A['vehicles_last_before_chars']),
         ('gap after vehicles -> characters', A['vehicles_last_before_chars'], A['characters']),
         ('characters + remaining vehicles -> PostLevelLoad', A['characters'], A['postlevelload']),
         ('PostLevelLoad -> loader return', A['postlevelload'], A['race_loaded']),
         ('loader return -> race entry (first race frame)', A['race_loaded'], A['race_entry'])]
# stderr accounting per second
hb = 0
sc = defaultdict(lambda: defaultdict(float)); scn = defaultdict(lambda: defaultdict(Counter))
busy = defaultdict(float); passes = defaultdict(int)
BUSY = re.compile(r'busy_ms=([0-9.]+)')
for l in open(rd / 'stderr.log', encoding='utf-8', errors='replace'):
    if l.startswith('[rsx-hb] ms='):
        hb = int(l.split('ms=')[1].split()[0]); continue
    s = hb // 1000
    if l.startswith('[sc-wait]'):
        m = re.search(r'tid=(\d+) total_ms=([0-9.]+)', l)
        if m:
            sc[s][m[1]] += float(m[2])
            for name, ms in re.findall(r'(sc\d+)=([0-9.]+)ms', l):
                scn[s][m[1]][name] += float(ms)
    elif l.startswith('[spurs-busy]'):
        m = BUSY.search(l)
        if m: busy[s] += float(m[1])
    elif l.startswith('[rsx-frame-perf] gframe='):
        passes[s] += 1
perf = json.loads((rd / 'performance.json').read_text())['samples']
def cpu(a, b):
    ss = [x for x in perf if a <= x['t'] <= b]
    if len(ss) < 2: return None
    return round((ss[-1]['cpu_user_s'] + ss[-1]['cpu_kernel_s'] - ss[0]['cpu_user_s'] - ss[0]['cpu_kernel_s']) / (ss[-1]['t'] - ss[0]['t']), 2)
out = {'anchors_host_s': A, 'phases': []}
for name, a, b in order:
    if a is None or b is None: continue
    secs = range(int(a), int(b))
    n = max(1, len(secs))
    th = defaultdict(float); names = defaultdict(Counter)
    for s in secs:
        for t, v in sc[s].items(): th[t] += v
        for t, cn in scn[s].items(): names[t].update(cn)
    top = sorted(th.items(), key=lambda x: -x[1])[:3]
    out['phases'].append({'phase': name, 'start_s': round(a, 1), 'dur_s': round(b - a, 1),
                          'rsx_passes_per_s': round(sum(passes[s] for s in secs) / n, 1),
                          'spurs_busy_workers': round(sum(busy[s] for s in secs) / 1000 / n, 2),
                          'cpu_cores': cpu(a, b),
                          'guest_thread_wait_ms_per_s': {t: {'ms': round(v / n), 'top': names[t].most_common(1)[0][0] if names[t] else None} for t, v in top}})
print(json.dumps(out, indent=1))
