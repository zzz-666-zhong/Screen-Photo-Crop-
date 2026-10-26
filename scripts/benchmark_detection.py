"""Compare labeled localization and warm CPU time without publishing source images."""
from __future__ import annotations
import argparse
import csv
import importlib.util
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import screen_crop as current
from train_screen_model import read_dataset,overlap


def load_baseline(directory):
    spec=importlib.util.spec_from_file_location('benchmark_baseline',directory/'screen_crop.py')
    backend=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    return backend


def warm_models(backend):
    for filename in ('screen_crop_forest.xml.gz','screen_crop_reflection.xml.gz'):
        path=Path(backend.__file__).with_name(filename)
        if path.exists():backend.load_scoring_forest(str(path),path.stat().st_mtime_ns)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--baseline',type=Path,required=True,help='Folder with earlier script and matching models')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=3,help='Median of 1-9 calls per photo/version, excluding load time')
    parser.add_argument('--split',choices=('train','holdout','all'),default='all')
    args=parser.parse_args()
    if args.output.exists():parser.error('Choose a new output CSV; existing files are protected.')
    if not 1<=args.repeats<=9:parser.error('--repeats must be 1-9')
    rows=read_dataset(args.dataset)
    rows=[r for r in rows if args.split=='all' or r['split']==args.split]
    if not rows:parser.error('No photos in the selected split.')
    baseline=load_baseline(args.baseline)
    for backend in (baseline,current):warm_models(backend)
    records=[]
    for index,row in enumerate(rows):
        image=current.load_image(Path(row['image']))
        record=dict(sample_id=row['id'],split=row['split'])
        backends=[('baseline',baseline),('current',current)]
        if index%2:backends.reverse()
        for name,backend in backends:
            times=[]
            for _ in range(args.repeats):
                start=time.perf_counter()
                quad=backend.detect_screen(image,square=row.get('square',False))
                times.append(time.perf_counter()-start)
            iou=overlap(quad,row['quad']) if quad is not None else 0.
            record.update({name+'_iou':round(iou,6),name+'_pass':int(iou>=.85),
                           name+'_seconds':round(statistics.median(times),6)})
        records.append(record)
        print(f"{row['id']}: IoU {record['baseline_iou']:.3f} -> {record['current_iou']:.3f}; "
              f"{record['baseline_seconds']:.3f}s -> {record['current_seconds']:.3f}s",flush=True)
    fields=['sample_id','split','baseline_iou','baseline_pass','baseline_seconds',
            'current_iou','current_pass','current_seconds']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(records)
    print('Times exclude image I/O, model loading, preview, and saving; CPU/environment dependent.')
    print('Same-session examples and derivatives do not establish accuracy on new devices/scenes.')


if __name__=='__main__':main()
