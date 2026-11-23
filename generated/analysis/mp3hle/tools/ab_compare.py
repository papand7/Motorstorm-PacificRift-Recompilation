"""Compare original-job captures (A) with in-game HLE captures (B), job by job (v2 capture files).
Reports PCM SNR / max abs diff per alignment, header word agreement, and the input byte stream."""
import glob, struct, sys
import numpy as np

def load(p):
    b = open(p, 'rb').read()
    h = struct.unpack_from('<8I', b, 0); o = 32 + 2048
    lo = h[7]; win = b[o:o + 0x11000]; o += 0x11000
    n, dl = struct.unpack_from('<II', b, o); o += 8
    ents = [struct.unpack_from('<4IQII', b, o + 32 * i) for i in range(n)]; o += 32 * n
    data = b[o:o + dl]
    puts = [(e, data[e[5]:e[5] + e[2]]) for e in ents if (e[0] & 0xFF) == 0x20 and e[6] != 0xFFFFFFFF and e[6] >= 0x4000]
    S = win[0x1FC00 + 0x2000 - lo:][:0x60]
    w = struct.unpack('>24I', S)
    pcm = np.frombuffer(puts[0][1], '>f4').astype(np.float64)
    sout = b''.join(d for _, d in puts[1:])
    inp = win[0x1FC00 - lo:0x1FC00 - lo + 0x2000]
    return dict(w=w, pcm=pcm, sout=sout, inp=inp, puts=[(e[1], e[4], e[2], e[3]) for e, _ in puts])

A = [load(p) for p in sorted(glob.glob(sys.argv[1] + '/job_*.bin'))]
B = [load(p) for p in sorted(glob.glob(sys.argv[2] + '/job_*.bin'))]
n = min(len(A), len(B))
def stream(J):
    s = bytearray()
    for j in J:
        rd, av, hd = j['w'][10], j['w'][11], j['w'][13]
        c = av if hd == 0 else int(struct.unpack('>f', j['sout'][4:8])[0])
        s += j['inp'][rd:rd + c]
    return bytes(s)
sa, sb = stream(A[:n]), stream(B[:n])
m = min(len(sa), len(sb))
print('jobs', n, 'stream bytes A', len(sa), 'B', len(sb), 'common prefix identical:', sa[:m] == sb[:m])
inits = [i for i, j in enumerate(A[:n]) if j['w'][13] == 0], [i for i, j in enumerate(B[:n]) if j['w'][13] == 0]
print('stream starts (S+0x34 == 0) A', inits[0], 'B', inits[1])
pa = np.array([j['pcm'] for j in A[:n]]); pb = np.array([j['pcm'] for j in B[:n]])
e = pa - pb
print('PCM same job index: SNR %.1f dB, max abs diff %.3g, frames > 1e-4: %d' % (
    10 * np.log10((pa ** 2).sum() / max((e ** 2).sum(), 1e-300)), np.abs(e).max(), int((np.abs(e).max(1) > 1e-4).sum())))
# header words written by the job (+0x00..+0x24), excluding consumed (+4)
hdr_bad = 0; cons_bad = 0
for a, b in zip(A[:n], B[:n]):
    wa = struct.unpack('>10I', a['sout'][:40]); wb = struct.unpack('>10I', b['sout'][:40])
    if wa[:1] + wa[2:] != wb[:1] + wb[2:]: hdr_bad += 1
    if wa[1] != wb[1]: cons_bad += 1
print('header words +00,+08..+24 differ in', hdr_bad, 'jobs; consumed (+04) differs in', cons_bad, 'jobs')
print('S size PUT A', len(A[1]['sout']), 'B', len(B[1]['sout']), '; PUT lists equal (lsa,ea,size,tag):',
      sum(a['puts'] == b['puts'] for a, b in zip(A[:n], B[:n])), '/', n)
