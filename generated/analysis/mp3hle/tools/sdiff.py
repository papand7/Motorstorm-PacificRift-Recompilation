import sys, struct
sys.path.insert(0, 'tools')
from cap import Job
for p in sys.argv[1:]:
    j = Job(p)
    puts = [e for e in j.ents if (e['cmd'] & 0xFF) == 0x20 and e['phase'] != 0xFFFFFFFF and e['phase'] >= 0x4000]
    st = b''.join(e['data'] for e in puts[1:4])
    before = j.lin[0x21C00:0x21C00 + len(st)]
    diffs = [i for i in range(0, len(st), 4) if st[i:i+4] != before[i:i+4]]
    print(p, 'pcm ea %08X' % puts[0]['ea'], 'state len %X' % len(st), 'changed words', len(diffs))
    hdr = [i for i in diffs if i < 0x200]
    for i in hdr: print('   +%03X  %08X -> %08X' % (i, struct.unpack_from('>I', before, i)[0], struct.unpack_from('>I', st, i)[0]))
    print('   later ranges:', ['%X' % i for i in diffs if i >= 0x200][:10], '...')
