"""Whole-picture proposals against a smooth light screen background."""
from __future__ import annotations
import cv2
import numpy as np


def light_background(image):
    scale=min(1.,700/max(image.shape[:2]))
    small=cv2.resize(image,None,fx=scale,fy=scale)
    if np.mean(np.mean(small,axis=2)>150)<.55:return None
    h,w=small.shape[:2]
    smooth=cv2.GaussianBlur(small,(5,5),1.1).astype(np.float32)
    yy,xx=np.mgrid[:h,:w].astype(np.float32)
    xx=(xx-w/2)/w;yy=(yy-h/2)/h
    basis=np.stack([np.ones_like(xx),xx,yy,xx*xx,xx*yy,yy*yy],axis=-1)
    step=max(6,round(max(h,w)/60))
    coords=basis[::step,::step].reshape(-1,6)
    pixels=smooth[::step,::step].reshape(-1,3)
    keep=np.ones(len(coords),bool)
    for _ in range(5):
        params=np.linalg.lstsq(coords[keep],pixels[keep],rcond=None)[0]
        errors=np.linalg.norm(pixels-coords@params,axis=1)
        keep=errors<=np.percentile(errors,65)
    background=basis@params
    residual=np.linalg.norm(smooth-background,axis=2)
    if np.median(background)<155 or np.percentile(residual,65)>13:
        return None
    return small,scale,residual


def light_proposals(evidence,order_corners,*,square=False):
    small,scale,residual=evidence
    h,w=small.shape[:2]
    noise=float(np.percentile(residual,65))
    proposals=[];seen=set()
    for threshold,size in ((max(9.,noise*1.8),23),(max(15.,noise*2.6),29),(max(24.,noise*3.5),35),(max(24.,noise*3.5),65)):
        binary=np.uint8(residual>threshold)*255
        count,components,stats,_=cv2.connectedComponentsWithStats(binary,8)
        for i in range(1,count):
            x,y,bw,bh,area=stats[i]
            if x<3 or y<3 or x+bw>w-3 or y+bh>h-3:
                binary[components==i]=0
        binary=cv2.morphologyEx(binary,cv2.MORPH_CLOSE,np.ones((size,size),np.uint8))
        contours,_=cv2.findContours(binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours,key=cv2.contourArea,reverse=True)[:8]:
            if not .025*h*w<cv2.contourArea(contour)<.65*h*w:continue
            rect=cv2.minAreaRect(contour)
            q=order_corners(cv2.boxPoints(rect))
            if q[:,0].min()<12 or q[:,1].min()<12 or q[:,0].max()>w-12 or q[:,1].max()>h-12:continue
            edges=np.roll(q,-1,axis=0)-q;sides=np.linalg.norm(edges,axis=1)
            if sides.min()<65 or sides.max()/sides.min()>3.5:continue
            candidates=[q]
            # Sparse dark text needs a group envelope rather than a single glyph.
            x0,y0=np.maximum(np.floor(q.min(axis=0)).astype(int),0)
            x1,y1=np.minimum(np.ceil(q.max(axis=0)).astype(int),[w-1,h-1])
            region=residual[y0:y1+1,x0:x1+1]
            strong=region>max(28.,noise*4)
            if .025<float(strong.mean())<.30:
                ys,xs=np.where(strong)
                if len(xs)>100:
                    left,right=np.percentile(xs,[.5,99.5])+x0
                    top,bottom=np.percentile(ys,[.5,99.5])+y0
                    pad=max(2.,(right-left)*.015)
                    box=np.float32([[left-pad,top-pad],[right+pad,top-pad],[right+pad,bottom+pad],[left-pad,bottom+pad]])
                    candidates.append(box)
                    if square:
                        side=max(right-left,bottom-top)+2*pad
                        cx,cy=(left+right)/2,(top+bottom)/2
                        for v in (-.04,0.,.04):
                            center=np.float32([cx,cy+side*v])
                            candidates.append(center+np.float32([[-1,-1],[1,-1],[1,1],[-1,1]])*side/2)
            hull=cv2.convexHull(contour);perimeter=cv2.arcLength(hull,True)
            poly=cv2.approxPolyDP(hull,.025*perimeter,True)
            if len(poly)==4:candidates.append(order_corners(poly.reshape(4,2)))
            if square and sides.max()/sides.min()<1.8:
                # Complete a faint side using the user's square-picture prior.
                horizontal=edges[0]/sides[0];vertical=edges[1]/sides[1]
                if sides[0]<sides[1]:
                    gap=sides[1]-sides[0]
                    for fraction in (0.,.5,1.):
                        p=q.copy();p[[0,3]]-=horizontal*gap*fraction;p[[1,2]]+=horizontal*gap*(1-fraction)
                        candidates.append(p)
                else:
                    gap=sides[0]-sides[1]
                    for fraction in (0.,.5,1.):
                        p=q.copy();p[[0,1]]-=vertical*gap*fraction;p[[2,3]]+=vertical*gap*(1-fraction)
                        candidates.append(p)
            for p in candidates:
                key=tuple(np.round(p/3).astype(int).ravel())
                if key not in seen:proposals.append(np.float32(p/scale));seen.add(key)
    return proposals


def light_score(evidence,quad,*,square=False):
    small,scale,residual=evidence
    q=np.float32(quad)*scale
    h,w=small.shape[:2]
    if q[:,0].min()<0 or q[:,1].min()<0 or q[:,0].max()>=w or q[:,1].max()>=h:return None
    area=abs(cv2.contourArea(q))/(h*w)
    if not .035<area<.60:return None
    edges=np.roll(q,-1,axis=0)-q
    sides=np.linalg.norm(edges,axis=1)
    if sides.min()<65:return None
    normals=np.column_stack((-edges[:,1],edges[:,0]))/sides[:,None]
    t=np.linspace(.08,.92,72,dtype=np.float32)
    points=q[:,None,:]+t[None,:,None]*edges[:,None,:]
    before=points[None]-np.float32([4,9,16])[:,None,None,None]*normals[None,:,None,:]
    if before[...,0].min()<0 or before[...,1].min()<0 or before[...,0].max()>=w or before[...,1].max()>=h:return None
    def sample(image,pts):
        shape=pts.shape[:-1]
        return cv2.remap(image,np.float32(pts[...,0].reshape(-1,72)),np.float32(pts[...,1].reshape(-1,72)),
                         cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT).reshape(*shape,*image.shape[2:])
    outside=sample(residual,before)
    exterior=float(np.percentile(outside,85))
    if exterior>18:return None
    after=points+normals[:,None,:]*4
    contrast=np.linalg.norm(sample(small,after).astype(float)-sample(small,before[0]).astype(float),axis=2)
    edge_strength=np.percentile(contrast,60,axis=1)
    mask=np.zeros((h,w),np.uint8);cv2.fillConvexPoly(mask,np.int32(q),1)
    gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
    target=np.float32([[0,0],[63,0],[63,63],[0,63]])
    transform=cv2.getPerspectiveTransform(q,target)
    inside=cv2.warpPerspective(gray,transform,(64,64))[8:-8,8:-8].ravel()
    if len(inside)<100 or inside.std()<8 or np.percentile(inside,95)-np.percentile(inside,5)<20:return None
    foreground=float(np.mean(residual[mask>0]>24))
    if foreground<.025:return None
    coverage=float(np.mean(edge_strength>8))
    if coverage<.5:return None
    aspect=abs(np.log((sides[0]+sides[2])/(sides[1]+sides[3])))
    score=1.1*np.mean(np.minimum(edge_strength/40,1))-.50*np.log1p(exterior)+.25*foreground
    if square:score-=1.8*aspect
    return float(score),dict(exterior=exterior,edge_strength=edge_strength.tolist(),foreground=foreground,area=area)


def detect_light_picture(image,order_corners,*,square=False):
    evidence=light_background(image)
    if evidence is None:return None
    ranked=[]
    for quad in light_proposals(evidence,order_corners,square=square):
        result=light_score(evidence,quad,square=square)
        if result is not None:ranked.append((result[0],quad,result[1]))
    if not ranked:return None
    ranked.sort(key=lambda r:-r[0])
    if ranked[0][0]<-.72:return None
    # Similar proposals for the same picture are normal. Separate comparable
    # pictures are ambiguous and should use the general detector/review path.
    best=ranked[0]
    for other in ranked[1:]:
        if other[0]<best[0]-.18:break
        intersection,_=cv2.intersectConvexConvex(np.float32(best[1]),np.float32(other[1]))
        if intersection<.2*min(abs(cv2.contourArea(best[1])),abs(cv2.contourArea(other[1]))):
            return None
    return best,evidence
