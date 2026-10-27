"""Verify actual output files, outstanding images and batch progress agree."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from batch_status import existing_crops, image_state, matches_filter, progress_summary


class ProgressTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.names=['a.jpg','nested/b.jpg','c.jpg','d.jpg','e.jpg','f.jpg']
        self.records={'c.jpg':{'status':'error'},'d.jpg':{'status':'skipped'},'e.jpg':{'status':'ok'}}
        self.drafts={'nested/b.jpg':{'points':[[1,2]]}}
        self.session=SimpleNamespace(destination=self.root,names=self.names,records=self.records,drafts=self.drafts)
        self.session.pending=lambda i:self.names[i] in self.drafts or self.records.get(self.names[i],{}).get('status') not in ('ok','existing','skipped','error')
        output=self.root/'裁剪成功'
        output.mkdir()
        (output/'a.jpg_cropped.png').write_bytes(b'old result')
        (output/'c.jpg_cropped.png').write_bytes(b'old result')
        (output/'unrelated.jpg_cropped.png').write_bytes(b'not a source')

    def test_existing_outputs_and_unprocessed_states_are_distinct(self):
        saved=existing_crops(self.root,self.names)
        self.assertEqual(saved,{'a.jpg','c.jpg'})
        self.assertEqual([image_state(self.session,i,saved) for i in range(6)],
                         ['saved','draft','saved_error','skipped','missing','pending'])
        summary=progress_summary(self.session,saved)
        self.assertEqual(summary,dict(total=6,cropped=2,uncropped=4,processed=3,skipped=1,errors=1,drafts=1))
        self.assertEqual([self.names[i] for i in range(6) if matches_filter(self.session,i,saved,'uncropped')],
                         ['nested/b.jpg','d.jpg','e.jpg','f.jpg'])
        self.assertEqual([self.names[i] for i in range(6) if matches_filter(self.session,i,saved,'error')],['c.jpg'])

    def test_refresh_sees_new_nested_output_and_missing_output(self):
        saved=existing_crops(self.root,self.names)
        nested=self.root/'裁剪成功'/'nested'
        nested.mkdir()
        (nested/'b.jpg_cropped.png').write_bytes(b'cropped')
        (self.root/'裁剪成功'/'a.jpg_cropped.png').unlink()
        refreshed=existing_crops(self.root,self.names)
        self.assertEqual(refreshed,{'nested/b.jpg','c.jpg'})
        self.assertEqual(image_state(self.session,1,refreshed),'saved_draft')
        self.assertEqual(image_state(self.session,0,refreshed),'pending')
        self.assertNotEqual(saved,refreshed)


if __name__=='__main__':
    unittest.main()
