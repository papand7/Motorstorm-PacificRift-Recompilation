"""T133: tally race texture bindings: guest filter/mip/LOD/aniso state vs the host sampler and view.

usage: python tex_tally.py <events.jsonl> [...]
Decodes SET_TEXTURE_FILTER / CONTROL0 / ADDRESS as RPCS3 does (rsx_decode / gcm_enums):
  FILTER  [12:0] bias s4.8 (signed 13 bit), [15:13] conv, [18:16] min, [26:24] mag,
          [28..31] ASIGNED/RSIGNED/GSIGNED/BSIGNED
  CONTROL0 [31] enable, [30:19] min LOD u4.8, [18:7] max LOD u4.8, [6:4] max aniso, [3:2] alpha kill
"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't113', 'tools'))
from ev import events

MIN = {1: 'N', 2: 'L', 3: 'N_MIP_N', 4: 'L_MIP_N', 5: 'N_MIP_L', 6: 'L_MIP_L', 7: 'CONV'}
MAG = {1: 'N', 2: 'L', 4: 'CONV'}
ANISO = [1, 2, 4, 6, 8, 10, 12, 16]


def dec(t):
    r = t['req']
    f = int(r['filter'], 16); c0 = int(r['control0'], 16); a = int(r['address'], 16)
    b = f & 0x1FFF
    if b & 0x1000: b -= 0x2000
    return dict(min=MIN.get((f >> 16) & 7, '?%d' % ((f >> 16) & 7)), mag=MAG.get((f >> 24) & 7, '?%d' % ((f >> 24) & 7)),
                conv=(f >> 13) & 7, bias=b / 256.0, signed=(f >> 28) & 0xF,
                en=c0 >> 31, minlod=((c0 >> 19) & 0xFFF) / 256.0, maxlod=((c0 >> 7) & 0xFFF) / 256.0,
                aniso=ANISO[(c0 >> 4) & 7], akill=(c0 >> 2) & 3,
                wrap=(a & 0xF, (a >> 8) & 0xF, (a >> 16) & 0xF), zfunc=(a >> 28) & 0xF,
                mips=r.get('mips', 1), fmt=r['fmt'], w=r['w'], h=r['h'], host=r.get('host_sampler', '?'),
                src=t.get('src'))


def main(paths):
    combo = collections.Counter(); hostc = collections.Counter(); unit_host = collections.Counter()
    akill = collections.Counter(); aniso = collections.Counter(); bias = collections.Counter()
    ndraw = 0; nbind = 0; mipbind = 0; mipfilt = 0
    for p in paths:
        for e in events(p):
            if 'tex' not in e: continue
            ndraw += 1
            for t in e['tex']:
                if not t.get('req', {}).get('set'): continue
                d = dec(t); nbind += 1
                if d['mips'] > 1: mipbind += 1
                if d['min'].find('MIP') >= 0: mipfilt += 1
                combo[(d['fmt'], d['mips'] > 1, d['min'], d['mag'], d['host'])] += 1
                unit_host[(t['unit'], d['host'], d['min'], d['mag'])] += 1
                aniso[(d['aniso'], d['min'])] += 1
                bias[(round(d['bias'], 3), d['minlod'], d['maxlod'])] += 1
                akill[d['akill']] += 1
    print('draws with tex %d, bindings %d, chains advertised %d, mip min filter %d' % (ndraw, nbind, mipbind, mipfilt))
    print('\n(fmt, chain, min, mag, host) top:')
    for k, v in combo.most_common(25): print('  %6d %s' % (v, k))
    print('\n(unit, host, min, mag) top:')
    for k, v in unit_host.most_common(25): print('  %6d %s' % (v, k))
    print('\n(aniso, min):', aniso.most_common(10))
    print('\n(bias, minlod, maxlod):', bias.most_common(10))
    print('\nalpha kill (CONTROL0[3:2]):', dict(akill))


if __name__ == '__main__':
    main(sys.argv[1:])
