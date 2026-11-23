import re,glob,collections,sys
n=0;c0=0;c1=0;units=collections.Counter();combo=collections.Counter();sat=0
for f in glob.glob('*.hlsl'):
    s=open(f).read()
    if '_rsx_shadow13(' not in s or 'dot(' not in s: continue
    n+=1
    u=sorted(set(map(int,re.findall(r'rsx_tex\[(\d+)\]\.Sample\(',s))))
    for x in u: units[x]+=1
    combo[tuple(u)]+=1
    if 'input.col0' in s: c0+=1
    if re.search(r'saturate\(input\.col0\)',s): sat+=1
    if 'input.col1' in s: c1+=1
print(n,'col0',c0,'sat(col0)',sat,'col1',c1)
print(sorted(units.items()))
print(combo.most_common(8))
