"""Add launch Zz4 after Kk3: arm Z on exe 1e610e77 (kick off), under sample_chain.py for the main thread's waits."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk3', 'Yy1']", "'Kk3', 'Zz4', 'Yy1']")
sub("MAX_LAUNCHES = 49", "MAX_LAUNCHES = 50")
p.write_bytes(s.encode('utf-8'))
print('ok')
