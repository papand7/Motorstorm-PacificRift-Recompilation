import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
i = s.index('/* One icon in one known texture.'); j = s.index('#define PCPR_ICON_COUNT')
new = open(sys.argv[2], encoding='utf-8').read()
s = s[:i] + new + s[j:]
for a, b in [('{ 0x0D, "ENTER" }', '{ 0x0D, "\\x05" }'), ('{ 0x10, "SHIFT" }', '{ 0x10, "\\x07" }'),
             ('{ 0x20, "SPACE" }', '{ 0x20, "\\x06" }')]:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
a = '/* down */\n'
assert s.count(a) == 1
s = s.replace(a, a + "    case '\\x05': return \"4,0 4,4 0,4|2,2 0,4 2,6\";   /* return arrow (Enter) */\n"
                     "    case '\\x06': return \"0,3 0,5 4,5 4,3\";   /* open box (Space) */\n"
                     "    case '\\x07': return \"2,0 4,3 3,3 3,6 1,6 1,3 0,3 2,0\";   /* outlined up arrow (Shift) */\n")
open(p, 'w', encoding='utf-8').write(s)
print('ok')
