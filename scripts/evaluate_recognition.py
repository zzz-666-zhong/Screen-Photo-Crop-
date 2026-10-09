"""Reproduce synthetic localization metrics; no private images are used."""
import argparse
import csv
import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import screen_crop
from examples.recognition_scenes import KINDS, make_scene
from train_screen_model import overlap


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,help='Optional screen_crop.py from v0.1.1')
    parser.add_argument('--output',type=Path,default=ROOT/'recognition_metrics.csv')
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose another output path.')
    baseline=None
    if args.baseline:
        spec=importlib.util.spec_from_file_location('recognition_baseline',args.baseline)
        baseline=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(baseline)
        # Both versions use identical bundled weights; models are not retrained.
        baseline.__file__=str(ROOT/'screen_crop.py')
    rows=[]
    for kind in KINDS:
        # Fixed verification seeds, excluded from threshold development (11,29).
        for seed in (41,67):
            image,expected=make_scene(kind,seed)
            found=screen_crop.detect_screen(image)
            iou=overlap(found,expected) if found is not None else 0.
            row={'sample_id':f'{kind}-{seed}','kind':kind,'seed':seed,
                 'current_iou':round(iou,6),'current_pass':int(iou>=.85)}
            if baseline:
                previous=baseline.detect_screen(image)
                previous_iou=overlap(previous,expected) if previous is not None else 0.
                row.update(baseline_iou=round(previous_iou,6),baseline_pass=int(previous_iou>=.85))
            rows.append(row)
            print(row,flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    print(f"Passed IoU >= .85: {sum(r['current_pass'] for r in rows)}/{len(rows)}")
    print('Synthetic regression only; not a real-world accuracy estimate.')


if __name__=='__main__':
    main()
