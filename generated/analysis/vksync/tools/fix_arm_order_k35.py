"""Put run_vk.py's Kk33/Kk34/Kk35 ARMS lines in launch order (add_arm_k34/k35 inserted them after Kk32)."""
import pathlib
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
lines = p.read_bytes().decode('utf-8').split('\n')
idx = {k: [i for i, l in enumerate(lines) if l.startswith("ARMS['K']") and f'   # {k}: ' in l] for k in ('Kk32', 'Kk33', 'Kk34', 'Kk35')}
assert all(len(v) == 1 for v in idx.values()), idx
blk = sorted(v[0] for k, v in idx.items() if k != 'Kk32')
assert blk == list(range(idx['Kk32'][0] + 1, idx['Kk32'][0] + 4)), blk
new = [lines[idx[k][0]] for k in ('Kk33', 'Kk34', 'Kk35')]
lines[blk[0]:blk[-1] + 1] = new
p.write_bytes('\n'.join(lines).encode('utf-8'))
print('ok')
