"""Test crop decisions independently of Tk and desktop availability."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import screen_crop as crop
from crop_ui import CropSelection, CropWorkspace, ImageViewport


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.image=np.zeros((100,140,3),np.uint8)
        self.image[:20,:20]=(255,0,0)
        self.image[:20,-20:]=(0,255,0)
        self.image[-20:,-20:]=(0,0,255)
        self.image[-20:,:20]=(255,255,0)
        self.args=crop.parser().parse_args(['input','output','--square'])
        self.selection=CropSelection(self.image,self.args,crop)
        self.corners=[(0,0),(139,0),(139,99),(0,99)]

    def test_four_points_preview_without_saving_and_reset_discards_preview(self):
        before=self.image.copy()
        for point in self.corners[:3]:
            self.selection.add(point)
            self.assertIsNone(self.selection.accept())
        self.selection.add(self.corners[3])
        self.assertIsNotNone(self.selection.preview)
        self.assertIsNotNone(self.selection.accept())
        self.selection.reset()
        self.assertIsNone(self.selection.accept())
        self.assertEqual(self.selection.points,[])
        np.testing.assert_array_equal(self.image,before)

    def test_square_rectification_preserves_all_four_corner_contents(self):
        self.selection.set_corners(np.float32(self.corners))
        _,result=self.selection.accept()
        self.assertEqual(result.shape[:2],(139,139))
        for actual,expected in ((result[5,5],self.image[5,5]),
                                (result[5,-5],self.image[5,-5]),
                                (result[-5,-5],self.image[-5,-5]),
                                (result[-5,5],self.image[-5,5])):
            np.testing.assert_array_equal(actual,expected)

    def test_undo_or_degenerate_selection_cannot_accept_old_preview(self):
        self.selection.set_corners(np.float32(self.corners))
        self.selection.undo()
        self.assertIsNone(self.selection.accept())
        self.selection.add(self.corners[0])
        self.assertIsNone(self.selection.accept())
        self.assertTrue(self.selection.error)

    def test_square_remains_square_after_optional_black_trimming(self):
        self.args.no_trim_black=False
        self.image[20:80,20:120]=(70,130,210)
        self.selection.set_corners(np.float32(self.corners))
        result=self.selection.accept()[1]
        self.assertEqual(result.shape[0],result.shape[1])
        self.assertGreater(result.shape[0],8)

    def test_letterboxed_viewport_maps_display_coordinates(self):
        view=ImageViewport.fit((800,400),(500,500))
        np.testing.assert_allclose(view.to_image(*view.to_canvas((320,150))),(320,150))
        self.assertIsNone(view.to_image(0,0))

    def test_enter_accepts_ready_preview_once_and_rejects_incomplete_selection(self):
        workspace=CropWorkspace.__new__(CropWorkspace)
        workspace.busy=True
        workspace.future=workspace.drag_index=None
        workspace.enter_down=False
        workspace.selection=self.selection
        state={'value':'pending'}
        workspace.action=SimpleNamespace(get=lambda:state['value'],set=lambda v:state.update(value=v))
        workspace._disable_actions=Mock()
        event=SimpleNamespace(widget=SimpleNamespace(winfo_class=lambda:'Canvas'))
        workspace._enter(event)
        self.assertEqual(state['value'],'pending')
        workspace.enter_down=False
        self.selection.set_corners(np.float32(self.corners))
        workspace._enter(event)
        self.assertEqual(state['value'],'save')
        state['value']='pending'
        workspace._enter(event)
        self.assertEqual(state['value'],'pending')


if __name__=='__main__':
    unittest.main()
