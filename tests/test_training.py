import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from train_screen_model import overlap,read_dataset,training_variants


class TrainingTests(unittest.TestCase):
    def test_overlap_is_symmetric_and_bounded_for_shared_nearly_collinear_edges(self):
        a=np.float32([[105.52,182.6],[573,164],[592,370],[87.32,490.28]])
        b=np.float32([[196,179],[573,164],[599,451],[185,467]])
        iou=overlap(a,b)
        self.assertTrue(0<iou<1)
        self.assertAlmostEqual(iou,overlap(b,a),places=8)
        self.assertAlmostEqual(iou,overlap(a,b[::-1]),places=8)
        rect=np.float32([[0,0],[10,0],[10,10],[0,10]])
        self.assertAlmostEqual(overlap(rect,rect+[5,0]),1/3)
        self.assertEqual(overlap(rect,rect),1)
        self.assertEqual(overlap(rect,rect+[10,0]),0)

    def test_transformed_capture_cannot_cross_splits_by_group_or_file_content(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            Image.new('RGB',(20,20),'red').save(folder/'a.png')
            Image.new('RGB',(20,20),'blue').save(folder/'b.png')
            quad=[[1,1],[18,1],[18,18],[1,18]]
            rows=[dict(id='a',image='a.png',group='capture',split='train',quad=quad),
                  dict(id='b',image='b.png',group='capture',split='holdout',quad=quad)]
            manifest=folder/'dataset.json'
            manifest.write_text(json.dumps(rows),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'capture group'): read_dataset(manifest)
            rows[1].update(image='a.png',group='different')
            manifest.write_text(json.dumps(rows),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'capture group'): read_dataset(manifest)

    def test_stressors_are_reproducible_leave_source_unchanged_and_transform_labels(self):
        image=np.full((120,160,3),40,np.uint8)
        image[30:90,50:110]=200
        quad=np.float32([[50,30],[109,30],[109,89],[50,89]])
        before=image.copy()
        first=list(training_variants(image,quad,3,seed=71))
        second=list(training_variants(image,quad,3,seed=71))
        self.assertEqual(len(first),4)
        for (name,pixels,corners),(other,expected,labels) in zip(first,second):
            self.assertEqual(name,other)
            np.testing.assert_array_equal(pixels,expected)
            np.testing.assert_array_equal(corners,labels)
            self.assertTrue(np.isfinite(corners).all())
        self.assertFalse(np.array_equal(first[-1][2],quad))
        np.testing.assert_array_equal(image,before)


if __name__=='__main__': unittest.main()
