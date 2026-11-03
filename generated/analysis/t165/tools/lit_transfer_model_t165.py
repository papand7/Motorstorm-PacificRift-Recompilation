"""T165: predicted framebuffer value for a lit surface, RSX colour transfers applied vs the default D3D12 path
(no texture gamma, no sRGB output). Light values are the race capture's VP c40 (4.5) and c41 (about 0.28);
their meaning as sun and ambient is a HYPOTHESIS. Only the transfer curves are exact."""
def d(v): return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
def e(v):
    v = min(max(v, 0.0), 1.0)
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
print('albedo  light  RSX    default  default/RSX')
for t in (0.1, 0.2, 0.5, 0.8):
    for L in (0.05, 0.28, 1.0, 2.0, 4.5):
        hw, ours = e(d(t) * L), min(t * L, 1.0)
        print(f'{t:5.2f} {L:6.2f} {hw:6.3f} {ours:6.3f} {ours / hw:8.2f}')
