# list callers of timing-related import stubs, syscalls and mftb in EBOOT text
import json,collections,sys
from elf import *
S=json.load(open(os.path.join(R,'generated/analysis/garage_menu/stubs.json')))
want={int(k,16):v[1] for k,v in S.items() if v[1] and any(s in v[1] for s in
 ['Gcm','sys_time','VideoOut','ppu_thread_create','Timestamp','Rtc'])}
calls=collections.defaultdict(list)
sysc=collections.defaultdict(list); mftb=[]
END=0xCC1000
prev=[0]*8
for a in range(0x10200,END,4):
    x=w(a)
    if x>>26==18 and (x&3)==1:
        t=br(a,x)
        if t in want: calls[t].append(a)
        elif 0x10000<=t<END and w(t)==0xf8410028 and w(t+12)>>26==18:
            f=br(t+12,w(t+12))
            if f in want: calls[f].append(a)
    if x==0x44000002:
        # search back for li r11,N
        for b in range(a-4,a-40,-4):
            y=w(b)
            if y>>16==0x3960: sysc[y&0xffff].append(a); break
        else: sysc['?'].append(a)
    if (x&0xFC1FFFFE)==0x7C0C42E6 or (x&0xFC1FFFFE)==0x7C0C42A6 or (x&0xFC1FFFFE)==0x7C0D42E6 or (x&0xFC1FFFFE)==0x7C0D42A6:
        mftb.append(a)
for t in sorted(calls):
    print('%s %#x'%(want[t],t))
    for a in calls[t]: print('   call %#x in fn %#x'%(a,fn(a)))
print('SYSCALLS')
for n in sorted(sysc,key=str):
    if n in (130,141,142,144,145,146,147,'?') : print(n,[('%#x'%a,'%#x'%fn(a)) for a in sysc[n]])
    else: print(n,len(sysc[n]))
print('MFTB',[('%#x'%a,'%#x'%fn(a)) for a in mftb])
