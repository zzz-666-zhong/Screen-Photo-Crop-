"""Synthetic border localization and confirmation-before-save regressions."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np
from PIL import Image

import screen_crop as crop
from crop_ui import CropWorkspace
from batch_state import LabelStore, OPTION_NAMES
from train_screen_model import overlap


def framed_scene(*,text=False,blur=False,glare=False):
    yy,xx=np.indices((700,1000))
    background=np.uint8(178+12*xx/1000+7*yy/700)
    scene=cv2.cvtColor(background,cv2.COLOR_GRAY2BGR)
    cv2.rectangle(scene,(0,0),(999,25),(7,7,7),-1)
    cv2.rectangle(scene,(0,650),(999,699),(7,7,7),-1)
    picture=np.full((340,360,3),184,np.uint8)
    if text:
        for i,line in enumerate(('throughput in mb','on the performance','proposed a method','the low complexity')):
            cv2.putText(picture,line,(-8,44+i*84),cv2.FONT_HERSHEY_SIMPLEX,.8,(35,35,35),2,cv2.LINE_AA)
    else:
        picture[:]=(38,65,45)
        for y in range(20,320,28):cv2.line(picture,(5,y),(355,y),(75,85,70),2)
        cv2.circle(picture,(185,90),27,(160,170,180),-1)
        cv2.rectangle(picture,(145,115),(225,260),(130,60,20),-1)
        # A nearly black subject touches the picture's bottom edge.
        cv2.fillConvexPoly(picture,np.int32([[150,220],[195,220],[140,339],[75,339]]),(5,5,5))
        cv2.fillConvexPoly(picture,np.int32([[195,220],[225,220],[290,339],[225,339]]),(5,5,5))
    cv2.rectangle(picture,(1,1),(358,338),(75,75,75),3)
    quad=np.float32([[330,165],[705,180],[690,540],[315,525]])
    matrix=cv2.getPerspectiveTransform(np.float32([[0,0],[359,0],[359,339],[0,339]]),quad)
    warped=cv2.warpPerspective(picture,matrix,(1000,700))
    mask=cv2.warpPerspective(np.full((340,360),255,np.uint8),matrix,(1000,700))
    scene[mask>0]=warped[mask>0]
    if glare:
        glow=np.exp(-((xx-535)**2/140**2+(yy-320)**2/180**2))*.22
        scene=np.uint8(scene*(1-glow[:,:,None])+230*glow[:,:,None])
    if blur:
        kernel=np.eye(5,dtype=np.float32)/5
        scene=cv2.filter2D(scene,-1,kernel)
    return scene,quad


class BlackBorderDetectionTests(unittest.TestCase):
    def test_square_fallback_requires_a_bigger_enclosing_plausible_proposal(self):
        image=np.zeros((600,800,3),np.uint8)
        partial=np.float32([[200,150],[500,150],[500,360],[200,360]])
        enclosing=np.float32([[200,105],[500,105],[500,405],[200,405]])
        unrelated=np.float32([[30,30],[120,30],[120,120],[30,120]])
        with patch('black_border.detect_black_frame',return_value=partial),patch.object(crop,'_detect_screen_general',return_value=enclosing) as general:
            np.testing.assert_allclose(crop.detect_black_border(image,square=True),enclosing)
            general.assert_called_once()
        with patch('black_border.detect_black_frame',return_value=partial),patch.object(crop,'_detect_screen_general',return_value=unrelated):
            np.testing.assert_allclose(crop.detect_black_border(image,square=True),partial)
        with patch('black_border.detect_black_frame',return_value=partial),patch.object(crop,'_detect_screen_general',side_effect=ValueError('unavailable')):
            np.testing.assert_allclose(crop.detect_black_border(image,square=True),partial)
        with patch('black_border.detect_black_frame',return_value=None),patch.object(crop,'_detect_screen_general') as general:
            self.assertIsNone(crop.detect_black_border(image,square=True))
            general.assert_not_called()

    def test_square_table_uses_outer_frame_instead_of_internal_cells(self):
        image=np.full((700,1000,3),185,np.uint8)
        picture=np.full((340,360,3),182,np.uint8)
        cv2.rectangle(picture,(1,1),(358,338),(120,120,120),3)
        for y in range(42,320,42):cv2.line(picture,(3,y),(356,y),(35,35,35),3)
        cv2.line(picture,(270,3),(270,336),(35,35,35),3)
        for y in range(30,330,42):cv2.putText(picture,'6:57 AM',(25,y),cv2.FONT_HERSHEY_SIMPLEX,.65,(30,30,30),2)
        expected=np.float32([[330,165],[705,180],[690,540],[315,525]])
        matrix=cv2.getPerspectiveTransform(np.float32([[0,0],[359,0],[359,339],[0,339]]),expected)
        warped=cv2.warpPerspective(picture,matrix,(1000,700))
        mask=cv2.warpPerspective(np.full((340,360),255,np.uint8),matrix,(1000,700))
        image[mask>0]=warped[mask>0]
        corners=crop.detect_black_border(image,square=True)
        self.assertIsNotNone(corners)
        self.assertGreater(overlap(corners,expected),.94)

    def test_dark_photo_keeps_whole_target_and_black_subject(self):
        image,expected=framed_scene()
        original=image.copy()
        corners=crop.detect_black_border(image)
        self.assertIsNotNone(corners)
        self.assertGreater(overlap(corners,expected),.94)
        args=crop.parser().parse_args(['input','output','--black-review'])
        self.assertTrue(args.no_trim_black)
        rectified=crop.rectify(image,corners)
        np.testing.assert_array_equal(crop.finish_crop(rectified,args),rectified)
        reference=crop.rectify(image,expected)
        self.assertGreater(np.mean(np.max(rectified[-15:],axis=2)<18),
                           .8*np.mean(np.max(reference[-15:],axis=2)<18))
        np.testing.assert_array_equal(image,original)

    def test_sparse_text_frame_is_localized_instead_of_a_text_line(self):
        image,expected=framed_scene(text=True)
        corners=crop.detect_black_border(image,square=True)
        self.assertIsNotNone(corners)
        self.assertGreater(overlap(corners,expected),.94)

    def test_non_square_frame_returns_original_pixels_after_detection_resize(self):
        image,expected=framed_scene(text=True)
        image=cv2.resize(image,(1400,560))
        expected=expected*np.float32([1.4,.8])
        corners=crop.detect_black_border(image)
        self.assertIsNotNone(corners)
        self.assertGreater(overlap(corners,expected),.94)

    def test_mild_diagonal_blur_and_local_reflection_keep_full_frame(self):
        for text in (False,True):
            with self.subTest(text=text):
                image,expected=framed_scene(text=text,blur=True,glare=True)
                corners=crop.detect_black_border(image)
                self.assertIsNotNone(corners)
                self.assertGreater(overlap(corners,expected),.92)

    def test_motion_blurred_text_frame_in_both_automatic_paths(self):
        image,expected=framed_scene(text=True,glare=True)
        image=cv2.filter2D(image,-1,np.eye(13,dtype=np.float32)/13)
        for detector in (crop.detect_black_border,crop.detect_screen):
            with self.subTest(detector=detector.__name__):
                corners=detector(image,square=True)
                self.assertIsNotNone(corners)
                self.assertGreater(overlap(corners,expected),.93)

    def test_normal_detection_includes_text_and_frame_without_forcing_square(self):
        for text in (True,False):
            image,expected=framed_scene(text=text,blur=True,glare=True)
            image=cv2.resize(image,(1400,560))
            expected=expected*np.float32([1.4,.8])
            corners=crop.detect_screen(image)
            self.assertIsNotNone(corners)
            self.assertGreater(overlap(corners,expected),.90)

    def test_plain_panel_bezel_and_missing_side_require_manual_points(self):
        image=np.full((650,950,3),185,np.uint8)
        cv2.rectangle(image,(10,10),(940,640),(0,0,0),15)
        self.assertIsNone(crop.detect_black_border(image))
        for a,b in (((300,170),(650,170)),((650,170),(650,500)),((650,500),(300,500))):
            cv2.line(image,a,b,(60,60,60),3)
        self.assertIsNone(crop.detect_black_border(image))
        self.assertIsNone(crop.detect_black_border(np.zeros((40,40,3),np.uint8)))

    def test_two_equal_separate_frames_are_ambiguous(self):
        image=np.full((600,1000,3),185,np.uint8)
        for x in (120,620):cv2.rectangle(image,(x,150),(x+260,410),(50,50,50),3)
        self.assertIsNone(crop.detect_black_border(image))
        self.assertIsNone(crop.detect_black_border(image,square=True))


class BlackReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.source,self.output=self.root/'photos',self.root/'results'
        self.source.mkdir()
        for index,name in enumerate(('a.png','b.png')):
            image,_=framed_scene(text=bool(index))
            Image.fromarray(image[:,:,::-1]).save(self.source/name)
        self.workspace=SimpleNamespace(aborted=False,batch_decision='',record=Mock(),
            selection_metadata=lambda:dict(manual_modified=False))
        self.workspace.begin_batch=lambda session,labels,args:self.workspace.__dict__.update(session=session)
        self.workspace.prepare_item=lambda index:self.workspace.__dict__.update(index=index,batch_decision='')
        self.workspace.restore_item=lambda digest,record:self.workspace.__dict__.update(digest=digest)

    def args(self,*extra):
        return crop.parser().parse_args([str(self.source),str(self.output),'--black-review',*extra])

    def test_each_photo_waits_for_review_and_only_confirmed_crop_is_written(self):
        calls=[]
        originals={path.name:path.read_bytes() for path in self.source.iterdir()}
        def review(image,proposed,args,title,**kwargs):
            index=self.workspace.index
            calls.append(index)
            self.assertTrue(kwargs['auto_detect'])
            name=('a.png','b.png')[index]
            self.assertFalse((self.output/crop.SUCCESS_FOLDER/(name+'_cropped.png')).exists())
            if index==1:return None
            corners=crop.detect_black_border(image)
            return corners,crop.finish_crop(crop.rectify(image,corners),args)
        self.workspace.review=review
        with patch.object(crop,'check_model_runtime',side_effect=AssertionError('No forest required')):
            self.assertEqual(crop.run(self.args(),workspace=self.workspace),0)
        self.assertEqual(calls,[0,1])
        self.assertTrue((self.output/crop.SUCCESS_FOLDER/'a.png_cropped.png').is_file())
        self.assertFalse((self.output/crop.SUCCESS_FOLDER/'b.png_cropped.png').exists())
        labels=LabelStore(self.output).data['items']
        self.assertEqual(len(labels),1)
        label=next(iter(labels.values()))
        self.assertTrue(label['confirmed'])
        self.assertEqual(label['model_version'],{'detector':'black-border-v2','fallback':'conditional-general'})
        for name,before in originals.items():self.assertEqual((self.source/name).read_bytes(),before)

    def test_pause_resume_restores_black_review_and_partial_points(self):
        def pause(image,*args,**kwargs):
            self.workspace.session.draft([[330,165]],modified=True,source_sha256=self.workspace.digest)
            self.workspace.batch_decision='pause'
        self.workspace.review=pause
        self.assertEqual(crop.run(self.args(),workspace=self.workspace),0)
        self.assertEqual(self.workspace.session.data['status'],'paused')
        visits=[]
        def review(image,proposed,args,title,**kwargs):
            visits.append(self.workspace.index)
            self.assertTrue(args.black_review)
            if self.workspace.index==0:
                self.assertEqual(self.workspace.session.drafts['a.png']['points'],[[330.,165.]])
            corners=crop.detect_black_border(image)
            return corners,crop.rectify(image,corners)
        self.workspace.review=review
        self.assertEqual(crop.run(self.args('--resume'),workspace=self.workspace),0)
        self.assertEqual(visits,[0,1])

    def test_ui_selects_specialist_and_passes_black_mode_to_start_and_resume(self):
        workspace=CropWorkspace.__new__(CropWorkspace)
        for name,value in dict(source='photos',output='results',workflow='black_review',shape='full',
                               recursive=False,overwrite=False,debug=False,trim=False).items():
            setattr(workspace,name,Mock(get=Mock(return_value=value)))
        workspace.backend=crop
        workspace.remember_settings,workspace._run_batch=Mock(),Mock()
        workspace._start()
        args=workspace._run_batch.call_args.args[0]
        self.assertTrue(args.black_review and args.no_trim_black)
        workspace.backend=SimpleNamespace(detect_black_border=Mock(return_value='frame'),detect_screen=Mock())
        self.assertEqual(workspace.detect_review_corners(None,args),'frame')
        workspace.backend.detect_screen.assert_not_called()
        workspace.backend=crop
        workspace.busy=False
        options={key:getattr(args,key) for key in OPTION_NAMES}
        with patch('crop_ui.read_json',return_value={'schema':1,'source':'photos','destination':'results','options':options}):
            workspace.resume_last()
        resumed=workspace._run_batch.call_args.args[0]
        self.assertTrue(resumed.black_review and resumed.resume)

    def test_black_review_is_exclusive_and_alias_is_supported(self):
        for flag in ('--manual','--review','--fixed','--retry-failed'):
            with self.subTest(flag=flag),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                self.args(flag)
        self.assertTrue(crop.parser().parse_args(['input','output','--black-border-review']).black_review)


if __name__=='__main__':
    unittest.main()
