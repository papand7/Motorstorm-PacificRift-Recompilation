"""Black-pixel share inside the screen block of exposure texel (2,11) (x 160-240, y 495-540 at 1280x720) and its rows."""
import PIL.Image as I, io, sys
for p in sys.argv[1:]:
    im=I.open(io.BytesIO(open(p,'rb').read())).convert('RGB'); px=im.load()
    blk=[(x,y) for x in range(160,240) for y in range(450,560)]
    rows={}
    for x,y in blk:
        if px[x,y]==(0,0,0): rows[y]=rows.get(y,0)+1
    print(p.split('/')[-1], 'black px in x160-240 y450-560:', sum(rows.values()), 'rows', (min(rows),max(rows)) if rows else None)
