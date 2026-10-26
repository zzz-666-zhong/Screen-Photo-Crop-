"""Exercise one-confirmation exports, pixel coordinates, and restart behavior."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

import screen_crop as crop
from batch_state import LabelStore, fingerprint
from crop_ui import CropWorkspace


class FixedBatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source, self.output = self.root/'photos', self.root/'results'
        self.source.mkdir()
        y, x = np.indices((120,160))
        for index, name in enumerate(('a.png','b.png','c.png')):
            rgb = np.stack(((x+index*25)%256, y*2, (x+y)%256),axis=-1).astype(np.uint8)
            Image.fromarray(rgb).save(self.source/name)
        self.quad = np.float32([[15,12],[144,16],[149,103],[10,106]])
        self.workspace = SimpleNamespace(aborted=False, paused=False, closed=False,
            batch_decision='', requested_index=None, record=Mock(),
            selection_metadata=lambda:dict(manual_modified=True),
            fixed_batch_tick=Mock(), show_fixed_result=Mock())
        self.workspace.begin_batch = lambda session,labels,args: self.workspace.__dict__.update(
            session=session, labels=labels)
        self.workspace.prepare_item = lambda index: self.workspace.__dict__.update(
            index=index, requested_index=None, batch_decision='')
        self.workspace.restore_item = Mock()
        def confirm(image, proposed, args, title, **kwargs):
            return self.quad.copy(), crop.finish_crop(crop.rectify(image,self.quad,square=args.square),args)
        self.workspace.review = Mock(side_effect=confirm)

    def args(self,*extra):
        return crop.parser().parse_args([str(self.source),str(self.output),'--fixed',*extra])

    def test_one_confirmation_exports_identical_source_coordinates_without_detection(self):
        originals = {p.name:p.read_bytes() for p in self.source.iterdir()}
        with patch.object(crop,'detect_screen',side_effect=AssertionError('No repeated detection')):
            self.assertEqual(crop.run(self.args('--square'),workspace=self.workspace),0)
        self.assertEqual(self.workspace.review.call_count,1)
        self.assertEqual(self.workspace.show_fixed_result.call_count,2)
        for name, before in originals.items():
            image = crop.load_image(self.source/name)
            expected = crop.finish_crop(crop.rectify(image,self.quad,square=True),self.args('--square'))
            actual = crop.load_image(self.output/crop.SUCCESS_FOLDER/(name+'_cropped.png'))
            np.testing.assert_array_equal(actual,expected)
            self.assertEqual((self.source/name).read_bytes(),before)
        session = self.workspace.session.data
        self.assertEqual(session['status'],'complete')
        self.assertEqual(session['fixed_coordinates']['anchor_file'],'a.png')
        np.testing.assert_allclose(session['fixed_coordinates']['quad'],self.quad)
        self.assertEqual(session['fixed_coordinates']['image_size'],[160,120])
        labels = LabelStore(self.output)
        self.assertEqual(sum(row['confirmed'] for row in labels.data['items'].values()),1)
        self.assertEqual(labels.export(self.root/'reviewed.json'),1)
        self.assertFalse(labels.data['items'][fingerprint(self.source/'b.png')]['manual_modified'])

    def test_pause_and_restart_reuse_template_without_another_confirmation(self):
        self.workspace.fixed_batch_tick.side_effect = lambda: setattr(self.workspace,'paused',True)
        self.assertEqual(crop.run(self.args(),workspace=self.workspace),0)
        saved = self.output/crop.SUCCESS_FOLDER/'a.png_cropped.png'
        before, modified = saved.read_bytes(), saved.stat().st_mtime_ns
        self.assertEqual(self.workspace.session.data['status'],'paused')
        self.assertEqual(self.workspace.session.index,1)
        self.assertFalse((self.output/crop.SUCCESS_FOLDER/'b.png_cropped.png').exists())
        self.workspace.paused = False
        self.workspace.fixed_batch_tick.side_effect = None
        self.workspace.review.side_effect = AssertionError('Resume must not review again')
        self.assertEqual(crop.run(self.args('--resume'),workspace=self.workspace),0)
        self.assertEqual(saved.read_bytes(),before)
        self.assertEqual(saved.stat().st_mtime_ns,modified)
        self.assertEqual(self.workspace.session.data['status'],'complete')
        self.assertEqual(len(self.workspace.session.records),3)

    def test_stop_between_exports_leaves_remaining_inputs_pending(self):
        self.workspace.fixed_batch_tick.side_effect = lambda: setattr(self.workspace,'aborted',True)
        self.assertEqual(crop.run(self.args(),workspace=self.workspace),0)
        self.assertEqual(self.workspace.session.data['status'],'stopped')
        self.assertTrue(self.workspace.session.pending(1))
        self.assertEqual(list((self.output/crop.FAILURE_FOLDER).iterdir()),[])
        self.assertEqual(self.workspace.review.call_count,1)

    def test_different_image_size_is_reported_without_scaling_or_extra_review(self):
        Image.new('RGB',(320,240),'white').save(self.source/'b.png')
        self.assertEqual(crop.run(self.args(),workspace=self.workspace),1)
        records = self.workspace.session.records
        self.assertEqual([records[n]['status'] for n in ('a.png','b.png','c.png')],['ok','error','ok'])
        self.assertIn('expected 160x120, got 320x240',records['b.png']['detail'])
        self.assertTrue((self.output/crop.FAILURE_FOLDER/'b.png').is_file())
        self.assertEqual(self.workspace.review.call_count,1)

    def test_invalid_reference_does_not_lock_remaining_photos_to_bad_corners(self):
        def confirm(image,proposed,args,title,**kwargs):
            quad = self.quad.copy()
            if self.workspace.index==0:quad[0,0]=-5
            return quad,crop.rectify(image,quad)
        self.workspace.review.side_effect = confirm
        self.assertEqual(crop.run(self.args(),workspace=self.workspace),1)
        self.assertEqual(self.workspace.review.call_count,2)
        self.assertEqual(self.workspace.session.data['fixed_coordinates']['anchor_file'],'b.png')
        self.assertEqual(self.workspace.session.records['c.png']['status'],'ok')

    def test_old_checkpoints_resume_and_fixed_mode_requires_matching_options(self):
        args = crop.parser().parse_args([str(self.source),str(self.output),'--manual'])
        crop.run(args,workspace=self.workspace)
        checkpoint = self.output/'crop_session.json'
        data = json.loads(checkpoint.read_text(encoding='utf-8'))
        del data['options']['fixed']
        checkpoint.write_text(json.dumps(data),encoding='utf-8')
        args.resume = True
        self.workspace.review.side_effect = AssertionError('Completed records must be retained')
        self.assertEqual(crop.run(args,workspace=self.workspace),0)
        with self.assertRaisesRegex(ValueError,'saved source and crop options'):
            crop.run(self.args('--resume'),workspace=self.workspace)

    def test_bad_saved_coordinates_fail_before_any_further_export(self):
        self.workspace.fixed_batch_tick.side_effect = lambda: setattr(self.workspace,'paused',True)
        crop.run(self.args(),workspace=self.workspace)
        checkpoint = self.output/'crop_session.json'
        data = json.loads(checkpoint.read_text(encoding='utf-8'))
        data['fixed_coordinates']['quad'][0][0] = -10
        checkpoint.write_text(json.dumps(data),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Invalid fixed coordinates'):
            crop.run(self.args('--resume'),workspace=self.workspace)
        self.assertFalse((self.output/crop.SUCCESS_FOLDER/'b.png_cropped.png').exists())

    def test_fixed_is_exclusive_with_other_review_modes(self):
        for flag in ('--manual','--review','--retry-failed'):
            with self.subTest(flag=flag), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.args(flag)
        self.assertTrue(crop.parser().parse_args(['input','output','--fixed-coordinates']).fixed)


class FixedWorkspaceTests(unittest.TestCase):
    def test_fixed_thumbnails_do_not_overwrite_crops_by_starting_another_run(self):
        workspace = CropWorkspace.__new__(CropWorkspace)
        workspace.batch_args = SimpleNamespace(fixed=True)
        workspace.session = SimpleNamespace(files=['a.png'])
        workspace.status, workspace._run_batch = Mock(), Mock()
        workspace.jump_to(0)
        workspace._run_batch.assert_not_called()
        workspace.status.set.assert_called_once()

    def test_settings_start_passes_fixed_flag_and_selected_options(self):
        workspace = CropWorkspace.__new__(CropWorkspace)
        for name,value in dict(source='photos',output='results',workflow='fixed',shape='square',
                               recursive=True,overwrite=False,debug=False,trim=False).items():
            setattr(workspace,name,Mock(get=Mock(return_value=value)))
        workspace.backend = crop
        workspace.remember_settings, workspace._run_batch = Mock(), Mock()
        workspace._start()
        args = workspace._run_batch.call_args.args[0]
        self.assertTrue(args.fixed and args.square and args.recursive)
        self.assertFalse(args.manual or args.review or args.overwrite)

    def test_export_event_pump_clears_review_selection_before_pause(self):
        workspace = CropWorkspace.__new__(CropWorkspace)
        workspace.closed = False
        workspace.selection = object()
        workspace.action,workspace.status,workspace.root = Mock(),Mock(),Mock()
        workspace.stop_button,workspace.pause_button,workspace.previous_button = Mock(),Mock(),Mock()
        workspace._disable_actions = Mock()
        def update():
            self.assertIsNone(workspace.selection)
            workspace.paused = True
        workspace.root.update.side_effect = update
        workspace.fixed_batch_tick()
        self.assertTrue(workspace.paused)
        workspace.stop_button.configure.assert_called_with(state='normal')


if __name__=='__main__':
    unittest.main()
