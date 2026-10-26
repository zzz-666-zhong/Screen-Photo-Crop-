"""Exercise persistence, navigation, and reviewed-label exports across real files."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from PIL import Image

import screen_crop as crop
from batch_state import (LabelStore, fingerprint, load_preferences, atomic_json,
                         prepare_output_directories, OutputDirectoryError)
from crop_ui import CropSelection
from train_screen_model import read_dataset


class BatchStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'原图';self.output=self.root/'结果'
        self.source.mkdir()
        for index,name in enumerate(('a.png','b.png','c.png')):
            Image.new('RGB',(160,120),(60+index*30,90,180)).save(self.source/name)
        self.quad=np.float32([[10,10],[150,10],[150,110],[10,110]])
        self.changed=np.float32([[30,20],[130,20],[130,100],[30,100]])
        self.workspace=SimpleNamespace(aborted=False,batch_decision='',record=lambda *a:None,
            selection_metadata=lambda:dict(manual_modified=True))
        self.workspace.begin_batch=lambda session,labels,args:self.workspace.__dict__.update(session=session,labels=labels,args=args)
        self.workspace.prepare_item=lambda index:self.workspace.__dict__.update(index=index,batch_decision='')
        self.workspace.restore_item=lambda digest,record:self.workspace.__dict__.update(digest=digest,record_data=record)

    def args(self,*extra):
        return crop.parser().parse_args([str(self.source),str(self.output),'--manual',*extra])

    def test_output_preflight_uses_real_writes_without_changing_existing_files(self):
        self.output.mkdir()
        original=self.output/'crop_session.json'
        original.write_bytes(b'previous checkpoint')
        directories=[self.output,self.output/crop.SUCCESS_FOLDER,self.output/crop.FAILURE_FOLDER]
        prepare_output_directories(directories)
        self.assertEqual(original.read_bytes(),b'previous checkpoint')
        self.assertTrue(all(folder.is_dir() for folder in directories))
        self.assertEqual(list(self.output.rglob('.screen-crop-check-*')),[])

    def test_denied_success_folder_does_not_replace_checkpoint_or_start_review(self):
        self.output.mkdir()
        checkpoint=self.output/'crop_session.json';checkpoint.write_bytes(b'keep progress')
        # Hosted Windows temp paths may use short names or junction aliases;
        # run_batch resolves paths before invoking the filesystem operation.
        denied_directory=(self.output/crop.SUCCESS_FOLDER).resolve()
        mkdir=Path.mkdir
        def guarded(path,*args,**kwargs):
            if path.resolve()==denied_directory:
                raise PermissionError(13,'Access denied',str(path))
            return mkdir(path,*args,**kwargs)
        with patch.object(Path,'mkdir',new=guarded),patch.object(self.workspace,'review',create=True) as review:
            with self.assertRaises(OutputDirectoryError) as error:
                crop.run(self.args(),workspace=self.workspace)
        self.assertEqual(error.exception.directory,denied_directory)
        self.assertIn('启动裁剪.cmd',str(error.exception))
        self.assertEqual(checkpoint.read_bytes(),b'keep progress')
        review.assert_not_called()

    def test_denied_probe_rename_is_reported_and_cleans_unique_files(self):
        with patch.object(Path,'replace',side_effect=PermissionError(13,'Access denied')):
            with self.assertRaises(OutputDirectoryError):prepare_output_directories([self.output])
        self.assertEqual(list(self.output.iterdir()),[])

    def test_denied_file_creation_fails_once_even_when_access_check_says_writable(self):
        self.output.mkdir()
        original=self.output/'crop_session.json';original.write_bytes(b'preserved checkpoint')
        real_open=Path.open
        attempts=[]
        def denied(path,mode='r',*args,**kwargs):
            if mode in ('x','xb'):
                attempts.append(path)
                raise PermissionError(13,'Access denied',str(path))
            return real_open(path,mode,*args,**kwargs)
        with patch.object(Path,'open',new=denied),patch('os.access',return_value=True):
            with self.assertRaises(OutputDirectoryError):prepare_output_directories([self.output])
            self.assertEqual(len(attempts),1)
            with self.assertRaises(PermissionError):atomic_json(original,{'replacement':True})
        self.assertEqual(len(attempts),2)
        self.assertEqual(original.read_bytes(),b'preserved checkpoint')
        self.assertEqual(list(self.output.iterdir()),[original])

    def test_output_path_occupied_by_a_file_reports_conflict_and_retains_file(self):
        self.output.write_bytes(b'not a directory')
        with self.assertRaisesRegex(OutputDirectoryError,'同名文件'):
            prepare_output_directories([self.output/crop.SUCCESS_FOLDER])
        self.assertEqual(self.output.read_bytes(),b'not a directory')

    def result(self,image,quad=None):
        quad=self.quad if quad is None else quad
        return quad,crop.rectify(image,quad)

    def test_pause_resume_restores_partial_selection_and_keeps_completed_outputs(self):
        original=(self.source/'a.png').read_bytes()
        def first(image,*a,**kw):
            if self.workspace.index==0:return self.result(image)
            self.workspace.session.draft(self.changed[:2],modified=True,source_sha256=self.workspace.digest)
            self.workspace.batch_decision='pause'
        self.workspace.review=first
        self.assertEqual(crop.run(self.args(),workspace=self.workspace),0)
        saved=(self.output/crop.SUCCESS_FOLDER/'a.png_cropped.png').read_bytes()
        self.assertEqual(self.workspace.session.data['status'],'paused')
        visits=[]
        def resumed(image,*a,**kw):
            visits.append(self.workspace.index)
            if self.workspace.index==1:
                draft=self.workspace.session.drafts['b.png']
                np.testing.assert_allclose(draft['points'],self.changed[:2])
            return self.result(image)
        self.workspace.review=resumed
        self.assertEqual(crop.run(self.args('--resume'),workspace=self.workspace),0)
        self.assertEqual(visits,[1,2])
        self.assertEqual((self.output/crop.SUCCESS_FOLDER/'a.png_cropped.png').read_bytes(),saved)
        self.assertEqual((self.source/'a.png').read_bytes(),original)
        export=self.root/'labels.json'
        self.assertEqual(LabelStore(self.output).export(export),3)
        rows=read_dataset(export)
        self.assertTrue(all(r['manual_modified'] for r in rows))
        self.assertTrue(all(r['application_version']==crop.__version__ for r in rows))

    def test_previous_replaces_only_confirmed_crop_and_updates_one_label_per_original(self):
        visits=[]
        def review(image,*a,**kw):
            index=self.workspace.index;visits.append(index)
            if visits==[0,1]:
                self.workspace.session.draft(self.changed[:2],modified=True,source_sha256=self.workspace.digest)
                self.workspace.batch_decision='jump';self.workspace.requested_index=0;return
            return self.result(image,self.changed if visits==[0,1,0] else None)
        self.workspace.review=review
        self.assertEqual(crop.run(self.args(),workspace=self.workspace),0)
        self.assertEqual(visits,[0,1,0,1,2])
        row=LabelStore(self.output).data['items'][fingerprint(self.source/'a.png')]
        np.testing.assert_allclose(row['quad'],self.changed)
        self.assertEqual(len(LabelStore(self.output).data['items']),3)
        actual=crop.load_image(self.output/crop.SUCCESS_FOLDER/'a.png_cropped.png')
        np.testing.assert_array_equal(actual,crop.rectify(crop.load_image(self.source/'a.png'),self.changed))

    def test_skipping_a_revisited_crop_preserves_previous_pixels_and_label(self):
        visits=[];saved={}
        def review(image,*a,**kw):
            index=self.workspace.index;visits.append(index)
            if visits==[0,1]:
                saved['bytes']=(self.output/crop.SUCCESS_FOLDER/'a.png_cropped.png').read_bytes()
                self.workspace.batch_decision='jump';self.workspace.requested_index=0;return
            if visits==[0,1,0]:return None
            return self.result(image)
        self.workspace.review=review
        self.assertEqual(crop.run(self.args(),workspace=self.workspace),0)
        self.assertEqual((self.output/crop.SUCCESS_FOLDER/'a.png_cropped.png').read_bytes(),saved['bytes'])
        self.assertFalse((self.output/crop.FAILURE_FOLDER/'a.png').exists())
        np.testing.assert_allclose(LabelStore(self.output).data['items'][fingerprint(self.source/'a.png')]['quad'],self.quad)

    def test_pausing_an_edit_of_saved_crop_then_skipping_after_restart_retains_it(self):
        visits=[]
        def initial(image,*a,**kw):
            visits.append(self.workspace.index)
            if visits==[0]:return self.result(image)
            if visits==[0,1]:
                self.workspace.batch_decision='jump';self.workspace.requested_index=0;return
            self.workspace.session.draft(self.changed[:1],modified=True,source_sha256=self.workspace.digest)
            self.workspace.batch_decision='pause'
        self.workspace.review=initial
        crop.run(self.args(),workspace=self.workspace)
        target=self.output/crop.SUCCESS_FOLDER/'a.png_cropped.png';before=target.read_bytes()
        self.assertTrue(self.workspace.session.records['a.png']['saved'])
        def resumed(image,*a,**kw):
            if self.workspace.index==0:return None
            return self.result(image)
        self.workspace.review=resumed
        self.assertEqual(crop.run(self.args('--resume'),workspace=self.workspace),0)
        self.assertEqual(target.read_bytes(),before)
        self.assertEqual(self.workspace.session.records['a.png']['status'],'ok')
        self.assertEqual(LabelStore(self.output).export(self.root/'labels.json'),3)

    def test_automatic_results_are_not_exported_as_human_confirmed_labels(self):
        args=crop.parser().parse_args([str(self.source),str(self.output)])
        with patch.object(crop,'detect_screen',return_value=self.quad):
            self.assertEqual(crop.run(args),0)
        with self.assertRaisesRegex(ValueError,'human-confirmed'):LabelStore(self.output).export(self.root/'labels.json')

    def test_changed_original_blocks_label_export_and_resume_options_must_match(self):
        self.workspace.review=lambda image,*a,**kw:self.result(image)
        crop.run(self.args(),workspace=self.workspace)
        Image.new('RGB',(160,120),'black').save(self.source/'a.png')
        with self.assertRaisesRegex(ValueError,'missing or changed'):LabelStore(self.output).export(self.root/'labels.json')
        with self.assertRaisesRegex(ValueError,'saved source and crop options'):
            crop.run(self.args('--resume','--square'),workspace=self.workspace)

    def test_retry_retains_training_source_and_can_revisit_after_failure_copy_is_removed(self):
        failure=self.output/crop.FAILURE_FOLDER;failure.mkdir(parents=True)
        for path in self.source.iterdir():(failure/path.name).write_bytes(path.read_bytes())
        args=crop.parser().parse_args([str(self.output),'--retry-failed'])
        visits=[]
        def review(image,*a,**kw):
            visits.append(self.workspace.index)
            if visits==[0,1]:
                self.workspace.batch_decision='jump';self.workspace.requested_index=0;return
            return self.result(image)
        self.workspace.review=review
        self.assertEqual(crop.run(args,workspace=self.workspace),0)
        self.assertEqual(visits,[0,1,0,1,2])
        self.assertEqual(list(failure.iterdir()),[])
        self.assertEqual(LabelStore(self.output).export(self.root/'labels.json'),3)
        args.resume=True
        self.workspace.review=lambda *a,**kw:self.fail('Completed retry must not revisit without navigation')
        self.assertEqual(crop.run(args,workspace=self.workspace),0)
        self.assertEqual(len(self.workspace.session.records),3)

    def test_preferences_roundtrip_and_corrupt_file_falls_back_without_crashing(self):
        path=self.root/'.crop-settings.json'
        data=dict(source=str(self.source),output=str(self.output),workflow='manual',shape='square')
        atomic_json(path,data)
        self.assertEqual(load_preferences(path),data)
        path.write_text('{broken',encoding='utf-8')
        self.assertEqual(load_preferences(path),{})


if __name__=='__main__':unittest.main()
