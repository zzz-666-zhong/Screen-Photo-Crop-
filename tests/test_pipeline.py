"""Look-ahead must be bounded, reusable, and independent of the UI/save state."""
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
from PIL import Image
import screen_crop as crop
from crop_ui import CropWorkspace
from review_pipeline import ReviewPipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.path=self.root/'a.png'
        Image.new('RGB',(160,120),'gray').save(self.path)
        self.args=crop.parser().parse_args(['in','out','--review'])
        self.quad=np.float32([[10,10],[150,10],[150,110],[10,110]])
        self.backend=SimpleNamespace(load_image=crop.load_image,detect_screen=Mock(return_value=self.quad),
            rectify=crop.rectify,finish_crop=crop.finish_crop)
        self.pipeline=ReviewPipeline(self.backend,self.args);self.addCleanup(self.pipeline.close)
        self.addCleanup(lambda:self.pipeline.executor.shutdown(wait=True,cancel_futures=True))

    def test_next_image_starts_before_it_is_consumed_and_reuses_the_result(self):
        started=threading.Event();release=threading.Event()
        def detect(*a,**kw):
            started.set();release.wait(3);return self.quad
        self.backend.detect_screen.side_effect=detect
        future=self.pipeline.request(self.path)
        try:
            self.assertTrue(started.wait(2))
            self.assertFalse(future.done())
            self.assertIs(self.pipeline.take(self.path),future)
        finally:release.set()
        result=future.result(timeout=4)
        self.assertIsNotNone(result.preview)
        self.backend.detect_screen.assert_called_once()
        self.assertEqual(list(self.root.iterdir()),[self.path])

    def test_changed_source_invalidates_the_prefetched_image(self):
        old=self.pipeline.request(self.path);old.result(timeout=3)
        Image.new('RGB',(180,140),'white').save(self.path)
        fresh=self.pipeline.take(self.path)
        self.assertIsNot(fresh,old)
        self.assertEqual(fresh.result(timeout=3).image.shape[:2],(140,180))

    def test_failed_detector_keeps_the_source_available_for_manual_selection(self):
        self.backend.detect_screen.side_effect=ValueError('unavailable')
        result=self.pipeline.take(self.path).result(timeout=3)
        self.assertEqual(result.image.shape[:2],(120,160))
        self.assertIn('unavailable',result.error)

    def test_manual_lookahead_only_loads_and_never_detects(self):
        self.args.manual=True
        result=self.pipeline.take(self.path).result(timeout=3)
        self.backend.detect_screen.assert_not_called()
        self.assertIsNone(result.preview)

    def test_review_uses_specialist_aware_detector_when_available(self):
        self.backend.detect_review_screen=Mock(return_value=self.quad)
        result=self.pipeline.take(self.path).result(timeout=4)
        self.backend.detect_review_screen.assert_called_once()
        self.backend.detect_screen.assert_not_called()
        self.assertIsNotNone(result.preview)

    def test_close_discards_the_pending_entry(self):
        self.pipeline.request(self.path)
        self.pipeline.close()
        self.assertIsNone(self.pipeline.entry)

    def test_confirmed_last_image_cannot_be_checkpointed_as_a_new_draft(self):
        workspace=CropWorkspace.__new__(CropWorkspace)
        workspace.session=SimpleNamespace(draft=Mock())
        workspace.selection=Mock()
        workspace.processing=False
        workspace.action=Mock(get=Mock(return_value='save'))
        workspace.checkpoint_selection()
        workspace.session.draft.assert_not_called()

    def test_pause_during_save_defers_until_current_write_finishes(self):
        workspace=CropWorkspace.__new__(CropWorkspace)
        workspace.busy=workspace.processing=True
        workspace.paused=False;workspace.status=Mock();workspace.checkpoint_selection=Mock()
        workspace.pause()
        self.assertTrue(workspace.paused)
        workspace.checkpoint_selection.assert_not_called()


if __name__=='__main__':unittest.main()
