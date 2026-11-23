"""Run-quality gate for A/B races: flags host contention from the wrapper's own samples (no game change).
usage: python runq.py ksr65 [ksr66 ...]   (tag as in generated/analysis/vksync/ab2/runtime-<tag>-*)
Exit 1 if any run is flagged. Thresholds from 61 Kksr runs (FINDINGS.md): CPU-starved when non-game busy cores >= 6
(5-7 fps runs measured 8.7-9.6; clean runs 1.2-3.4); GPU-contended when another bf*.exe runs and GPU util in the race
window averages >= 70 % while the game's own GPU mem would be ~2.5 GB (fast races 30-45 % util)."""
import json,sys,glob,re,statistics as st
from pathlib import Path
AB2=Path(__file__).resolve().parents[2]/'vksync/ab2'
NC=12
def check(tag):
    d=sorted(AB2.glob(f'runtime-{tag}-*'))[-1]
    L=[json.loads(l) for l in (d/'cpu.jsonl').read_text().splitlines() if l.strip()]
    oc=[];bf=set();busy=[]
    for a,b in zip(L,L[1:]):
        bi=b['sys_busy']-a['sys_busy']; ii=b['sys_idle']-a['sys_idle']
        if bi+ii<=0: continue
        u=bi/(bi+ii); oc.append(max(0,u*NC-sum(b['threads'].values())/100)); busy.append(u)
        for o in b.get('others',[]):
            if re.match(r'(bf|bfbc)\w*\.exe$',o[0]) and o[2]>3: bf.add(o[0])
    k=len(oc)//3; oc=oc[k:]
    g=[int(l.split(',')[2].split()[0]) for l in (d/'gpu.csv').read_text().splitlines() if l.count(',')>=4][len(oc)//15:] if (d/'gpu.csv').exists() else []
    flags=[]
    m=st.mean(oc) if oc else 0
    if m>=6: flags.append(f'CPU-STARVED other_busy_cores={m:.1f}')
    elif m>=4: flags.append(f'cpu-contended(weak) other_busy_cores={m:.1f}')
    if bf and g and st.mean(g)>=70: flags.append(f'GPU-CONTENDED {sorted(bf)} gpu_util={st.mean(g):.0f}%')
    elif bf: flags.append(f'other-game-present {sorted(bf)}')
    return flags
bad=0
for t in sys.argv[1:]:
    f=check(t); hard=[x for x in f if x.split()[0] in('CPU-STARVED','GPU-CONTENDED')]
    bad+=bool(hard); print(t,'REJECT' if hard else 'ok', '; '.join(f))
sys.exit(1 if bad else 0)
