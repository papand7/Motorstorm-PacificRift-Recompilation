import numpy as np
from PIL import Image
D='../ab/runtime-D1-20261030-171539/rsxi/frames/f005110/'
a=np.asarray(Image.open(D+'snap01_pass_op0982_rt_00750000.bmp').convert('RGB')).astype(float)
b=np.asarray(Image.open(D+'snap05_pass_op1112_rt_00750000.bmp').convert('RGB')).astype(float)
print(a.shape)
d=np.abs(b-a).sum(2)>12
ys,xs=np.nonzero(d); print('changed',len(ys),'ybox',ys.min(),ys.max(),'xbox',xs.min(),xs.max())
cx,cy,ox,oy=0.000786163,-0.0013986,0.000195313,1.00699
H,W=a.shape[:2]
def sample(y,x):
    return a[np.clip(y,0,H-1).astype(int),np.clip(x,0,W-1).astype(int)]
xx=xs+0.5; yy=ys+0.5
u=xx*cx+ox
vs=yy*cy+oy    # host today: top-left WPOS
vb=(720-yy)*cy+oy  # guest: bottom-left WPOS
# host viewed image is 1280x720 surface; uv 0..1 maps onto window 1272x715 of surface at host RT_WINDOW off => whole 1280x720
for name,v,scale in [('host_mirror full-surface',vs,(W,H)),('host_mirror window',vs,(1272,715)),('guest bottom-left window',vb,(1272,715)),('guest bottom-left full',vb,(W,H))]:
    px=sample(v*scale[1],u*scale[0])
    res=b[ys,xs]
    # lighting scales colour, use per-pixel luma correl and rgb-chroma error
    c=np.corrcoef(px.mean(1),res.mean(1))[0,1]
    print(f'{name:28s} luma corr {c:.3f} mean abs err {np.abs(px-res).mean():.1f}')
print('no-change (res vs a at same px) corr',np.corrcoef(a[ys,xs].mean(1),b[ys,xs].mean(1))[0,1])
print('res mean',b[ys,xs].mean(0),'prior mean',a[ys,xs].mean(0))
c=Image.fromarray(b[230:340,600:1280].astype('uint8')).resize((1360,220));
c2=Image.fromarray(a[720-340:720-230,600:1280][::-1].astype('uint8')).resize((1360,220))
o=Image.new('RGB',(1360,450));o.paste(c,(0,0));o.paste(c2,(0,230));o.save((__import__('tempfile').gettempdir() + '/m.png'))
