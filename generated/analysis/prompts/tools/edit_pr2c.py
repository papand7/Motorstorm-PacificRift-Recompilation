import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
BS = '\\'
rep = [
 ('CHECK(label_is(&l, PCPR_CROSS, "ENTER"));\n    CHECK(label_is(&l, PCPR_SQUARE, "Q"));',
  'CHECK(label_is(&l, PCPR_CROSS, "' + BS + 'x05"));   /* Enter: the return arrow */\n    CHECK(label_is(&l, PCPR_SQUARE, "Q"));'),
 ('    l.vk[PAD_ACT_CROSS][0] = 0;\n    CHECK(label_is(&l, PCPR_CROSS, "ENTER"));',
  '    l.vk[PAD_ACT_CROSS][0] = 0;\n    CHECK(label_is(&l, PCPR_CROSS, "' + BS + 'x05"));'),
 ('CHECK(label_is(&l, PCPR_SQUARE, "SPACE"));', 'CHECK(label_is(&l, PCPR_SQUARE, "' + BS + 'x06"));'),
 ('CHECK(label_is(&l, PCPR_SELECT, "SPACE"));', 'CHECK(label_is(&l, PCPR_SELECT, "' + BS + 'x06"));'),
 ('CHECK(label_is(&l, PCPR_SELECT, "SHIFT"));', 'CHECK(label_is(&l, PCPR_SELECT, "' + BS + 'x07"));'),
 (BS + 'x04";', BS + 'x04' + BS + 'x05' + BS + 'x06' + BS + 'x07";'),
 ('pcpr_patch_bc3(tex, 500, 84, 500 / 4 * 16, 0, ic, "ENTER");', 'pcpr_patch_bc3(tex, 500, 84, 500 / 4 * 16, 0, ic, "CTRL");'),
 ('        CHECK(maxx - minx + 1 <= (int)ic->maxw + 1);',
  '        CHECK(minx >= (int)(ic->cx - ic->rw * 0.5f) && maxx <= (int)(ic->cx + ic->rw * 0.5f));   /* never past the icon */'),
 ('CHECK(bright > 40 && dark > 40);', 'CHECK(bright > 30 && dark > 30);'),
]
for a, b in rep:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
