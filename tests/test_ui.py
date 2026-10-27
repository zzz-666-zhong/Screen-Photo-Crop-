"""Test crop decisions independently of Tk and desktop availability."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
import screen_crop as crop
from crop_ui import CropSelection, CropWorkspace, ImageViewport, ImageNavigation
from batch_state import OutputDirectoryError


class OutputRecoveryTests(unittest.TestCase):
    def test_unwritable_output_returns_to_settings_without_retrying_or_changing_options(self):
        workspace=CropWorkspace.__new__(CropWorkspace)
        error=OutputDirectoryError('blocked-results',PermissionError(13,'Access denied'))
        workspace.backend=SimpleNamespace(run=Mock(side_effect=error))
        workspace.root=Mock();workspace.settings_button=Mock();workspace.output_entry=Mock()
        workspace._disable_actions=Mock();workspace.show_settings=Mock();workspace.status=Mock()
        args=crop.parser().parse_args(['input','blocked-results','--manual','--square'])
        with patch('tkinter.messagebox.showerror') as showerror:
            workspace._run_batch(args)
        self.assertFalse(workspace.busy)
        workspace.backend.run.assert_called_once_with(args,workspace=workspace)
        workspace.show_settings.assert_called_once()
        workspace.output_entry.focus_set.assert_called_once()
        self.assertTrue(args.manual and args.square)
        showerror.assert_called_once()


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

    def test_filter_and_image_list_keyboard_input_never_triggers_crop_shortcuts(self):
        workspace=CropWorkspace.__new__(CropWorkspace)
        workspace.busy=True
        callback=Mock()
        for widget_class in ('TCombobox','Treeview','Listbox','TEntry'):
            with self.subTest(widget_class=widget_class):
                event=SimpleNamespace(widget=SimpleNamespace(winfo_class=lambda:widget_class))
                workspace._shortcut(event,callback)
                callback.assert_not_called()


class ManualDetectionTests(unittest.TestCase):
    def make_workspace(self, result):
        workspace=CropWorkspace.__new__(CropWorkspace)
        args=crop.parser().parse_args(['input','output','--manual'])
        image=np.zeros((100,140,3),np.uint8)
        workspace.selection=CropSelection(image,args,crop)
        original=np.float32([[5,5],[130,5],[130,90],[5,90]])
        workspace.selection.set_corners(original)
        workspace.selection.manual_modified=True
        workspace.busy=True
        workspace.closed=False
        workspace.future=None
        workspace.current_index=1
        workspace.action=Mock(get=Mock(return_value='pending'))
        workspace.status=Mock()
        workspace._disable_actions=Mock()
        workspace._selection_changed=Mock()
        for name in ('skip_button','stop_button','pause_button','previous_button'):
            setattr(workspace,name,Mock())
        future=Mock(done=Mock(return_value=True),result=Mock(return_value=result))
        workspace.executor=Mock(submit=Mock(return_value=future))
        workspace.backend=crop
        return workspace,original

    def test_manual_detect_button_shows_proposal_without_saving(self):
        proposal=np.float32([[20,15],[120,15],[120,85],[20,85]])
        workspace,_=self.make_workspace(proposal)
        workspace.detect_current()
        np.testing.assert_allclose(workspace.selection.points,proposal)
        self.assertFalse(workspace.selection.manual_modified)
        self.assertEqual(workspace.automatic_quad,proposal.tolist())
        workspace.action.set.assert_not_called()

    def test_failed_manual_detection_keeps_existing_points(self):
        workspace,original=self.make_workspace(None)
        workspace.detect_current()
        np.testing.assert_allclose(workspace.selection.points,original)
        self.assertTrue(workspace.selection.manual_modified)
        self.assertIn('未找到可信边界',workspace.status.set.call_args.args[0])
        workspace.action.set.assert_not_called()


class DirectRecropTests(unittest.TestCase):
    def setUp(self):
        SelectionTests.setUp(self)
        self.selection.set_corners(np.float32(self.corners))
        self.workspace=CropWorkspace.__new__(CropWorkspace)
        self.workspace.selection=self.selection
        self.workspace.viewport=ImageViewport.fit((140,100),(500,400))
        self.workspace.future=self.workspace.drag_index=self.workspace.reselect_point=None
        self.workspace.pan_anchor=None
        self.workspace.space_down=False
        self.workspace.busy=True
        self.workspace.source_canvas=Mock()
        self.workspace.save_button=Mock()
        self.workspace.render_source=Mock()
        self.workspace._selection_changed=Mock()
        self.workspace._disable_actions=Mock()
        self.state={'value':'pending'}
        self.workspace.action=SimpleNamespace(get=lambda:self.state['value'],
                                              set=lambda v:self.state.update(value=v))

    def event(self, point):
        x,y=self.workspace.viewport.to_canvas(point)
        return SimpleNamespace(x=x,y=y)

    def click(self, point):
        event=self.event(point)
        self.workspace._click(event)
        self.workspace._release(event)

    def test_click_replaces_automatic_corners_and_enter_waits_for_four_new_points(self):
        new_corners=[(20,20),(120,20),(120,80),(20,80)]
        self.click(new_corners[0])
        np.testing.assert_allclose(self.selection.points,[new_corners[0]])
        self.assertIsNone(self.selection.preview)
        self.workspace._decide('save')
        self.assertEqual(self.state['value'],'pending')
        for point in new_corners[1:]:
            self.click(point)
        np.testing.assert_allclose(self.selection.accept()[0],new_corners)
        self.assertEqual(self.selection.preview.shape[:2],(100,100))
        self.workspace._decide('save')
        self.assertEqual(self.state['value'],'save')

    def test_click_handle_with_small_mouse_motion_starts_new_selection(self):
        point=self.corners[0]
        self.workspace._click(self.event(point))
        self.workspace._drag(self.event((0.25,0.25)))
        self.workspace._release(self.event((0.25,0.25)))
        np.testing.assert_allclose(self.selection.points,[point])
        self.assertIsNone(self.selection.accept())

    def test_drag_handle_keeps_four_corners_and_recalculates_preview_on_release(self):
        self.workspace._click(self.event(self.corners[0]))
        self.workspace._decide('save')
        self.assertEqual(self.state['value'],'pending')
        self.workspace._drag(self.event((10,10)))
        self.assertEqual(len(self.selection.points),4)
        self.assertIsNone(self.selection.preview)
        self.workspace._release(self.event((10,10)))
        self.assertIsNotNone(self.selection.accept())
        np.testing.assert_allclose(self.selection.points[0],(10,10))

    def test_margin_detection_and_completed_batch_clicks_leave_selection_unchanged(self):
        before=self.selection.accept()[1]
        self.workspace._click(SimpleNamespace(x=0,y=0))
        self.workspace.future=object()
        self.click((20,20))
        self.workspace.future=None
        self.workspace.busy=False
        self.click((20,20))
        np.testing.assert_allclose(self.selection.points,self.corners)
        np.testing.assert_array_equal(self.selection.preview,before)

    def test_space_drag_pans_without_restarting_or_modifying_the_crop(self):
        self.workspace.source_pil=Image.fromarray(self.image)
        self.workspace.navigation=ImageNavigation(zoom=3.)
        self.workspace.source_canvas.winfo_width.return_value=500
        self.workspace.source_canvas.winfo_height.return_value=400
        self.workspace.space_down=True
        before=self.selection.preview.copy()
        self.workspace._click(SimpleNamespace(x=200,y=180))
        self.workspace._drag(SimpleNamespace(x=245,y=210))
        self.workspace._release(SimpleNamespace(x=245,y=210))
        self.assertIsNone(self.workspace.pan_anchor)
        self.assertNotEqual(self.workspace.navigation.center,(70,50))
        np.testing.assert_allclose(self.selection.points,self.corners)
        np.testing.assert_array_equal(self.selection.preview,before)


class NavigationTests(unittest.TestCase):
    def test_pointer_anchor_and_source_coordinates_survive_zoom(self):
        nav=ImageNavigation()
        image_size,canvas_size=(4000,3000),(600,500)
        initial=nav.viewport(image_size,canvas_size)
        anchor=(240,210)
        original=initial.to_image(*anchor)
        nav.zoom_at(4,anchor,image_size,canvas_size)
        enlarged=nav.viewport(image_size,canvas_size)
        np.testing.assert_allclose(enlarged.to_image(*anchor),original)
        np.testing.assert_allclose(enlarged.to_image(*enlarged.to_canvas(original)),original)
        nav.reset()
        self.assertEqual(nav.viewport(image_size,canvas_size),initial)

    def test_panning_is_bounded_and_zoom_has_limits(self):
        nav=ImageNavigation()
        image_size,canvas_size=(1000,800),(500,400)
        nav.zoom_at(1000,(250,200),image_size,canvas_size)
        self.assertEqual(nav.zoom,16.)
        for direction in (-1,1):
            nav.pan(direction*100000,direction*100000,image_size,canvas_size)
            view=nav.viewport(image_size,canvas_size)
            self.assertLessEqual(view.x,24)
            self.assertLessEqual(view.y,24)
            self.assertGreaterEqual(view.x+view.width,476)
            self.assertGreaterEqual(view.y+view.height,376)
        nav.zoom_at(.0001,(250,200),image_size,canvas_size)
        self.assertEqual(nav.zoom,1.)

    def test_focus_enlarges_tiny_target_and_all_corners_remain_visible(self):
        points=[(180,210),(240,208),(242,272),(178,274)]
        before=list(points)
        nav=ImageNavigation()
        nav.focus(points,(2000,1500),(600,500))
        view=nav.viewport((2000,1500),(600,500))
        self.assertGreater(nav.zoom,5)
        for p in points:
            x,y=view.to_canvas(p)
            self.assertTrue(0<x<600 and 0<y<500)
        self.assertEqual(points,before)

    def test_recropping_at_high_zoom_still_stores_original_image_coordinates(self):
        case=DirectRecropTests()
        case.setUp()
        nav=ImageNavigation(zoom=4.)
        nav.pan(55,-20,(140,100),(500,400))
        case.workspace.viewport=nav.viewport((140,100),(500,400))
        case.click((60,40))
        np.testing.assert_allclose(case.selection.points,[(60,40)])
        self.assertIsNone(case.selection.accept())


if __name__=='__main__':
    unittest.main()
