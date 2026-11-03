"""T157: how often does the backend's sparse texture checksum (libs/video/rsx_d3d12_backend.c tex_csum, the per-pass
re-check of a kept texture) miss a partial write such as a new glyph in a font atlas?

tex_csum samples one 32-bit word every `step` bytes, step = nbytes / 1024 above 4 KB. This port reproduces exactly
which byte offsets are read, then writes one glyph-sized rectangle at every glyph-aligned position of an atlas and
counts the positions whose bytes are never sampled (the checksum is unchanged, so the stale texture is kept).
  py -3 csum_blindspot_t157.py        prints one line per atlas shape"""


def sampled(nbytes):
    step = nbytes // 1024 if nbytes > 4096 else 4
    s = set()
    i = 0
    while i + 3 < nbytes:
        s.update(range(i, i + 4))
        i += step
    return s


def blind(w, h, bpp, gw, gh):
    pitch = w * bpp
    smp = sampled(pitch * h)
    tot = miss = 0
    for gy in range(0, h - gh + 1, gh):
        for gx in range(0, w - gw + 1, gw):
            tot += 1
            hit = any((gy + y) * pitch + (gx + x) * bpp + b in smp
                      for y in range(gh) for x in range(gw) for b in range(bpp))
            miss += not hit
    return tot, miss


for w, h, bpp, gw, gh in ((1024, 1024, 1, 32, 32), (512, 512, 1, 32, 32), (1024, 1024, 4, 32, 32),
                          (512, 512, 4, 16, 16), (256, 256, 1, 16, 16), (2048, 2048, 1, 32, 32)):
    tot, miss = blind(w, h, bpp, gw, gh)
    print(f'atlas {w}x{h} {bpp} B/px, glyph {gw}x{gh}: {miss}/{tot} glyph positions never sampled '
          f'({100 * miss / tot:.0f} %), step {(w * h * bpp) // 1024} B')
