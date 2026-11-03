import json,os,subprocess,sys
sys.path.insert(0,os.path.dirname(__file__))
from common import *
H=os.path.dirname(__file__)
FILT=os.path.abspath(os.path.join(R,'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/llvm-cxxfilt.exe'))
M=json.load(open(os.path.join(H,'..','retail_devnames.json')))
STUBS={int(k,16):(v[1] or v[0]+'?') for k,v in json.load(open(os.path.join(R,'generated/analysis/garage_menu/stubs.json'))).items()}
_dm={}
def demangle(ns):
    need=[n for n in ns if n not in _dm]
    if need:
        out=subprocess.run([FILT],input='\n'.join(need),capture_output=True,text=True).stdout.split('\n')
        for a,b in zip(need,out): _dm[a]=b
    return [_dm[n] for n in ns]
def resolve(t):
    """follow xtoc trampoline; return (final_target, import name or None)"""
    if t in STUBS: return t,STUBS[t]
    if w(t)==0xf8410028 and w(t+12)>>26==18:
        f=br(t+12,w(t+12)); return f,STUBS.get(f)
    return t,None
def name(t):
    t,imp=resolve(t)
    if imp: return t,'IMPORT '+imp
    k='%#x'%t
    if k in M:
        kind,ns=M[k]; d=demangle(ns)
        return t,('' if kind=='full' else '~')+' | '.join(d)
    return t,''
