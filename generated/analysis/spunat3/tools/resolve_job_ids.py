import json,sys,os
want={int(k,16):k for k in ['2e29dde','2b93b080','9cc94279','64ab83b','1266e45a','1d51c6ce','145c1b7b']}
def fnv(b):
    h=2166136261
    for x in b: h=((h^x)*16777619)&0xffffffff
    return h
for dn in ['wws_modules_v100']:
  for f in sorted(os.listdir(dn)):
    if not f.endswith('.bin'): continue
    d=open(os.path.join(dn,f),'rb').read()
    for off in range(0,len(d)-64,16):
        h=fnv(d[off:off+64])
        if h in want: print(dn,f,len(d),hex(off),want[h])
