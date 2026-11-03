"""T69: race-window evidence from an existing run directory (read-only).

usage: py -3 -I race_evidence.py <run dir> [race_start_s]

Prints frame rate, per-thread CPU labelled with the PPU host TIDs the runtime
logs ("[THREAD n] host thread started ... hosttid="), Havok step counts per
frame, SPU dispatch mix, policy-module run rate and log volume."""
import bisect, collections, json, re, sys

run = sys.argv[1]
t_race = float(sys.argv[2]) if len(sys.argv) > 2 else None
perf = json.load(open(run + "/performance.json"))
err = open(run + "/stderr.log", encoding="utf-8", errors="replace").read().splitlines()

names = {}
for l in err:
    m = re.search(r"sys_ppu_thread_create tid=(\d+) name=\"([^\"]*)\"", l)
    if m: names.setdefault("g" + m.group(1), m.group(2))
ppu = {}
for l in err:
    m = re.match(r"\[THREAD (\d+)\] host thread started.*hosttid=(\d+)", l)
    if m: ppu[int(m.group(2))] = "PPU %s %s" % (m.group(1), names.get("g" + m.group(1), ""))
first = perf["samples"][1]["top_thread_cpu_s"] if len(perf["samples"]) > 1 else []

hb = []
for i, l in enumerate(err):
    m = re.match(r"\[rsx-hb\] ms=(\d+) frames=(\d+) draw_frames=\d+ last_draws=(\d+)", l)
    if m: hb.append((i, int(m.group(1)) / 1000, int(m.group(2)), int(m.group(3))))
if t_race is None:
    t_race = next(t for i, t, f, d in hb if d > 200)
race_hb = [h for h in hb if h[1] >= t_race]
i0, i1 = race_hb[0][0], race_hb[-1][0]
fps = (race_hb[-1][2] - race_hb[0][2]) / (race_hb[-1][1] - race_hb[0][1])
print(f"race window {race_hb[0][1]:.1f}-{race_hb[-1][1]:.1f} s, frames {race_hb[0][2]}->{race_hb[-1][2]}, "
      f"{fps:.2f} fps, draws/frame {race_hb[-1][3]}")

S = perf["samples"]
rows = []
for a, b in zip(S, S[1:]):
    if b["t"] < t_race + 4: continue
    dt = b["t"] - a["t"]
    rows.append(((b["cpu_user_s"] + b["cpu_kernel_s"] - a["cpu_user_s"] - a["cpu_kernel_s"]) / dt,
                 (b["cpu_kernel_s"] - a["cpu_kernel_s"]) / dt, b["top_thread_cpu_s"], dt))
print(f"process: {sum(r[0] for r in rows)/len(rows):.2f} cores busy, {sum(r[1] for r in rows)/len(rows):.2f} kernel")
acc = collections.defaultdict(list)
for _, _, top, dt in rows:
    for tid, c in top: acc[tid].append(c / dt)
print("top threads in race (mean cores over the samples where listed):")
for tid, v in sorted(acc.items(), key=lambda kv: -sum(kv[1]))[:8]:
    lab = ppu.get(tid, "non-PPU host thread")
    if tid == perf["samples"][0]["top_thread_cpu_s"][0][0]: lab = "process main thread = PPU main (ppu_run)"
    print(f"  tid {tid:>6}: {sum(v)/len(v):.2f} cores (listed {len(v)}/{len(rows)})  {lab}")

race = err[i0:i1]
disp = collections.Counter(re.search(r"image=(\d+)", l).group(1) for l in race if "dispatch HIT (async)" in l)
print("SPU async dispatches in race by image:", dict(disp), "total", sum(disp.values()),
      f"= {sum(disp.values())/(race_hb[-1][1]-race_hb[0][1]):.1f}/s")
idx = [h[0] for h in race_hb]
steps = collections.Counter()
for k, l in enumerate(race):
    if "dispatch HIT" in l and "image=341580667" in l:
        steps[bisect.bisect(idx, i0 + k)] += 1
per = [(steps[k], race_hb[k][2] - race_hb[k - 1][2]) for k in range(1, len(race_hb)) if race_hb[k][2] > race_hb[k-1][2]]
tot_s, tot_f = sum(s for s, f in per), sum(f for s, f in per)
print(f"Havok simulate (341580667) steps per frame: {tot_s}/{tot_f} = {tot_s/max(tot_f,1):.2f}")
pm = sum(1 for l in race if l.startswith("[spurs-pm] poll #1 "))
print(f"policy-module runs with >=1 poll: {pm} = {pm/(race_hb[-1][1]-race_hb[0][1]):.0f}/s")
hle = [int(m.group(1)) for l in race for m in [re.search(r"nid=8A85674D .*dur_us=(\d+)", l)] if m]
if hle: print(f"LFQueue PushBody HLE: {len(hle)} calls, mean {sum(hle)/len(hle):.1f} us")
print(f"stderr lines in race: {len(race)} = {len(race)/(race_hb[-1][1]-race_hb[0][1]):.0f}/s")
