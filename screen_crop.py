#!/usr/bin/env python3
"""Batch perspective correction and black-margin trimming for screen photos."""

from __future__ import annotations

import argparse
import csv
import gzip
from functools import lru_cache
import shutil
import sys
from pathlib import Path

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
except ImportError as exc:
    raise SystemExit(
        f"Missing dependency: {exc.name}. Run: python -m pip install -r requirements.txt"
    ) from exc


__version__ = "0.1.0"

EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SUCCESS_FOLDER = "裁剪成功"
FAILURE_FOLDER = "裁剪失败"


def check_model_runtime() -> None:
    if not callable(getattr(getattr(cv2, "ml", None), "RTrees_create", None)):
        raise ValueError(
            f"当前 Python 的 OpenCV {getattr(cv2, '__version__', '未知版本')} "
            "缺少 ml.RTrees_create，无法加载识别模型。\n"
            f"Python：{sys.executable}\n"
            "请使用工具文件夹内的“启动裁剪.cmd”，或用 .crop-env\\Scripts\\python.exe 运行。\n"
            "若尚未安装独立环境，请按照使用说明安装 OpenCV 4.x。"
        )


def load_image(path: Path) -> np.ndarray:
    # Pillow handles Unicode paths and phone-camera orientation metadata.
    with Image.open(path) as source:
        rgb = np.array(ImageOps.exif_transpose(source).convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def order_corners(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float32).reshape(4, 2)
    hull = cv2.convexHull(points).reshape(-1, 2)
    if len(hull) != 4 or abs(cv2.contourArea(hull)) < 16:
        raise ValueError("Select four distinct corners of a convex image region.")
    # Cyclic ordering avoids duplicate corners on strongly rotated rectangles.
    center = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    ordered = points[np.argsort(angles)]
    return np.roll(ordered, -int(np.argmin(ordered.sum(axis=1))), axis=0)


def fit_border_lines(contour: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Fit the middle of each border; corner handles should not define the crop."""
    points = contour.reshape(-1, 2).astype(np.float32)
    lengths = np.linalg.norm(np.roll(corners, -1, axis=0) - corners, axis=1)
    lines = []
    for i in range(4):
        start, end = corners[i], corners[(i + 1) % 4]
        delta = end - start
        offset = points - start
        position = offset @ delta / float(delta @ delta)
        distance = np.abs(offset[:, 0] * delta[1] - offset[:, 1] * delta[0]) / lengths[i]
        support = points[(position > 0.15) & (position < 0.85)
                         & (distance < max(3, lengths.min() * 0.06))]
        if len(support) < 5:
            lines.append((start, delta))
        else:
            vx, vy, x, y = cv2.fitLine(support, cv2.DIST_WELSCH, 0, 0.01, 0.01).ravel()
            lines.append((np.array([x, y]), np.array([vx, vy])))
    result = []
    for i in range(4):
        a, u = lines[(i - 1) % 4]
        b, v = lines[i]
        matrix = np.column_stack((u, -v))
        if abs(np.linalg.det(matrix)) < 1e-6:
            return corners
        t = np.linalg.solve(matrix, b - a)[0]
        result.append(a + t * u)
    result = np.float32(result)
    if np.max(np.linalg.norm(result - corners, axis=1)) > lengths.min() * 0.12:
        return corners
    if not cv2.isContourConvex(result.reshape(-1, 1, 2)):
        return corners
    return result


FEATURE_NAMES = [
    'center', 'log_area', 'aspect', 'rectangularity', 'color_inside',
    'color_outside', 'brightness_difference', 'inside_std', 'outside_std',
    'texture_inside', 'texture_outside', 'texture_ratio', 'edge_mean',
    'edge_min', 'edge_coverage', 'border_difference_mean', 'border_difference_min',
    'outer_smoothness', 'saturation_std', 'interior_dynamic_range',
    'side_balance', 'outside_dark', 'inside_dark', 'edge_brightness_change',
]


def detection_image(image):
    """Remove only detected sparse annotation components from detection evidence."""
    scale = min(1., 1400. / max(image.shape[:2]))
    small = cv2.resize(image, None, fx=scale, fy=scale)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    yellow = ((hsv[:, :, 0] >= 24) & (hsv[:, :, 0] <= 35)
              & (hsv[:, :, 1] > 210) & (hsv[:, :, 2] > 225)).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(yellow, 8)
    mask = np.zeros_like(yellow)
    for i in range(1, n):
        _, _, w, h, area = stats[i]
        if min(w, h) >= 20 and area >= 100 and area / (w * h) < .3:
            mask[labels == i] = 1
    if mask.any():
        for i in range(1, n):
            _, _, w, h, area = stats[i]
            if 8 <= area and area / (w * h) < .6:
                mask[labels == i] = 1
        mask = cv2.dilate(mask, np.ones((7, 7), np.uint8))
        small = cv2.inpaint(small, mask * 255, 5, cv2.INPAINT_TELEA)
    return small, scale


def quad_features(small, gray, saturation, texture, gradients, q):
    h, w = gray.shape
    sides = np.linalg.norm(np.roll(q, -1, axis=0) - q, axis=1)
    area = abs(cv2.contourArea(q)) / (w * h)
    center = 1 - np.linalg.norm(q.mean(axis=0) - [w/2, h/2]) / np.hypot(w/2,h/2)
    angles = []
    for i in range(4):
        a, b = q[(i-1)%4]-q[i], q[(i+1)%4]-q[i]
        angles.append(abs(float(a@b)) / (np.linalg.norm(a)*np.linalg.norm(b)))
    if max(angles) > .88:
        return None
    matrix = cv2.getPerspectiveTransform(q, np.float32([[0,0],[63,0],[63,63],[0,63]]))
    inside = cv2.warpPerspective(small, matrix, (64,64))[3:-3,3:-3]
    ins_gray = cv2.cvtColor(inside,cv2.COLOR_BGR2GRAY)
    ins_hsv = cv2.cvtColor(inside,cv2.COLOR_BGR2HSV)
    ins_color = (ins_hsv[:,:,1]>55)&(ins_hsv[:,:,2]>50)
    if ins_color.mean() < .035:
        return None
    t = np.linspace(.10,.90,40,dtype=np.float32)
    outer=[]; inner=[]; gvals=[]; contrasts=[]; cover=[]
    distance = max(3., min(12., sides.min()*.035))
    for i in range(4):
        a,b=q[i],q[(i+1)%4]
        delta=b-a
        normal=np.float32([-delta[1],delta[0]]) / np.linalg.norm(delta)
        points=a[None,:]+t[:,None]*delta[None,:]
        # Cyclic corners have inward-pointing left normals in image coordinates.
        pin=points+normal*distance
        pout=points-normal*distance
        def sample(arr, pts):
            return cv2.remap(arr,pts[:,0].reshape(1,-1),pts[:,1].reshape(1,-1),
                             cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT).reshape(-1,*arr.shape[2:])
        outside_pixels=sample(small,pout)
        inside_pixels=sample(small,pin)
        outer.append(outside_pixels)
        inner.append(inside_pixels)
        values=[]
        for d in (-2.,0.,2.):
            values.append(sample(gradients,points+normal*d))
        edge=np.max(values,axis=0)
        gvals.append(float(np.median(edge)))
        cover.append(float(np.mean(edge>12)))
        contrasts.append(float(np.median(np.linalg.norm(inside_pixels.astype(float)-outside_pixels.astype(float),axis=1)))/441.)
    outer=np.concatenate(outer).reshape(4,40,3)
    out_hsv=cv2.cvtColor(outer,cv2.COLOR_BGR2HSV)
    out_gray=cv2.cvtColor(outer,cv2.COLOR_BGR2GRAY)
    ins_tex=cv2.warpPerspective(texture,matrix,(64,64))[3:-3,3:-3]
    # Texture in a 1.2x wider quad tests whether the rectangle isolates a photo
    # from a flat viewer background instead of selecting a part inside the photo.
    outer_tex=[]
    for i in range(4):
        a,b=q[i],q[(i+1)%4];delta=b-a
        normal=np.float32([-delta[1],delta[0]])/np.linalg.norm(delta)
        pts=a+t[:,None]*delta-normal*distance
        outer_tex.extend(cv2.remap(texture,pts[:,0].reshape(1,-1),pts[:,1].reshape(1,-1),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT).ravel())
    it=float(np.mean(ins_tex));ot=float(np.mean(outer_tex))
    return np.float32([
        center,np.log(max(area,1e-6)),np.log(sides.max()/sides.min()),1-np.mean(angles),
        ins_color.mean(),np.mean((out_hsv[:,:,1]>55)&(out_hsv[:,:,2]>50)),
        abs(float(ins_gray.mean())-float(out_gray.mean()))/255,
        ins_gray.std()/128,out_gray.std()/128,it/40,ot/40,np.log((it+1)/(ot+1)),
        np.mean(gvals)/100,min(gvals)/100,np.mean(cover),np.mean(contrasts),min(contrasts),
        np.mean([np.std(row) for row in out_gray])/128,ins_hsv[:,:,1].std()/128,
        (np.percentile(ins_gray,90)-np.percentile(ins_gray,10))/255,
        abs(sides[0]-sides[2])/max(sides[0],sides[2])+abs(sides[1]-sides[3])/max(sides[1],sides[3]),
        np.mean(out_gray<60),np.mean(ins_gray<50),
        np.mean(np.abs(np.concatenate(inner).astype(float)-outer.reshape(-1,3)))/255])


def photo_candidates(image):
    small,scale=detection_image(image)
    gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
    gray=cv2.GaussianBlur(gray,(5,5),0)
    hsv=cv2.cvtColor(small,cv2.COLOR_BGR2HSV)
    h,w=gray.shape
    g=gray.astype(np.float32)
    mean=cv2.boxFilter(g,-1,(11,11))
    texture=np.sqrt(np.maximum(cv2.boxFilter(g*g,-1,(11,11))-mean*mean,0))
    gx=cv2.Sobel(g,cv2.CV_32F,1,0,ksize=3)
    gy=cv2.Sobel(g,cv2.CV_32F,0,1,ksize=3)
    gradients=cv2.magnitude(gx,gy)
    color=(((hsv[:,:,1]>60)&(hsv[:,:,2]>50)).astype(np.uint8)*255)
    masks=[]
    close=lambda m,k:cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((k,k),np.uint8))
    masks += [close(color,5),close(color,15)]
    enhanced=cv2.createCLAHE(clipLimit=2.5,tileGridSize=(12,12)).apply(gray)
    for source in (gray,enhanced):
        for lo,hi in ((15,45),(35,100)):
            masks.append(close(cv2.Canny(source,lo,hi),5))
        for threshold in (25,45,65,85,110,145,180):
            binary=np.uint8(source>threshold)*255
            masks.append(close(binary,7))
            masks.append(close(255-binary,7))
            combined=cv2.bitwise_or(255-binary,color)
            combined=cv2.morphologyEx(combined,cv2.MORPH_OPEN,np.ones((5,5),np.uint8))
            masks.append(close(combined,9))
    for level in (3,6,10):
        m=np.uint8(texture>level)*255
        masks.append(close(m,11))
        masks.append(close(m,21))
    candidates=[];seen=set()
    for binary in masks:
        contours,_=cv2.findContours(binary,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours,key=cv2.contourArea,reverse=True)[:90]:
            area=abs(cv2.contourArea(contour))
            if not .0006*w*h <= area <= .88*w*h:continue
            hull=cv2.convexHull(contour)
            perimeter=cv2.arcLength(hull,True)
            quads=[]
            for eps in (.015,.03,.055):
                p=cv2.approxPolyDP(hull,eps*perimeter,True)
                if len(p)==4:quads.append(p.reshape(4,2))
            rect=cv2.minAreaRect(hull)
            ra=rect[1][0]*rect[1][1]
            if ra>0 and cv2.contourArea(hull)/ra > .60:
                quads.append(cv2.boxPoints(rect))
            for p in quads:
                try:q=order_corners(p)
                except ValueError:continue
                sides=np.linalg.norm(np.roll(q,-1,axis=0)-q,axis=1)
                if sides.min()<22 or sides.max()/sides.min()>9:continue
                if q[:,0].min()<3 or q[:,1].min()<3 or q[:,0].max()>w-4 or q[:,1].max()>h-4:continue
                key=tuple(np.round(q/5).astype(int).ravel())
                if key in seen:continue
                seen.add(key)
                features=quad_features(small,gray,hsv[:,:,1],texture,gradients,q)
                if features is not None:candidates.append((q/scale,features))
    # A bright reflection may merge one side into the viewer background. Complete
    # partial rectangles by extending one side along its two adjacent edges.
    # Proposals are generated without target coordinates or a fixed aspect ratio.
    ranked=sorted(candidates,key=lambda c:float(c[1][11]+c[1][7]-c[1][8]+c[1][12]),reverse=True)
    seeds=[]
    for q,f in ranked:
        sides=np.linalg.norm(np.roll(q,-1,axis=0)-q,axis=1)
        if sides.min()*scale<35 or f[1]<np.log(.002):continue
        if any(np.mean(np.linalg.norm(q-p,axis=1))<sides.min()*.08 for p in seeds):continue
        seeds.append(q)
        if len(seeds)>=40:break
    for original in seeds:
        for side in range(4):
            for fraction in (.08,.16,.24,.36):
                q=original.copy()*scale
                i,j=side,(side+1)%4
                q[i]+=fraction*(q[i]-q[(i-1)%4])
                q[j]+=fraction*(q[j]-q[(j+1)%4])
                if q[:,0].min()<3 or q[:,1].min()<3 or q[:,0].max()>w-4 or q[:,1].max()>h-4:continue
                key=tuple(np.round(q/5).astype(int).ravel())
                if key in seen:continue
                seen.add(key)
                features=quad_features(small,gray,hsv[:,:,1],texture,gradients,q)
                if features is not None:candidates.append((q/scale,features))
    return candidates


def refine_photo_edges(image, quad):
    """Snap nearby sides to a consistently supported border, including dim edges."""
    small,scale=detection_image(image)
    gray=cv2.GaussianBlur(cv2.cvtColor(small,cv2.COLOR_BGR2GRAY),(5,5),0).astype(np.float32)
    q=quad*scale
    sides=np.linalg.norm(np.roll(q,-1,axis=0)-q,axis=1)
    radius=min(24.,max(5.,float(sides.min())*.10))
    positions=np.linspace(.12,.88,48,dtype=np.float32)
    lines=[]
    for i in range(4):
        a,b=q[i],q[(i+1)%4];delta=b-a
        normal=np.float32([-delta[1],delta[0]])/np.linalg.norm(delta)
        points=a+positions[:,None]*delta
        options=[];offsets=[]
        for shift in np.linspace(-radius,radius,25):
            for tilt in np.linspace(-radius*.6,radius*.6,7):
                move=shift+(positions-.5)*2*tilt
                options.append(points+move[:,None]*normal)
                offsets.append((shift,tilt))
        pts=np.float32(options)
        before=pts-normal*3
        after=pts+normal*3
        low=cv2.remap(gray,before[:,:,0],before[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
        high=cv2.remap(gray,after[:,:,0],after[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
        differences=high-low
        strength=np.abs(np.median(differences,axis=1))
        proximity=np.array([abs(s)+abs(t) for s,t in offsets])
        score=strength-.12*proximity
        index=int(score.argmax())
        shift,tilt=offsets[index]
        if strength[index]<7:
            shift=tilt=0.
        aa=a+(shift-tilt)*normal
        bb=b+(shift+tilt)*normal
        lines.append((aa,bb-aa))
    result=[]
    for i in range(4):
        a,u=lines[(i-1)%4];b,v=lines[i]
        matrix=np.column_stack((u,-v))
        if abs(np.linalg.det(matrix))<1e-6:return quad
        result.append(a+np.linalg.solve(matrix,b-a)[0]*u)
    result=np.float32(result)
    if not cv2.isContourConvex(result.reshape(-1,1,2)):return quad
    if np.max(np.linalg.norm(result-q,axis=1))>radius*1.8:return quad
    if result[:,0].min()<0 or result[:,1].min()<0 or result[:,0].max()>=small.shape[1] or result[:,1].max()>=small.shape[0]:return quad
    # Avoid a one-pixel interpolated screen fringe without trimming dark rows.
    edges=np.roll(result,-1,axis=0)-result
    normals=np.column_stack((-edges[:,1],edges[:,0]))/np.linalg.norm(edges,axis=1)[:,None]
    inset=min(2.,max(.5,float(sides.min())*.005))
    result += np.float32([np.linalg.solve(np.vstack((normals[(i-1)%4],normals[i])),[inset,inset]) for i in range(4)])
    return result/scale


@lru_cache(maxsize=1)
def load_scoring_forest(path, modified_ns):
    check_model_runtime()
    # Python handles Unicode folder names; OpenCV parses the model from memory.
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        serialized=stream.read()
    storage=cv2.FileStorage(serialized,cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
    try:
        forest=cv2.ml.RTrees_create()
        forest.read(storage.getFirstTopLevelNode())
    finally:
        storage.release()
    return forest


def detect_screen(image: np.ndarray) -> np.ndarray | None:
    import json
    candidates=photo_candidates(image)
    if not candidates:return None
    path=Path(__file__).with_name('screen_crop_model.json')
    if not path.exists():
        raise ValueError('Missing screen_crop_model.json. Keep the model beside screen_crop.py.')
    model=json.loads(path.read_text(encoding='utf-8'))
    if model['features'] != FEATURE_NAMES:
        raise ValueError('Model version mismatch. Extract all files from the same release.')
    X=np.array([f for _,f in candidates])
    forest_path=Path(__file__).with_name('screen_crop_forest.xml.gz')
    if not forest_path.exists():
        raise ValueError('Missing screen_crop_forest.xml.gz. Extract all release files together.')
    forest=load_scoring_forest(str(forest_path),forest_path.stat().st_mtime_ns)
    scores=forest.predict(X.astype(np.float32))[1].ravel()
    if float(scores.max()) < .4:
        return None
    best=candidates[int(np.argmax(scores))][0]
    return refine_photo_edges(image,np.float32(best))


def rectify(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = order_corners(corners)
    width = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    height = int(round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))))
    if min(width, height) < 8:
        raise ValueError("Selected image region is too small.")
    target = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    matrix = cv2.getPerspectiveTransform(np.float32([tl, tr, br, bl]), target)
    return cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)


def trim_black(image: np.ndarray, threshold: int, max_trim: float) -> np.ndarray:
    height, width = image.shape[:2]
    top, bottom, left, right = 0, height, 0, width
    # Recompute on the current rectangle: side bars must not hide the end of top bars.
    dark = np.max(image, axis=2) <= threshold
    for _ in range(3):
        while top < int(height * max_trim) and np.mean(dark[top, left:right]) >= 0.90:
            top += 1
        while height - bottom < int(height * max_trim) and np.mean(dark[bottom - 1, left:right]) >= 0.90:
            bottom -= 1
        while left < int(width * max_trim) and np.mean(dark[top:bottom, left]) >= 0.90:
            left += 1
        while width - right < int(width * max_trim) and np.mean(dark[top:bottom, right - 1]) >= 0.90:
            right -= 1
    return image[top:bottom, left:right]


def finish_crop(image: np.ndarray, args: argparse.Namespace) -> np.ndarray:
    if not args.no_trim_black:
        image = trim_black(image, args.black_threshold, args.max_trim)
    h, w = image.shape[:2]
    # A small inset removes edge interpolation and thin remnants of the bezel.
    dx, dy = round(w * args.inset), round(h * args.inset)
    return image[dy:h - dy, dx:w - dx].copy()


def choose_corners(image: np.ndarray, proposed: np.ndarray | None, title: str) -> np.ndarray | None:
    scale = min(1.0, 1200 / image.shape[1], 760 / image.shape[0])
    preview = cv2.resize(image, None, fx=scale, fy=scale)
    selected = []
    active_proposal = proposed
    header_height = 104
    window = "Screen crop - " + title.encode("ascii", "replace").decode("ascii")
    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)

    def mouse(event, x, y, flags, userdata):
        nonlocal active_proposal
        if event == cv2.EVENT_LBUTTONDOWN and 8 <= x <= 208 and 70 <= y <= 98:
            selected.clear()
            active_proposal = None
            return
        y -= header_height
        if not (0 <= x < preview.shape[1] and 0 <= y < preview.shape[0]):
            return
        if event == cv2.EVENT_LBUTTONDOWN and len(selected) < 4:
            selected.append((x, y))
        elif event == cv2.EVENT_RBUTTONDOWN and selected:
            selected.pop()

    cv2.setMouseCallback(window, mouse)
    try:
        while True:
            canvas = preview.copy()
            if active_proposal is not None and not selected:
                polygon = np.round(active_proposal * scale).astype(np.int32)
                cv2.polylines(canvas, [polygon], True, (0, 255, 0), 2)
            for i, point in enumerate(selected):
                cv2.circle(canvas, point, 5, (0, 255, 255), -1)
                cv2.putText(canvas, str(i + 1), (point[0] + 7, point[1] - 7),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            if len(selected) > 1:
                cv2.polylines(canvas, [np.array(selected, np.int32)], len(selected) == 4, (0, 255, 255), 2)
            canvas = cv2.copyMakeBorder(canvas, header_height, 0, 0, max(0, 680 - canvas.shape[1]),
                                        cv2.BORDER_CONSTANT, value=(25, 25, 25))
            cv2.putText(canvas, "Click 4 corners in order; Enter: preview; R: reset; Esc: skip",
                        (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (255, 255, 255), 1)
            cv2.putText(canvas, "Right click: undo. Choose the picture itself, inside the screen.",
                        (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (255, 255, 255), 1)
            cv2.rectangle(canvas, (8, 70), (208, 98), (75, 75, 75), -1)
            cv2.putText(canvas, "Re-crop (R)", (24, 90), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, (255, 255, 255), 1)
            cv2.imshow(window, canvas)
            key = cv2.waitKey(30) & 0xFF
            if key == 27 or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                return None
            if key in (ord("r"), ord("R")):
                selected.clear()
                active_proposal = None
            if key in (10, 13):
                if len(selected) == 4:
                    try:
                        return order_corners(np.float32(selected) / scale)
                    except ValueError:
                        selected.clear()
                elif not selected and active_proposal is not None:
                    return active_proposal
    finally:
        cv2.destroyWindow(window)


def preview_crop(cropped: np.ndarray, title: str) -> str:
    """Confirm a crop before advancing; re-crop always returns to the source image."""
    import tkinter as tk
    from tkinter import ttk
    from PIL import ImageTk

    root = tk.Tk()
    root.title("裁剪预览 / Crop preview - " + title)
    root.resizable(False, False)
    action = "skip"

    def decide(value: str) -> None:
        nonlocal action
        action = value
        root.quit()

    try:
        preview = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        max_width = max(160, min(1200, root.winfo_screenwidth() - 100))
        max_height = max(120, min(760, root.winfo_screenheight() - 240))
        preview.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(preview, master=root)
        ttk.Label(root, text="检查当前图片，确认保存后进入下一张 / Review before saving and advancing",
                  padding=10).pack()
        ttk.Label(root, image=photo).pack(padx=12)
        ttk.Label(root, text=f"{cropped.shape[1]} × {cropped.shape[0]} px", padding=6).pack()
        buttons = ttk.Frame(root, padding=12)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="重新裁剪 / Re-crop (R)",
                   command=lambda: decide("recrop")).pack(side="left", padx=5)
        ttk.Button(buttons, text="跳过 / Skip (Esc)",
                   command=lambda: decide("skip")).pack(side="left", padx=5)
        save = ttk.Button(buttons, text="保存并下一张 / Save & next (Enter)",
                          command=lambda: decide("save"))
        save.pack(side="left", padx=5)
        root.bind("<Return>", lambda event: decide("save"))
        root.bind("<r>", lambda event: decide("recrop"))
        root.bind("<R>", lambda event: decide("recrop"))
        root.bind("<Escape>", lambda event: decide("skip"))
        root.protocol("WM_DELETE_WINDOW", lambda: decide("skip"))
        save.focus_set()
        root.mainloop()
    finally:
        root.destroy()
    return action


def review_and_crop(image: np.ndarray, proposed: np.ndarray | None,
                    args: argparse.Namespace, title: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Keep the current image pending until saved or skipped, without intermediate writes."""
    while True:
        corners = choose_corners(image, proposed, title)
        if corners is None:
            return None
        cropped = finish_crop(rectify(image, corners), args)
        action = preview_crop(cropped, title)
        if action == "save":
            return corners, cropped
        if action != "recrop":
            return None
        # Start a fresh manual selection on the original, not on an already warped crop.
        proposed = None


def folder_dialogs() -> list[str] | None:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        retry = messagebox.askyesno("处理方式", "是否手动处理已有的“裁剪失败”文件夹？\n\n是：选择上次的结果总文件夹，手动裁剪失败照片。\n否：选择原照片，开始自动批量裁剪。")
        if retry:
            destination = filedialog.askdirectory(title="选择包含“裁剪成功”和“裁剪失败”的结果总文件夹")
            return [destination, "--retry-failed"] if destination else None
        source = filedialog.askdirectory(title="选择拍屏照片所在文件夹")
        if not source:
            return None
        destination = filedialog.askdirectory(title="选择结果总文件夹（将创建裁剪成功、裁剪失败两个子文件夹）")
        if not destination:
            return None
        review = messagebox.askyesno("裁切方式", "是否逐张确认裁切区域？\n\n是：查看自动识别结果，可手动点选四角。\n否：自动批量处理，完成后请检查结果。")
        return [source, destination] + (["--review"] if review else [])
    finally:
        root.destroy()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    result.add_argument("input_dir", type=Path, help="Photo folder, or result root with --retry-failed")
    result.add_argument("output_dir", type=Path, nargs="?", help="Result root containing success/failure subfolders")
    mode = result.add_mutually_exclusive_group()
    mode.add_argument("--manual", action="store_true", help="Pick four corners on every photo")
    mode.add_argument("--review", action="store_true", help="Review automatic corners before saving")
    mode.add_argument("--retry-failed", action="store_true", help="Manually crop pending failures from the result root")
    result.add_argument("--recursive", action="store_true", help="Include subfolders")
    trimming = result.add_mutually_exclusive_group()
    trimming.add_argument("--no-trim-black", dest="no_trim_black", action="store_true",
                          help="Preserve black content after perspective correction (default)")
    trimming.add_argument("--trim-black", dest="no_trim_black", action="store_false",
                          help="Opt in to trimming black rows/columns; may remove photographic content")
    result.set_defaults(no_trim_black=True)
    result.add_argument("--black-threshold", type=int, default=45, help="Dark pixel threshold, 0-255 (default: 45)")
    result.add_argument("--max-trim", type=float, default=0.48, help="Maximum black trim per side, fraction (default: 0.48)")
    result.add_argument("--inset", type=float, default=0, help="Extra inward crop per side, fraction (default: 0)")
    result.add_argument("--overwrite", action="store_true", help="Replace existing cropped images")
    result.add_argument("--debug", action="store_true", help="Save detected-corner previews in _debug")
    return result


def run(args: argparse.Namespace) -> int:
    if args.retry_failed:
        if args.output_dir is not None:
            raise ValueError("Use: python screen_crop.py RESULT_ROOT --retry-failed")
        destination = args.input_dir.resolve()
        source = destination / FAILURE_FOLDER
    else:
        if args.output_dir is None:
            raise ValueError("Specify both the input folder and the result folder.")
        source, destination = args.input_dir.resolve(), args.output_dir.resolve()
    success_dir = destination / SUCCESS_FOLDER
    failure_dir = destination / FAILURE_FOLDER
    if not source.is_dir():
        raise ValueError(f"Input folder does not exist: {source}")
    if source == destination:
        raise ValueError("Input and output folders must be different.")
    if not args.retry_failed and (source.is_relative_to(success_dir) or source.is_relative_to(failure_dir)):
        raise ValueError("Use RESULT_ROOT --retry-failed to process the failure folder.")
    if not 0 <= args.black_threshold <= 255:
        raise ValueError("--black-threshold must be between 0 and 255.")
    if not 0 <= args.max_trim <= 0.49 or not 0 <= args.inset <= 0.1:
        raise ValueError("--max-trim must be 0..0.49 and --inset must be 0..0.1.")
    files = sorted(p for p in (source.rglob("*") if args.recursive or args.retry_failed else source.iterdir())
                   if p.is_file() and p.suffix.lower() in EXTENSIONS
                   and not (destination.is_relative_to(source)
                            and p.resolve().is_relative_to(destination)))
    if not files:
        if args.retry_failed:
            print("No pending failed photos. All done.")
            return 0
        raise ValueError("No supported images were found in the input folder.")
    # An incompatible installation is a batch-level error, not a bad photo.
    if not args.manual and not args.retry_failed:
        check_model_runtime()
    success_dir.mkdir(parents=True, exist_ok=True)
    failure_dir.mkdir(parents=True, exist_ok=True)
    report = []
    for index, path in enumerate(files, 1):
        relative = path.relative_to(source)
        # Include the original extension so automatic and retry runs agree on names.
        target = success_dir / relative.with_name(relative.name + "_cropped.png")
        failed_copy = failure_dir / relative
        status, detail = "error", ""
        try:
            if target.exists() and not args.overwrite:
                status, detail = "existing", "Output already exists; use --overwrite to replace."
            else:
                image = load_image(path)
                corners = None if args.manual or args.retry_failed else detect_screen(image)
                cropped = None
                if args.manual or args.review or args.retry_failed:
                    reviewed = review_and_crop(image, corners, args, f"{index}/{len(files)}")
                    if reviewed is None:
                        status, detail = "skipped", "Skipped by user."
                    else:
                        corners, cropped = reviewed
                if status != "skipped":
                    if corners is None:
                        raise ValueError("No screen rectangle detected. Retry RESULT_ROOT --retry-failed.")
                    if cropped is None:
                        cropped = finish_crop(rectify(image, corners), args)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_name(target.name + ".tmp")
                    try:
                        Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)).save(temporary, format="PNG")
                        temporary.replace(target)
                    finally:
                        temporary.unlink(missing_ok=True)
                    status, detail = "ok", f"{cropped.shape[1]}x{cropped.shape[0]}"
                    if args.debug:
                        debug = image.copy()
                        cv2.polylines(debug, [np.round(corners).astype(np.int32)], True, (0, 255, 0),
                                      max(2, round(max(image.shape[:2]) / 600)))
                        debug_path = destination / "_debug" / target.relative_to(destination)
                        debug_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            Image.fromarray(cv2.cvtColor(debug, cv2.COLOR_BGR2RGB)).save(debug_path)
                        except OSError as exc:
                            detail += f"; debug preview unavailable: {exc}"
        except Exception as exc:
            status, detail = "error", str(exc)
        if status in ("error", "skipped") and not args.retry_failed:
            try:
                failed_copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, failed_copy)
            except OSError as exc:
                status = "error"
                detail += f"; could not export failed original: {exc}"
        elif status == "ok" and failed_copy.exists():
            try:
                failed_copy.unlink()
            except OSError as exc:
                detail += f"; could not remove failure copy: {exc}"
        print(f"[{index}/{len(files)}] {status}: {relative} {detail}", flush=True)
        report.append([str(relative), str(target.relative_to(destination)), status, detail])
    report_path = destination / ("manual_crop_report.csv" if args.retry_failed else "crop_report.csv")
    with report_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["input", "output", "status", "detail"])
        writer.writerows(report)
    errors = sum(row[2] == "error" for row in report)
    print(f"Done. Saved: {sum(row[2] == 'ok' for row in report)}; errors: {errors}. Report: {report_path}")
    return 1 if errors else 0


def main() -> int:
    argv = sys.argv[1:]
    gui = not argv
    if not argv:
        try:
            argv = folder_dialogs()
        except Exception as exc:
            print(f"Folder dialog unavailable: {exc}. Use: python screen_crop.py INPUT OUTPUT", file=sys.stderr)
            return 2
        if argv is None:
            return 0
    args = parser().parse_args(argv)
    try:
        result = run(args)
        if gui and not args.retry_failed:
            failure_dir = args.output_dir.resolve() / FAILURE_FOLDER
            pending = sum(p.is_file() and p.suffix.lower() in EXTENSIONS for p in failure_dir.rglob("*"))
            if pending:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                try:
                    retry = messagebox.askyesno("自动裁剪完成", f"还有 {pending} 张照片位于“裁剪失败”。\n现在手动裁剪这些照片吗？\n\n成功后将保存到“裁剪成功”，并移除失败副本。")
                finally:
                    root.destroy()
                if retry:
                    retry_args = argparse.Namespace(**vars(args))
                    retry_args.input_dir = args.output_dir
                    retry_args.output_dir = None
                    retry_args.retry_failed = True
                    retry_args.manual = retry_args.review = False
                    result = run(retry_args)
        return result
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
