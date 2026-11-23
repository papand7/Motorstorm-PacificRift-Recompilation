import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
i = s.index('typedef struct {\n    float x0, y0, w, h;        /* the cap')
j = s.index('/* The cap\'s RGBA at texel centre')
new = open(sys.argv[2], encoding='utf-8').read()
s = s[:i] + new + s[j:]
a = '''        const float gx = (px - c->ox) / c->sx, gy = (py - c->oy) / c->sx;
        float dm = 1e9f;
        for (int i = 0; i < c->nseg; i++) { const float s = pcpr_seg_dist(gx, gy, &c->seg[i]); if (s < dm) dm = s; }
        tx = pcpr_clamp01(c->hw + 0.5f - dm * c->sx);'''
b = '''        float dm = 1e9f;   /* the strokes are in texels (pcpr_cap_make) */
        for (int i = 0; i < c->nseg; i++) { const float s = pcpr_seg_dist(px, py, &c->seg[i]); if (s < dm) dm = s; }
        tx = pcpr_clamp01(c->hw + 0.5f - dm);'''
assert s.count(a) == 1
s = s.replace(a, b)
a = '    const float r = c->h * 0.22f;\n'
assert s.count(a) == 1
s = s.replace(a, '    const float r = (c->w < c->h ? c->w : c->h) * 0.22f;\n')
open(p, 'w', encoding='utf-8').write(s)
print('ok')
