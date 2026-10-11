"""Compare crop versions on explicit labels and optional deterministic stressors."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import screen_crop as current
from train_screen_model import overlap,read_dataset,training_variants,sample_seed


def load_backend(path):
    path=path/'screen_crop.py' if path.is_dir() else path
    spec=importlib.util.spec_from_file_location('crop_evaluation_baseline',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path)
    parser.add_argument('--baseline',type=Path,required=True,help='Old screen_crop.py with its matching models beside it')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stress',type=int,default=0,help='Additional glare/motion/combined variants (0-12)')
    parser.add_argument('--seed',type=int,default=20261012)
    parser.add_argument('--split',choices=('train','holdout','all'),default='all')
    args=parser.parse_args()
    if args.output.exists(): parser.error('Output exists; choose a new output path.')
    if not 0<=args.stress<=12: parser.error('--stress must be between 0 and 12')
    baseline=load_backend(args.baseline)
    rows=read_dataset(args.dataset)
    records=[]
    for row in rows:
        if args.split!='all' and row['split']!=args.split: continue
        image=current.load_image(Path(row['image']))
        for variant,pixels,quad in training_variants(image,row['quad'],args.stress,sample_seed(row['group'],args.seed)):
            record=dict(sample_id=row['id'],split=row['split'],variant=variant)
            for name,backend in (('baseline',baseline),('current',current)):
                found=backend.detect_screen(pixels,square=row.get('square',False))
                iou=overlap(found,quad) if found is not None else 0.
                record.update({name+'_iou':round(iou,6),name+'_pass':int(iou>=.85)})
            records.append(record)
            print(json.dumps(record),flush=True)
    if not records: parser.error('No samples in the selected split.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]))
        writer.writeheader();writer.writerows(records)
    print('Results are specific to these labeled captures; stress variants are not independent photos.')


if __name__=='__main__': main()
