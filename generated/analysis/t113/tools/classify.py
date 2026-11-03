import PIL.Image as I, glob, io, os, sys
d=sys.argv[1]; t0=float(sys.argv[2]); out=sys.argv[3]; os.makedirs(out,exist_ok=True)
for f in sorted(glob.glob(os.path.join(d,'frames','*.bmp'))):
    im=I.open(io.BytesIO(open(f,'rb').read())).convert('RGB'); L=im.convert('L'); h=L.histogram(); n=sum(h)
    mean=sum(i*c for i,c in enumerate(h))/n
    cls='BLACK' if h[0]==n else 'WHITE%d%%'%(100*h[255]//n)
    print('%s t=%.0fs %s mean=%.1f levels=%d'%(os.path.basename(f), os.path.getmtime(f)-t0, cls, mean, sum(1 for c in h if c)))
    im.resize((640,360)).save(os.path.join(out, os.path.basename(f)[:-4]+'.png'))
