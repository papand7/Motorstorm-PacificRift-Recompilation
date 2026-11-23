"""Relighting census: classify MotorStorm's decompiled fragment programs (the HLSL the engine sends to
glslang, extracted from the SPIR-V cache into generated/analysis/relight/census/<hash>_s1.hlsl) by
how they light a pixel:

  sun    dot(N, +-fp_constants[k]) -- a constant direction -> the light-direction constant(s)
  shadow _rsx_shadow<unit>(...)    -- the sun's shadow map unit
  albedo _rsx_gamma_input(rsx_tex[u] ...) -- sRGB colour textures
  nmap   a texture result * 2 or (x + c) * 2 -- tangent-space normal map unpack
  cube   TextureCube sampling (reflection / ambient probe)
  mrt    number of SV_TARGET outputs
  inputs the varyings read (tcN, col0/col1, fog)

usage: py -3 census.py [census dir] [--list]"""
import collections
import re
import sys
from pathlib import Path

D = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else \
    Path(__file__).resolve().parents[1] / 'census'

rx_tex = re.compile(r'rsx_tex\[(\d+)\]\.Sample(?:Level)?\(rsx_samp\[\d+\],\s*\(\(input\.(\w+)\)')
rx_tex_any = re.compile(r'rsx_(?:tex|cube)\[?(\d+)\]?\.Sample')
rx_gamma = re.compile(r'_rsx_gamma_input\(rsx_tex\[?(\d+)\]?')
rx_shadow = re.compile(r'_rsx_shadow(\d+)\(\(')
rx_dotc = re.compile(r'dot\(([^;]*?)fp_constants\[(\d+)\]')
rx_bx2 = re.compile(r'\(rsx_tex\[?(\d+)\]?[^;]*?\)\)\)? \* 2\.0|\(\(\(h\[\d+\]\)\.xyzw\) \+ \(\(fp_constants\[\d+\]\)\.xyzw\)\) \* 2\.0')
rx_in = re.compile(r'input\.(tc\d|col0|col1|fog)')
rx_cube = re.compile(r'rsx_cube\[?\d+\]?\.Sample')
rx_mrt = re.compile(r'SV_TARGET(\d)')
rx_nconst = re.compile(r'fp_constants\[(\d+)\];')

rows = []
for f in sorted(D.glob('*_s1.hlsl')):
    t = f.read_text(encoding='utf-8', errors='replace')
    body = t[t.find('PSOutput main'):] if 'PSOutput main' in t else t[t.find('main('):]
    tex = sorted({int(u) for u in rx_tex_any.findall(body)})
    rows.append(dict(
        name=f.stem.split('_')[0], size=len(t),
        tex=tex,
        gamma=sorted({int(u) for u in rx_gamma.findall(body)}),
        shadow=sorted({int(u) for u in rx_shadow.findall(body)}),
        dotc=sorted({int(c) for _, c in rx_dotc.findall(body)}),
        bx2='* 2.0' in body and bool(rx_bx2.search(body)),
        cube=bool(rx_cube.search(t)),
        mrt=len(set(rx_mrt.findall(t))) or 1,
        inputs=sorted(set(rx_in.findall(body))),
        nconst=int((rx_nconst.findall(t) or ['0'])[0]),
        instrs=body.count('{ float4 _v'),
    ))

lit = [r for r in rows if r['dotc'] and r['shadow']]
print(f'{len(rows)} fragment programs; {sum(1 for r in rows if r["shadow"])} sample a shadow map, '
      f'{sum(1 for r in rows if r["dotc"])} dot a normal with a constant, {len(lit)} both (sun-lit, shadowed)')
print(f'  shadow units: {collections.Counter(u for r in rows for u in r["shadow"])}')
print(f'  sun constant index: {collections.Counter(c for r in lit for c in r["dotc"])}')
print(f'  sRGB albedo units in lit programs: {collections.Counter(u for r in lit for u in r["gamma"])}')
print(f'  normal-map unpack in lit programs: {sum(1 for r in lit if r["bx2"])}; cube maps: '
      f'{sum(1 for r in rows if r["cube"])}; MRT outputs: {collections.Counter(r["mrt"] for r in rows)}')
sig = collections.Counter((tuple(r['tex']), tuple(r['shadow']), tuple(r['dotc']), r['mrt']) for r in lit)
print(f'  distinct (units, shadow, sun const, mrt) signatures among lit programs: {len(sig)}; top:')
for (u, s, c, m), n in sig.most_common(8):
    print(f'    {n:3d}  units {list(u)} shadow {list(s)} sun c{list(c)} mrt {m}')
unlit = [r for r in rows if not r['shadow']]
print(f'  unshadowed programs: {len(unlit)}; with a constant-dot (lit without shadow): '
      f'{sum(1 for r in unlit if r["dotc"])}')
if '--list' in sys.argv:
    for r in sorted(rows, key=lambda r: (not r['shadow'], -r['instrs'])):
        print(f"{r['name']} instr {r['instrs']:3d} tex {r['tex']} srgb {r['gamma']} shadow {r['shadow']} "
              f"dot c{r['dotc']} nmap {int(r['bx2'])} cube {int(r['cube'])} mrt {r['mrt']} in {r['inputs']}")
