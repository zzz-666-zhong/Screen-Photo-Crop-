"""Train from unmarked photos and explicit corner labels; augment training groups only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

if __name__ == '__main__':
    from launch_crop import runtime_problem, main as launch_main
    problem = runtime_problem()
    if problem is not None:
        print(problem, flush=True)
        raise SystemExit(launch_main(sys.argv[1:], script='train_screen_model.py'))

import cv2
import numpy as np
import screen_crop as crop


def overlap(a, b):
    """Double-precision convex clipping, including nearly collinear shared edges."""
    a, b = np.asarray(a,dtype=float), np.asarray(b,dtype=float)
    def area(points):
        if len(points)<3: return 0.
        p=np.asarray(points,dtype=float)
        return float(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1)))/2
    direction = 1 if area(b)>=0 else -1
    polygon = [tuple(p) for p in a]
    for start,end in zip(b,np.roll(b,-1,axis=0)):
        if not polygon: break
        dx,dy = end-start
        def distance(p):
            return direction*(dx*(p[1]-start[1])-dy*(p[0]-start[0]))
        clipped=[]
        previous=polygon[-1]; dp=distance(previous)
        for point in polygon:
            dc=distance(point)
            if (dc>=-1e-8)!=(dp>=-1e-8):
                t=dp/(dp-dc)
                clipped.append((previous[0]+t*(point[0]-previous[0]),previous[1]+t*(point[1]-previous[1])))
            if dc>=-1e-8: clipped.append(point)
            previous,dp=point,dc
        polygon=clipped
    aa,bb=abs(area(a)),abs(area(b))
    intersection=min(aa,bb,abs(area(polygon)))
    return float(intersection/max(aa+bb-intersection,1e-12))


def read_dataset(path):
    rows = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(rows, list) or not rows:
        raise ValueError('Dataset must be a nonempty JSON array.')
    ids, groups, hashes = set(), {}, {}
    result = []
    for item in rows:
        row = dict(item)
        if row['id'] in ids:
            raise ValueError('Sample IDs must be unique.')
        ids.add(row['id'])
        if row['split'] not in ('train', 'holdout'):
            raise ValueError('split must be train or holdout')
        image_path = Path(row['image'])
        if not image_path.is_absolute(): image_path = path.parent/image_path
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        group = row.get('group', row['id'])
        for mapping, key in ((groups, group), (hashes, digest)):
            if key in mapping and mapping[key] != row['split']:
                raise ValueError('The same image or capture group appears in both training and holdout splits.')
            mapping[key] = row['split']
        row.update(image=str(image_path), group=group, source_sha256=digest)
        row['quad'] = crop.order_corners(np.float32(row['quad'])).tolist()
        result.append(row)
    return result


def sample_seed(group, seed):
    return int.from_bytes(hashlib.sha256(f'{seed}:{group}'.encode()).digest()[:4], 'little')


def training_variants(image, quad, count=0, seed=0):
    """Paired photometric/geometric stressors, with no changes to source files."""
    scale = min(1., 1400/max(image.shape[:2]))
    image = cv2.resize(image, None, fx=scale, fy=scale)
    quad = np.float32(quad)*scale
    yield 'original', image, quad
    rng = np.random.default_rng(seed)
    h, w = image.shape[:2]
    for index in range(count):
        mode = ('glare', 'motion', 'combined')[index % 3]
        pixels, corners = image.copy(), quad.copy()
        if mode == 'combined':
            frame = np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
            moved = frame+rng.uniform(-.008,.008,(4,2)).astype(np.float32)*[w,h]
            matrix = cv2.getPerspectiveTransform(frame,np.float32(moved))
            pixels = cv2.warpPerspective(pixels,matrix,(w,h),borderMode=cv2.BORDER_REFLECT)
            corners = cv2.perspectiveTransform(corners[None],matrix)[0]
        if mode in ('glare', 'combined'):
            size = np.maximum(corners.max(axis=0)-corners.min(axis=0),12)
            center = corners.mean(axis=0)+rng.uniform(-.65,.65,2)*size
            yy,xx = np.indices((h,w),dtype=np.float32)
            sigma = size*rng.uniform(.65,1.6,2)
            glow = np.exp(-.5*(((xx-center[0])/sigma[0])**2+((yy-center[1])/sigma[1])**2))
            alpha = glow[:,:,None]*rng.uniform(.22,.46)
            pixels = np.uint8(np.clip(pixels*(1-alpha)+np.array([235,245,255])*alpha,0,255))
        if mode in ('motion', 'combined'):
            length = int(rng.choice([5,7,9]))
            kernel = np.zeros((length,length),np.float32)
            cv2.line(kernel,(0,length//2),(length-1,length//2),1,1)
            rotation = cv2.getRotationMatrix2D(((length-1)/2,(length-1)/2),float(rng.uniform(0,180)),1)
            kernel = cv2.warpAffine(kernel,rotation,(length,length))
            kernel /= kernel.sum()
            pixels = cv2.filter2D(pixels,-1,kernel,borderType=cv2.BORDER_REFLECT)
        yield f'{mode}-{index+1}', pixels, corners


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--output',type=Path,default=Path('trained_model'))
    parser.add_argument('--augment',type=int,default=0,help='Glare/motion/perspective variants per training image (0-12)')
    parser.add_argument('--seed',type=int,default=20261011)
    parser.add_argument('--role',choices=('base','reflection'),default='base')
    args = parser.parse_args()
    if not 0 <= args.augment <= 12: parser.error('--augment must be between 0 and 12')
    rows = read_dataset(args.dataset)
    train = [r for r in rows if r['split']=='train']
    if len({r['group'] for r in train}) < 3:
        raise ValueError('Provide at least three training capture groups.')
    stem = 'screen_crop_forest' if args.role=='base' else 'screen_crop_reflection'
    weight_path, metadata_path = args.output/(stem+'.xml.gz'), args.output/'screen_crop_model.json'
    if weight_path.exists() or metadata_path.exists():
        raise ValueError('Output model exists; choose a new output folder.')
    matrices, targets, fitted, skipped = [], [], [], []
    for row in train:
        image = crop.load_image(Path(row['image']))
        count = int(row.get('augment',args.augment))
        if not 0 <= count <= 12: raise ValueError('Per-image augment must be between 0 and 12')
        for variant, pixels, quad in training_variants(image,row['quad'],count,sample_seed(row['group'],args.seed)):
            candidates = crop.photo_candidates(pixels)
            y = np.float32([overlap(q,quad) for q,f in candidates])
            best = float(y.max()) if len(y) else 0
            if best < .65:
                if variant=='original':
                    raise ValueError(f"No useful candidate for {row['id']}; improve candidate detection before fitting.")
                skipped.append(dict(id=row['id'],variant=variant,best_iou=best))
                print(row['id'],variant,'skipped: no useful proposal',flush=True)
                continue
            matrices.append(np.float32([f for q,f in candidates])); targets.append(y)
            fitted.append(dict(id=row['id'],variant=variant,candidates=len(y),best_iou=best))
            print(row['id'],variant,len(y),'candidates, best overlap',round(best,3),flush=True)
    X,y = np.concatenate(matrices),np.concatenate(targets)
    positive = np.flatnonzero(y>.80)
    X = np.concatenate([X,X[positive],X[positive]])
    y = np.concatenate([y,y[positive],y[positive]])
    cv2.setRNGSeed(args.seed)
    forest = cv2.ml.RTrees_create()
    forest.setMaxDepth(16); forest.setMinSampleCount(3)
    forest.setRegressionAccuracy(.005); forest.setActiveVarCount(12)
    forest.setTermCriteria((cv2.TERM_CRITERIA_MAX_ITER,240,0))
    forest.train(cv2.ml.TrainData_create(X,cv2.ml.ROW_SAMPLE,y))
    args.output.mkdir(parents=True,exist_ok=True)
    # In-memory serialization also supports Chinese output paths on Windows.
    storage = cv2.FileStorage('',cv2.FILE_STORAGE_WRITE|cv2.FILE_STORAGE_MEMORY|cv2.FILE_STORAGE_FORMAT_XML)
    storage.startWriteStruct('opencv_ml_rtrees',cv2.FileNode_MAP)
    forest.write(storage)
    storage.endWriteStruct()
    import gzip
    with gzip.open(weight_path,'wt',encoding='utf-8') as stream:
        stream.write(storage.releaseAndGetString())
    model = dict(version=3,features=crop.FEATURE_NAMES,method='OpenCV random-forest IoU regression',trees=240,
        role=args.role,training_sources=[r['id'] for r in train],
        holdout_sources=[r['id'] for r in rows if r['split']=='holdout'],seed=args.seed,
        training_groups=len({r['group'] for r in train}),holdout_groups=len({r['group'] for r in rows if r['split']=='holdout'}),
        augment=args.augment,weight_sha256=hashlib.sha256(weight_path.read_bytes()).hexdigest(),
        fitted_variants=len(fitted),skipped_variants=len(skipped))
    metadata_path.write_text(json.dumps(model,indent=2),encoding='utf-8')
    (args.output/'training_report.json').write_text(json.dumps(dict(model=model,fitted=fitted,skipped=skipped),indent=2),encoding='utf-8')
    print('Saved model to',args.output,'; evaluate excluded capture groups before adopting it.')


if __name__=='__main__': main()
