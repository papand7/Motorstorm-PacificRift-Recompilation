import sys
p=sys.argv[1]
s=open(p,encoding='utf-8',newline='').read()
crlf='\r\n' in s
if crlf: s=s.replace('\r\n','\n')
def rep(old,new,count=1):
    global s
    assert s.count(old)==count,(old[:70],s.count(old)); s=s.replace(old,new)
exec(open(sys.argv[2],encoding='utf-8').read())
if crlf: s=s.replace('\n','\r\n')
open(p,'w',encoding='utf-8',newline='').write(s); print('ok',p)
