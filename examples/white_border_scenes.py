"""Original light-background fixtures for localization regression checks."""
from __future__ import annotations
import cv2
import numpy as np

KINDS=('white-frame','faint-side','text-page','portrait')


def make_scene(kind,seed=0):
    if kind not in KINDS:raise ValueError(kind)
    rng=np.random.default_rng(51000+seed)
    h,w=600,840
    yy,xx=np.mgrid[:h,:w]
    background=191+9*(xx/w)+5*(yy/h)**2
    scene=np.repeat(background[:,:,None],3,axis=2)
    scene+=rng.normal(0,.7,scene.shape)
    scene=np.uint8(np.clip(scene,0,255))
    ph,pw=(350,245) if kind=='portrait' else (320,320)
    picture=np.full((ph,pw,3),224,np.uint8)
    if kind=='text-page':
        for i,text in enumerate(('A complete page','with white edges','and dark letters','preserves space','around its text')):
            cv2.putText(picture,text,(4,43+i*54),cv2.FONT_HERSHEY_SIMPLEX,.65,(48,48,48),2,cv2.LINE_AA)
    else:
        start=135 if kind=='faint-side' else 23
        if kind=='faint-side':picture[:]=202
        for y in range(17,ph-17):
            for x in range(start,pw-17):
                picture[y,x]=(65+x//3,55+y//3,160+(x+y)%45)
        for _ in range(30):
            x=int(rng.integers(start+5,pw-22));y=int(rng.integers(24,ph-24))
            cv2.circle(picture,(x,y),int(rng.integers(3,11)),tuple(int(v) for v in rng.integers(25,220,3)),-1)
    width=250 if kind=='portrait' else 330
    height=365 if kind=='portrait' else 338
    x=int(rng.integers(225,265));y=int(rng.integers(102,132))
    quad=np.float32([[x+7,y],[x+width,y+4],[x+width+10,y+height],[x-6,y+height+2]])
    matrix=cv2.getPerspectiveTransform(np.float32([[0,0],[pw-1,0],[pw-1,ph-1],[0,ph-1]]),quad)
    pixels=cv2.warpPerspective(picture,matrix,(w,h),flags=cv2.INTER_LINEAR)
    mask=cv2.warpPerspective(np.full((ph,pw),255,np.uint8),matrix,(w,h))
    alpha=mask.astype(np.float32)[:,:,None]/255
    scene=np.uint8(scene*(1-alpha)+pixels*alpha)
    return scene,quad
