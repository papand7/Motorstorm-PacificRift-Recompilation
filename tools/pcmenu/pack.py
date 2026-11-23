# Read-only (no game data included): parse the outer 'EVOSBIG ' resource pack of a .gui file (MotorStorm PR).
# File: 'EVOSBIG ' u32 len, title[len] ("Resource PacK file"), u32 dirSize, u32 dirOff
# Dir section @dirOff: 'EVOSBIG ' id8(type 0x0001) u16 ver(4) u16 0 u32 0x11111111 u32 nEnt u32 nNames u32 nDeps
#   u32 namesLen u32 pathsLen id8 rootId ; names ; paths ; entries ; u32 0x99999999
# Entry: id8 u32 size u32 off u16 nDeps id8[nDeps] u16 nName u32 nameOff[nName] u16 nPath u32 pathOff[nPath]
import struct, sys
def be(fmt, d, o): return struct.unpack_from('>'+fmt, d, o)
def parse(d):
    if d[:8] != b'EVOSBIG ': return None
    (slen,) = be('I', d, 8); title = d[12:12+slen]
    o = 12 + slen
    dsize, doff = be('II', d, o)
    D = doff
    assert d[D:D+8] == b'EVOSBIG '
    did = d[D+8:D+16]
    ver, z, sent, nent, nnames, ndeps, nlen, plen = be('HHIIIIII', d, D+16)
    rootid = d[D+16+28:D+16+36]
    p = D+16+36
    nb = d[p:p+nlen]; p += nlen
    pb = d[p:p+plen]; p += plen
    gs = lambda b, k: b[k:b.index(b'\0', k)].decode('latin1')
    ents = []
    for i in range(nent):
        eid = d[p:p+8]; size, off = be('II', d, p+8); p += 16
        (nd,) = be('H', d, p); p += 2
        deps = [d[p+8*k:p+8*k+8].hex() for k in range(nd)]; p += 8*nd
        (nn,) = be('H', d, p); p += 2
        nms = [gs(nb, be('I', d, p+4*k)[0]) for k in range(nn)]; p += 4*nn
        (np_,) = be('H', d, p); p += 2
        pts = [gs(pb, be('I', d, p+4*k)[0]) for k in range(np_)]; p += 4*np_
        sec = d[off:off+8]; sid = d[off+8:off+16].hex()
        ents.append(dict(id=eid.hex(), size=size, off=off, deps=deps, names=nms, paths=pts, secmagic=sec, secid=sid))
    term = be('I', d, p)[0]; p += 4
    return dict(title=title, slen=slen, dsize=dsize, doff=doff, dirid=did.hex(), ver=ver, z=z, sent=sent, nent=nent, nnames=nnames,
                ndeps=ndeps, nlen=nlen, plen=plen, rootid=rootid.hex(), ents=ents, dirend=p, term=term)
def page_section(d):
    r = parse(d)
    e = [e for e in r['ents'] if e['id'] == r['rootid']][0]
    o = e['off']
    ver, z, dsz, rsz = be('HHII', d, o+16)
    return dict(off=o, base=o+0x1C, ver=ver, z=z, datasize=dsz, relocsize=rsz, size=e['size'])
if __name__ == '__main__':
    for f in sys.argv[1:]:
        d = open(f,'rb').read(); r = parse(d)
        if not r: print(f, 'not a pack'); continue
        print(f, len(d), {k:v for k,v in r.items() if k not in ('ents',)})
        for e in r['ents']:
            print(f"   {e['id']} size={e['size']:#x} off={e['off']:#x} end={e['off']+e['size']:#x} ok={e['secmagic']==b'EVOSBIG ' and e['secid']==e['id']} {e['names']} {e['paths']} deps={len(e['deps'])}")
        print('   page', page_section(d))
