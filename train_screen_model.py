"""Train the crop scorer from an explicitly labeled local dataset.

Usage: python train_screen_model.py dataset.json --output model_output
Each item: {"id":"...", "image":"path/to/unmarked.png", "quad":[[x,y],...],
            "split":"train" or "holdout"}. All images of one capture and its
derivatives must be assigned to the same split. Use unmarked images for fitting.
"""
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


def overlap(a,b):
    intersection,_=cv2.intersectConvexConvex(np.float32(a),np.float32(b))
    return float(intersection/(abs(cv2.contourArea(a))+abs(cv2.contourArea(b))-intersection+1e-6))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--output',type=Path,default=Path('trained_model'))
    args=parser.parse_args()
    rows=json.loads(args.dataset.read_text(encoding='utf-8'))
    matrices=[];targets=[];sources=[];hash_splits={}
    for row in rows:
        path=Path(row['image'])
        if not path.is_absolute():path=args.dataset.parent/path
        split=row['split']
        if split not in ('train','holdout'):raise ValueError('split must be train or holdout')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in hash_splits and hash_splits[digest]!=split:
            raise ValueError('The same image appears in both training and holdout splits.')
        hash_splits[digest]=split
        if split!='train':continue
        quad=crop.order_corners(np.float32(row['quad']))
        candidates=crop.photo_candidates(crop.load_image(path))
        if not candidates:raise ValueError(f"No candidates for {row['id']}")
        y=np.float32([overlap(q,quad) for q,f in candidates])
        if y.max()<.65:raise ValueError(f"No useful candidate for {row['id']}; improve candidate detection before fitting.")
        matrices.append(np.float32([f for q,f in candidates]));targets.append(y)
        sources.append(row['id'])
        print(row['id'],len(y),'candidates, best overlap',round(float(y.max()),3),flush=True)
    if len(sources)<3:raise ValueError('Provide at least three training images.')
    X=np.concatenate(matrices);y=np.concatenate(targets)
    positive=np.flatnonzero(y>.85)
    X=np.concatenate([X,X[positive],X[positive]])
    y=np.concatenate([y,y[positive],y[positive]])
    cv2.setRNGSeed(20261008)
    forest=cv2.ml.RTrees_create()
    forest.setMaxDepth(18);forest.setMinSampleCount(1)
    forest.setRegressionAccuracy(.005);forest.setActiveVarCount(12)
    forest.setTermCriteria((cv2.TERM_CRITERIA_MAX_ITER,240,0))
    forest.train(cv2.ml.TrainData_create(X,cv2.ml.ROW_SAMPLE,y))
    args.output.mkdir(parents=True,exist_ok=True)
    forest.save(str(args.output/'screen_crop_forest.xml.gz'))
    model=dict(version=2,features=crop.FEATURE_NAMES,method='OpenCV random-forest IoU regression',trees=240,
               training_sources=sources,holdout_sources=[r['id'] for r in rows if r['split']=='holdout'],seed=20261008)
    (args.output/'screen_crop_model.json').write_text(json.dumps(model,indent=2),encoding='utf-8')
    print('Saved model to',args.output,'; evaluate holdout images before replacing a working model.')


if __name__=='__main__':main()
