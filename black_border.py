"""Propose the four dark borders of a picture on a lighter screen for review."""
from __future__ import annotations

from itertools import combinations

import cv2
import numpy as np


def merged_lines(gray, detected, *, horizontal):
    """Join collinear border fragments while retaining their observed extent."""
    height, width = gray.shape
    center = width/2 if horizontal else height/2
    segments = []
    for raw in detected.reshape(-1,4):
        points = raw.reshape(2,2).astype(float)
        delta = points[1]-points[0]
        length = np.linalg.norm(delta)
        if length < max(16, max(gray.shape)*.018):
            continue
        if (abs(delta[0]) >= abs(delta[1])) != horizontal:
            continue
        if not horizontal:
            points = points[:,::-1]
        slope = (points[1,1]-points[0,1])/(points[1,0]-points[0,0])
        position = points[0,1]+slope*(center-points[0,0])
        segments.append((length, slope, position, points))
    groups = []
    for length, slope, position, points in sorted(segments,key=lambda row:-row[0]):
        group = next((g for g in groups if abs(np.arctan(g['slope'])-np.arctan(slope)) < .035
                      and abs(g['position']-position) < 3),None)
        if group is None:
            group = dict(slope=slope,position=position,segments=[])
            groups.append(group)
        group['segments'].append((length,points))
    result = []
    for group in groups:
        points = np.concatenate([p for _,p in group['segments']])
        weights = np.repeat([length for length,_ in group['segments']],2)
        design = np.column_stack((points[:,0]-center,np.ones(len(points))))
        slope, position = np.linalg.lstsq(design*np.sqrt(weights[:,None]),
                                         points[:,1]*np.sqrt(weights),rcond=None)[0]
        intervals = sorted((float(p[:,0].min()),float(p[:,0].max())) for _,p in group['segments'])
        covered = 0.
        end = -np.inf
        for left,right in intervals:
            covered += max(0.,right-max(left,end))
            end = max(end,right)
        if covered < max(42,max(gray.shape)*.05):
            continue
        result.append(dict(slope=slope,intercept=position-slope*center,position=position,
                           low=points[:,0].min(),high=points[:,0].max(),covered=covered))
    return sorted(result,key=lambda line:-line['covered'])[:24]


def component_frames(gray):
    """Keep closed dark outlines even when blur fragments their line segments."""
    height,width=gray.shape
    proposals=[]
    for threshold in (30,65,100,135):
        binary=np.uint8(gray<threshold)*255
        binary=cv2.morphologyEx(binary,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        _,labels,stats,_=cv2.connectedComponentsWithStats(binary,8)
        x,y,w,h,_=stats.T
        discard=(x<5)|(y<5)|(x+w>width-5)|(y+h>height-5)
        binary[discard[labels]]=0
        contours,_=cv2.findContours(binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours,key=cv2.contourArea,reverse=True)[:8]:
            hull=cv2.convexHull(contour)
            if not .012*gray.size<cv2.contourArea(hull)<.6*gray.size:
                continue
            poly=cv2.approxPolyDP(hull,.018*cv2.arcLength(hull,True),True)
            if len(poly)!=4:
                continue
            points=poly.reshape(4,2).astype(np.float32)
            center=points.mean(axis=0)
            points=points[np.argsort(np.arctan2(points[:,1]-center[1],points[:,0]-center[0]))]
            points=np.roll(points,-np.argmin(points.sum(axis=1)),axis=0)
            sides=np.linalg.norm(np.roll(points,-1,axis=0)-points,axis=1)
            if sides.min()>42 and sides.max()<sides.min()*5:
                proposals.append(points)
    return proposals


def frame_proposals(gray):
    """Intersect two horizontal and two vertical line groups in bounded batches."""
    height,width = gray.shape
    detected = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(gray)[0]
    if detected is None:
        return component_frames(gray)
    horizontal = merged_lines(gray,detected,horizontal=True)
    vertical = merged_lines(gray,detected,horizontal=False)
    def pairs(lines):
        return [(a,b) if a['position']<b['position'] else (b,a)
                for a,b in combinations(lines,2)
                if abs(a['position']-b['position'])>max(42,max(gray.shape)*.05)
                and abs(np.arctan(a['slope'])-np.arctan(b['slope']))<.25]
    hpairs, vpairs = pairs(horizontal), pairs(vertical)
    if not hpairs or not vpairs:
        return component_frames(gray)
    vl,vr = (np.array([[pair[i][key] for key in ('slope','intercept','low','high')]
                       for pair in vpairs]) for i in (0,1))
    def intersection(h,v):
        denominator = 1-h['slope']*v[:,0]
        x = (v[:,0]*h['intercept']+v[:,1])/np.where(abs(denominator)>.05,denominator,np.nan)
        return np.column_stack((x,h['slope']*x+h['intercept']))
    def coverage(low,high,start,end):
        left,right = np.minimum(start,end),np.maximum(start,end)
        return np.maximum(0,np.minimum(high,right)-np.maximum(low,left))/np.maximum(1,right-left)
    proposals = []
    seen = set()
    for top,bottom in hpairs:
        quads = np.stack((intersection(top,vl),intersection(top,vr),
                          intersection(bottom,vr),intersection(bottom,vl)),axis=1)
        edges = np.roll(quads,-1,axis=1)-quads
        sides = np.linalg.norm(edges,axis=2)
        crosses = edges[:,:,0]*np.roll(edges[:,:,1],-1,axis=1)-edges[:,:,1]*np.roll(edges[:,:,0],-1,axis=1)
        area = .5*np.abs(np.sum(quads[:,:,0]*np.roll(quads[:,:,1],-1,axis=1)
                              -quads[:,:,1]*np.roll(quads[:,:,0],-1,axis=1),axis=1))
        support = np.stack((coverage(top['low'],top['high'],quads[:,0,0],quads[:,1,0]),
                            coverage(vr[:,2],vr[:,3],quads[:,1,1],quads[:,2,1]),
                            coverage(bottom['low'],bottom['high'],quads[:,2,0],quads[:,3,0]),
                            coverage(vl[:,2],vl[:,3],quads[:,3,1],quads[:,0,1])),axis=1)
        valid = (np.isfinite(quads).all(axis=(1,2)) & (crosses>0).all(axis=1)
                 & (quads[:,:,0].min(axis=1)>8) & (quads[:,:,0].max(axis=1)<width-8)
                 & (quads[:,:,1].min(axis=1)>8) & (quads[:,:,1].max(axis=1)<height-8)
                 & (sides.min(axis=1)>42) & (sides.max(axis=1)<sides.min(axis=1)*5)
                 & (area>gray.size*.012) & (area<gray.size*.60) & (support.min(axis=1)>.64))
        selected=quads[valid]
        quality=support[valid].mean(axis=1)
        if len(selected):
            plausible=coarse_frame_mask(gray,selected)
            selected,quality=selected[plausible],quality[plausible]
        for q,quality in zip(selected,quality):
            key = tuple(np.round(q/3).astype(int).ravel())
            if key not in seen:
                seen.add(key)
                proposals.append((float(quality),np.float32(q)))
    return [q for _,q in sorted(proposals,key=lambda item:-item[0])[:180]]+component_frames(gray)


def coarse_frame_mask(gray,quads):
    """Reject interior/outer-bezel line combinations before the proposal cap."""
    edges=np.roll(quads,-1,axis=1)-quads
    sides=np.linalg.norm(edges,axis=2)
    normals=np.stack((-edges[:,:,1],edges[:,:,0]),axis=2)/sides[:,:,None]
    t=np.linspace(.08,.92,16,dtype=np.float32)
    points=quads[:,:,None,:]+t[None,None,:,None]*edges[:,:,None,:]
    locations=points[None]+np.float32([-8,-4,-1,1,3])[:,None,None,None,None]*normals[None,:,:,None,:]
    values=cv2.remap(gray,np.float32(locations[...,0].reshape(-1,16)),
                     np.float32(locations[...,1].reshape(-1,16)),cv2.INTER_LINEAR).reshape(5,len(quads),4,16).astype(float)
    exterior=np.median(values[:2],axis=0)
    contrast=exterior-values[2:].min(axis=0)
    return (np.mean(contrast>5,axis=2).min(axis=1)>.5)&(np.percentile(exterior,25,axis=2).min(axis=1)>75)


def frame_score(gray,quad,*,square=False):
    """Require a continuous dark edge and a smooth, brighter exterior on all sides."""
    q = np.float32(quad)
    edges = np.roll(q,-1,axis=0)-q
    sides = np.linalg.norm(edges,axis=1)
    normals = np.column_stack((-edges[:,1],edges[:,0]))/sides[:,None]
    t = np.linspace(.06,.94,96,dtype=np.float32)
    points = q[:,None,:]+t[None,:,None]*edges[:,None,:]
    offsets = np.float32([-10,-6,-3,-1,0,1,2,3])
    locations = points[None]+offsets[:,None,None,None]*normals[None,:,None,:]
    height,width = gray.shape
    if locations[...,0].min()<0 or locations[...,1].min()<0 or locations[...,0].max()>=width or locations[...,1].max()>=height:
        return None
    values = cv2.remap(gray,np.float32(locations[...,0].reshape(-1,96)),
                       np.float32(locations[...,1].reshape(-1,96)),cv2.INTER_LINEAR).reshape(len(offsets),4,96).astype(float)
    exterior = np.median(values[:3],axis=0)
    border = values[3:].min(axis=0)
    contrast = exterior-border
    noise = np.median(abs(exterior-np.median(exterior,axis=1)[:,None]),axis=1)
    support = np.mean(contrast>np.maximum(6.,noise[:,None]*1.8),axis=1)
    if support.min()<.64 or np.percentile(exterior,25)<85 or noise.max()>18:
        return None
    strength = np.percentile(contrast,35,axis=1)
    if strength.min()<7:
        return None
    score = float(support.mean()+np.mean(np.minimum(strength/50,1))-.012*noise.mean())
    if square:
        score -= .2*abs(np.log((sides[0]+sides[2])/(sides[1]+sides[3])))
    return float(score)


def inset_border(gray,quad):
    """Use a thin dark valley's inside edge; leave dark photo content intact."""
    offsets=np.arange(-3,10.5,.5,dtype=np.float32)
    t=np.linspace(.1,.9,96,dtype=np.float32)
    lines=[]
    for start,end in zip(quad,np.roll(quad,-1,axis=0)):
        direction=end-start
        normal=np.float32([-direction[1],direction[0]])/np.linalg.norm(direction)
        points=start+t[:,None]*direction
        locations=points[None]+offsets[:,None,None]*normal
        values=cv2.remap(gray,np.float32(locations[:,:,0]),np.float32(locations[:,:,1]),cv2.INTER_LINEAR)
        profile=np.median(values,axis=1)
        low=int(np.argmin(profile[(offsets>=0)&(offsets<=6)]))+int(np.flatnonzero(offsets>=0)[0])
        exterior=float(np.median(profile[offsets<-1]))
        depth=exterior-float(profile[low])
        distance=.8
        if depth>8:
            recovered=np.flatnonzero((np.arange(len(offsets))>low)&(profile>=profile[low]+.75*depth))
            if len(recovered) and offsets[recovered[0]]<=6:
                distance=max(.8,min(2.,float(offsets[recovered[0]])))
        lines.append((start+normal*distance,direction))
    corners=[]
    for i in range(4):
        a,u=lines[i-1];b,v=lines[i]
        distance=np.linalg.solve(np.column_stack((u,-v)),b-a)[0]
        corners.append(a+distance*u)
    return np.float32(corners)


def detect_black_frame(image,order_corners,*,square=False):
    """Return one conservative proposal in original pixels, or None for manual input.

    This detector does not trim dark rows/columns inside photographic content.
    The owning workflow must ask the user to confirm the proposal before saving.
    """
    if image.ndim!=3 or image.shape[2]!=3 or min(image.shape[:2])<64:
        return None
    scale = min(1.,1100/max(image.shape[:2]))
    small = cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(cv2.cvtColor(small,cv2.COLOR_BGR2GRAY),(3,3),.6)
    ranked = []
    for quad in frame_proposals(gray):
        score = frame_score(gray,quad,square=False)
        if score is not None:
            sides=np.linalg.norm(np.roll(quad,-1,axis=0)-quad,axis=1)
            aspect=abs(np.log((sides[0]+sides[2])/(sides[1]+sides[3])))
            area=abs(cv2.contourArea(quad))/gray.size
            # An internal table cell can have stronger edges than the complete
            # picture. Prefer an enclosing frame, using the square prior only
            # when the user selected an originally square target.
            score += (.6 if square else .08)*np.log(area)
            if square:score -= .6*aspect
            ranked.append((score,quad))
    if not ranked:
        return None
    ranked.sort(key=lambda row:-row[0])
    score,quad = ranked[0]
    for other_score,other_quad in ranked[1:]:
        if other_score<score-.12:
            break
        intersection,_ = cv2.intersectConvexConvex(quad,other_quad)
        if intersection<.2*min(abs(cv2.contourArea(quad)),abs(cv2.contourArea(other_quad))):
            return None
    return order_corners(inset_border(gray,quad)/scale)
