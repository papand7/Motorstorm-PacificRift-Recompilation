# scan lfs/lfd from r2 (TOC-inline constants) for timing-like values
import collections,math
from elf import *
INT={1/30:'1/30',1/60:'1/60',1/120:'1/120',1/240:'1/240',1/50:'1/50',1/25:'1/25',1/15:'1/15',1/180:'1/180',1/300:'1/300',1/90:'1/90',
 30.0:'30',60.0:'60',59.94:'59.94',29.97:'29.97',59.94005994:'60000/1001',1001/60000:'1001/60000',1001/30000:'1001/30000',120.0:'120',240.0:'240',
 0.1:'0.1',0.05:'0.05',0.25:'0.25',1e-6:'1e-6',1e-3:'1e-3',1000.0:'1000',1e6:'1e6',0.0333:'0.0333',0.0166:'0.0166',0.016:'0.016',0.033:'0.033',0.5:'0.5',1/79800000:'1/tb',79800000.0:'tbfreq'}
hits=collections.defaultdict(list)
for a in range(0x10200,0xCC1000,4):
    x=w(a); op=x>>26
    if op not in (48,50) or ((x>>16)&31)!=2: continue
    simm=x&0xffff; simm=simm-0x10000 if simm&0x8000 else simm
    ea=tocof(a)+simm
    v=f32(ea) if op==48 else f64(ea)
    for k,n in INT.items():
        if v!=0 and abs(v-k)/abs(k)<2e-4 and n not in('0.5','0.1','0.25','1000','1e-3','1e-6','1e6','0.05'):
            hits[n].append((a,fn(a),('%#x'%w(ea)) if op==48 else ('%#x'%q(ea)),v))
for n in hits:
    fns=collections.Counter(f for a,f,_,_ in hits[n])
    print('==',n,len(hits[n]),'sites; bits',sorted(set(b for _,_,b,_ in hits[n])))
    for a,f,b,v in hits[n][:60]: print('   %#x fn %#x %s %r'%(a,f,b,v))
