import json, re
p = r'<repo>\generated\analysis\vksync\ab2\run_vk.py'
lock = r'<repo>\generated\analysis\vksync\ab2\launches_used.jsonl'
s = open(p, encoding='utf-8').read()
assert "K_BY_TAG['pr2']" not in s
line = re.search(r"^K_BY_TAG\['pr1'\] = .*$", s, re.M).group(0)
new = line.replace("K_BY_TAG['pr1'] = ('pr1',", "K_BY_TAG['pr2'] = ('pr2',", 1)
new = new.replace("shots\\\\pr1'", "shots\\\\pr2'", 1)
new = new.split('   # ')[0] + "   # Kpr2: Kpr1 with the key cap kept inside the original icon's rect (symbols for Enter/Space/Shift; prompts/RESULTS.md)"
assert "pr1" not in new.split("   # ")[0], new
s = s.rstrip('\n') + '\n' + new + '\n'
order = eval(re.search(r'^ORDER = (\[.*?\])', s, re.M).group(1))
used = [json.loads(l)['tag'] for l in open(lock)]
last = order[-1]
print('last in ORDER:', last, '; next to launch:', order[len(used)] if len(used) < len(order) else None)
pass
a = "'Kst9o', "
assert s.count(a) == 1
s = s.replace(a, "'Kst9o', 'Kpr2', ")
open(p, 'w', encoding='utf-8').write(s)
order = eval(re.search(r'^ORDER = (\[.*?\])', s, re.M).group(1))
print(all(order[i] == used[i] for i in range(len(used))), order[len(used):])
print(new)
