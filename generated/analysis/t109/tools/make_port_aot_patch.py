"""T109: the MSPR_WWS_AOT CMake block that race builds lack.

port/CMakeLists.txt (what build/motorstorm-t96i configures from) has no
MSPR_WWS_AOT option; port-t70/CMakeLists.txt has it. This copies that block
verbatim into a candidate next to the analysis (port/ itself is not touched),
inserted at the same place as in port-t70 (before the discovered-overlay
glob), and writes a unified diff. The option is OFF by default, so a
configure without -DMSPR_WWS_AOT=ON produces the same source list.
  python make_port_aot_patch.py"""
import difflib
from pathlib import Path

M = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1] / 'port'
OUT.mkdir(exist_ok=True)
src70 = (M / 'port-t70/CMakeLists.txt').read_text(encoding='utf-8')
port = (M / 'port/CMakeLists.txt').read_text(encoding='utf-8')

start = src70.index('# Optional relocatable AOT of the Wws job modules')
end = src70.index('\nendif()\n', src70.index('if(MSPR_WWS_AOT)', start)) + len('\nendif()\n')
block = src70[start:end]
opens = sum(1 for l in block.splitlines() if l.strip().startswith('if('))
closes = sum(1 for l in block.splitlines() if l.strip() == 'endif()')
assert opens == closes == 3, f'unbalanced block {opens}/{closes}'
assert 'MSPR_WWS_AOT' not in port, 'port/ already has the block'

anchor = '# Additional locally discovered overlays live only in ignored generated/.'
assert port.count(anchor) == 1 and src70.count(anchor) == 1, 'anchor missing or ambiguous'
assert src70.index(anchor) > end, 'block is not before the anchor in port-t70'
new = port.replace(anchor, block + '\n' + anchor, 1)

(OUT / 'CMakeLists.txt').write_text(new, encoding='utf-8')
diff = ''.join(difflib.unified_diff(port.splitlines(True), new.splitlines(True),
                                    'a/port/CMakeLists.txt', 'b/port/CMakeLists.txt'))
(OUT / 'port_wws_aot.patch').write_text(diff, encoding='utf-8')
added = [l for l in diff.splitlines() if l.startswith('+') and not l.startswith('+++')]
removed = [l for l in diff.splitlines() if l.startswith('-') and not l.startswith('---')]
print(f'block {block.count(chr(10))} lines; diff +{len(added)} -{len(removed)}')
assert not removed
