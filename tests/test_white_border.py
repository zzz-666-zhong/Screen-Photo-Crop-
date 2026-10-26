"""Behavior checks for light backgrounds without private source photos."""
import unittest
from unittest.mock import patch
import cv2
import numpy as np
import screen_crop as crop
from white_border import detect_light_picture,light_background
from examples.white_border_scenes import make_scene,KINDS
from examples.generate_demo import make_scene as original_scene
from train_screen_model import overlap


class WhiteBorderTests(unittest.TestCase):
    def test_vectorized_features_keep_the_existing_forest_input_contract(self):
        image,quad=original_scene()
        small,scale,gray,hsv,texture,gradients=crop.photo_evidence(image)
        actual=crop.quad_features(small,gray,hsv[:,:,1],texture,gradients,quad*scale)
        expected=np.float32([.98987615,-1.35350454,.43041426,.93478060,.76367420,0,
            .13887762,.38058388,0,.20149450,0,2.20384479,1.50967467,1.33406782,
            1,.17689282,.12154404,0,.44734713,.60392159,.11182379,0,.13079667,.20039216])
        np.testing.assert_allclose(actual,expected,rtol=.003,atol=.001)

    def test_whole_picture_includes_white_margin_faint_side_and_text(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                image,expected=make_scene(kind,41)
                before=image.copy()
                actual=crop.detect_screen(image,square=kind!='portrait')
                self.assertIsNotNone(actual)
                self.assertGreater(overlap(actual,expected),.85)
                np.testing.assert_array_equal(image,before)

    def test_blank_background_and_flat_panel_have_no_light_picture(self):
        for background in (155,195,230):
            image=np.full((600,840,3),background,np.uint8)
            cv2.rectangle(image,(220,150),(570,470),(90,90,90),-1)
            self.assertIsNone(detect_light_picture(image,crop.order_corners,square=True))

    def test_light_route_skips_forests_and_dark_background_uses_general_detector(self):
        image,_=make_scene('white-frame',67)
        with patch.object(crop,'photo_candidates',side_effect=AssertionError('Unnecessary general pass')):
            self.assertIsNotNone(crop.detect_screen(image,square=True))
        self.assertIsNone(light_background(np.full((600,840,3),35,np.uint8)))

    def test_two_separate_similar_pictures_are_ambiguous(self):
        rng=np.random.default_rng(14)
        image=np.full((600,1000,3),195,np.uint8)
        picture=rng.integers(25,180,(210,210,3),dtype=np.uint8)
        image[170:380,150:360]=picture
        image[170:380,650:860]=picture
        self.assertIsNone(detect_light_picture(image,crop.order_corners,square=True))


if __name__=='__main__':unittest.main()
