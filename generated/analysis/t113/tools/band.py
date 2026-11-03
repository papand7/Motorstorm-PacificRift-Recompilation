import PIL.Image as I, io, sys
p=sys.argv[1]; im=I.open(io.BytesIO(open(p,'rb').read())).convert('RGB')
W,H=im.size; px=im.load()
# rows with many pure-black pixels
for y in range(0,H,4):
    n=sum(1 for x in range(0,W,2) if px[x,y]==(0,0,0))
    if n>20: print('row',y,'black',n*2)
im.crop((0,380,640,560)).save(sys.argv[2])
