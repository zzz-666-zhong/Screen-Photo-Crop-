"""Manual capture rejection is an archive decision, never an automatic verdict."""
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

import numpy as np
from PIL import Image
import screen_crop as crop
from batch_state import fingerprint
from capture_failures import CaptureFailures,FOLDER,REPORT,csv_cell
from crop_ui import CropWorkspace


class DetectionPriorityTests(unittest.TestCase):
    def test_picture_edge_result_cannot_be_overridden_by_a_black_frame(self):
        primary=np.float32([[10,10],[90,10],[90,90],[10,90]])
        with patch.object(crop,'_detect_screen_general',return_value=primary),patch.object(crop,'detect_black_border') as frame:
            np.testing.assert_array_equal(crop.detect_screen(np.zeros((100,100,3),np.uint8)),primary)
            frame.assert_not_called()

    def test_missing_picture_edges_can_use_a_frame_but_not_a_plain_panel(self):
        frame=np.float32([[10,10],[90,10],[90,90],[10,90]])
        textured=np.random.default_rng(10).integers(0,255,(100,100,3),dtype=np.uint8)
        with patch.object(crop,'_detect_screen_general',return_value=None),patch.object(crop,'detect_black_border',return_value=frame):
            np.testing.assert_allclose(crop.detect_screen(textured),frame)
            self.assertIsNone(crop.detect_screen(np.zeros_like(textured)))


class CaptureFailureTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.source=self.root/'photos';self.output=self.root/'results'
        self.source.mkdir();(self.source/'nested').mkdir()
        Image.new('RGB',(160,120),(60,90,180)).save(self.source/'nested'/'照片.png')
        self.path=self.source/'nested'/'照片.png'
        self.quad=np.float32([[10,10],[150,10],[150,110],[10,110]])
        self.workspace=SimpleNamespace(aborted=False,batch_decision='',record=Mock(),
            selection_metadata=lambda:dict(manual_modified=True),failure_reason='反光遮挡 / Glare')
        self.workspace.begin_batch=lambda session,labels,args:self.workspace.__dict__.update(session=session,labels=labels)
        self.workspace.prepare_item=lambda index:self.workspace.__dict__.update(index=index,batch_decision='')
        def reject(*a,**kw):self.workspace.batch_decision='capture_failed'
        self.workspace.review=reject

    def args(self,*flags):
        return crop.parser().parse_args([str(self.source),str(self.output),'--review','--recursive',*flags])

    def test_reject_copies_source_records_reason_and_finishes_without_a_crop(self):
        before=self.path.read_bytes()
        self.assertEqual(crop.run(self.args(),workspace=self.workspace),0)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual((self.output/FOLDER/'nested'/'照片.png').read_bytes(),before)
        self.assertEqual(list((self.output/crop.SUCCESS_FOLDER).rglob('*.png')),[])
        self.assertEqual(self.workspace.labels.data['items'],{})
        self.assertEqual(self.workspace.session.records['nested/照片.png']['status'],'capture_failed')
        self.assertFalse(self.workspace.session.pending(0))
        self.assertEqual(self.workspace.session.data['status'],'complete')
        with (self.output/REPORT).open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.reader(stream))
        self.assertEqual(len(rows),2)
        self.assertIn('反光遮挡',rows[1][3]);self.assertIn('待重拍',rows[1][4])
        self.assertEqual(rows[1][1],str(self.path.resolve()))
        with patch.object(self.workspace,'review') as review:
            crop.run(self.args('--resume'),workspace=self.workspace)
            review.assert_not_called()

    def test_rejection_is_deduplicated_and_success_retains_archive_as_history(self):
        crop.run(self.args(),workspace=self.workspace)
        args=self.args('--resume');args.start_index=0
        crop.run(args,workspace=self.workspace)
        store=CaptureFailures(self.output)
        self.assertEqual(len(store.data['items']),1)
        self.workspace.review=lambda image,*a,**kw:(self.quad,crop.rectify(image,self.quad))
        crop.run(args,workspace=self.workspace)
        store=CaptureFailures(self.output)
        self.assertEqual(next(iter(store.data['items'].values()))['status'],'recropped')
        self.assertTrue((self.output/FOLDER/'nested'/'照片.png').exists())

    def test_same_filename_new_capture_does_not_overwrite_prior_archive(self):
        self.output.mkdir();store=CaptureFailures(self.output)
        first=store.reject(self.path,'nested/照片.png',fingerprint(self.path),'blur')
        previous=first.read_bytes()
        Image.new('RGB',(180,140),'white').save(self.path)
        second=store.reject(self.path,'nested/照片.png',fingerprint(self.path),'glare')
        self.assertNotEqual(first,second);self.assertEqual(first.read_bytes(),previous)
        self.assertEqual(second.read_bytes(),self.path.read_bytes())
        self.assertEqual(len(store.data['items']),2)

    def test_automatic_detection_error_is_not_a_manual_capture_rejection(self):
        args=crop.parser().parse_args([str(self.source),str(self.output),'--recursive'])
        with patch.object(crop,'detect_screen',return_value=None):
            self.assertEqual(crop.run(args),1)
        self.assertFalse((self.output/FOLDER).exists())
        self.assertFalse((self.output/REPORT).exists())

    def test_rejecting_a_previously_saved_photo_keeps_its_crop(self):
        self.workspace.review=lambda image,*a,**kw:(self.quad,crop.rectify(image,self.quad))
        crop.run(self.args(),workspace=self.workspace)
        target=self.output/crop.SUCCESS_FOLDER/'nested'/'照片.png_cropped.png'
        saved=target.read_bytes()
        def reject(*a,**kw):self.workspace.batch_decision='capture_failed'
        self.workspace.review=reject
        args=self.args('--resume');args.start_index=0
        crop.run(args,workspace=self.workspace)
        self.assertEqual(target.read_bytes(),saved)
        self.assertTrue(self.workspace.session.records['nested/照片.png']['saved'])

    def test_export_escapes_formula_like_filenames(self):
        self.assertEqual(csv_cell('=filename.png'),"'=filename.png")
        self.assertEqual(csv_cell('普通照片.png'),'普通照片.png')

    def test_reject_button_does_not_require_valid_crop_corners(self):
        workspace=CropWorkspace.__new__(CropWorkspace)
        workspace.busy=True;workspace.processing=False
        workspace.selection=SimpleNamespace(preview=None)
        workspace.action=Mock(get=Mock(return_value='pending'))
        workspace.capture_reason=Mock(get=Mock(return_value='目标缺失 / Missing'))
        workspace._disable_actions=Mock()
        workspace.reject_capture()
        self.assertEqual(workspace.batch_decision,'capture_failed')
        self.assertEqual(workspace.failure_reason,'目标缺失 / Missing')
        workspace.action.set.assert_called_once_with('capture_failed')

    def test_returning_to_an_earlier_draft_does_not_review_a_settled_rejection_again(self):
        for name in ('a.png','b.png'):Image.new('RGB',(160,120),'gray').save(self.source/name)
        visits=[]
        def review(image,*a,**kw):
            index=self.workspace.index;visits.append(index)
            if visits==[0,1]:
                self.workspace.session.draft([[10,10]],source_sha256=fingerprint(self.source/'b.png'))
                self.workspace.batch_decision='jump';self.workspace.requested_index=2
                return None
            if index==2:
                self.workspace.batch_decision='capture_failed'
                return None
            return self.quad,crop.rectify(image,self.quad)
        self.workspace.review=review
        crop.run(self.args(),workspace=self.workspace)
        self.assertEqual(visits,[0,1,2,1])
        self.assertEqual(self.workspace.session.data['status'],'complete')


if __name__=='__main__':unittest.main()
