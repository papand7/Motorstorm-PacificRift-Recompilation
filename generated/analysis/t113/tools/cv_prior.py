MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
import PIL.Image as I, collections, os, sys, io
base=(MS_ROOT + r'\generated\analysis')
for a,n in [('A2-20261027-140411',1),('A2-20261027-140411',0),('A2-20261027-140411',11),('B1-20261027-135436',5)]:
    p=os.path.join(base,'t106','ab','runtime-'+a,'frames','frame_%03d.bmp'%n)
    b=open(p,'rb').read(); print(len(b), b[:2])
    try: im=I.open(io.BytesIO(b)).convert('RGB')
    except Exception as e: print('ERR',e); continue
    im.resize((640,360)).save(os.path.join(base,'t113','prior_t106','%s_frame_%03d.png'%(a[:2],n)))
    px=list(im.getdata())
    print(a,n,len(set(px)), collections.Counter(px).most_common(3))
