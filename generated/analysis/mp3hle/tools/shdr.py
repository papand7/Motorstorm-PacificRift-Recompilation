import sys, struct
sys.path.insert(0, 'tools')
from cap import Job
for p in sys.argv[1:]:
    j = Job(p)
    puts = [e for e in j.ents if (e['cmd'] & 0xFF) == 0x20 and e['phase'] != 0xFFFFFFFF and e['phase'] >= 0x4000]
    st = puts[1]['data']
    b = j.lin[0x21C00:0x21C00+0x80]
    print(p, 'pcm->%08X' % puts[0]['ea'])
    print('  in :', ' '.join('%08X' % struct.unpack_from('>I', b, i)[0] for i in range(0, 0x60, 4)))
    print('  out:', ' '.join('%08X' % struct.unpack_from('>I', st, i)[0] for i in range(0, 0x60, 4)))
