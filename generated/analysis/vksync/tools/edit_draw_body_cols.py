"""One-off edit: vk_eng_draw_body takes draw_columns' columns and says whether it took them
(rsx_vulkan_backend.c, RSX_VTX_GPU). Bare returns inside it become `return 1` (dropped, as before)."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'libs' / 'video' / 'rsx_vulkan_backend.c'
s = p.read_bytes().decode('latin-1')
CR = '\r'
L = s.split('\n')
i = [k for k, l in enumerate(L) if l.startswith('static void vk_eng_draw_body(')][0]
e = next(k for k in range(i, len(L)) if L[k].rstrip(CR) == '}')
n = 0
for k in range(i, e):
    if 'return;' in L[k]:
        L[k] = L[k].replace('return;', 'return 1;')
        n += 1
assert L[i].rstrip(CR) == 'static void vk_eng_draw_body(rsx_topology topology, const void* vertices, u32 vertex_count,'
assert L[i + 1].rstrip(CR) == '                             u32 stride, const u32* indices, u32 index_count)'
L[i] = 'static int vk_eng_draw_body(rsx_topology topology, const void* vertices,' + CR
L[i + 1] = ('                            const rsx_be_vtx_column* cols, u32 ncols, u32 vertex_count,' + CR + '\n'
            '                            u32 stride, const u32* indices, u32 index_count)' + CR)
body = L[i:e + 1]
out = []
k = 0
while k < len(body):
    t = body[k].rstrip(CR)
    if t == '    if (!s_e2.pipeline || !vertices || !vertex_count || !stride) return 1;':
        out.append('    if (!s_e2.pipeline || (!vertices && !cols) || !vertex_count || !stride) return 1;' + CR)
    elif t == '    if (s_b.on) {':
        assert body[k + 1].strip() == 'vk_batch_draw(P, pipe, rp, fb, w, h, vertices, vertex_count, stride, indices, index_count);'
        assert body[k + 2].strip() == 'return 1;' and body[k + 3].rstrip(CR) == '    }'
        out += ['    if (s_b.on)' + CR,
                '        return vk_batch_draw(P, pipe, rp, fb, w, h, vertices, cols, ncols, vertex_count, stride,' + CR,
                '                             indices, index_count);' + CR,
                '    if (cols) return 0;   /* the synchronous path takes CPU-decoded vertices only */' + CR]
        k += 3
    elif k == len(body) - 1:
        out += ['    return 1;' + CR, body[k]]
    else:
        out.append(body[k])
    k += 1
L[i:e + 1] = out
s = '\n'.join(L)
a = 'vk_eng_draw_body(topology, vertices, vertex_count, stride, indices, index_count);'
assert s.count(a) == 2, s.count(a)
s = s.replace(a, 'vk_eng_draw_body(topology, vertices, NULL, 0, vertex_count, stride, indices, index_count);')
p.write_bytes(s.encode('latin-1'))
print('bare returns changed:', n)
