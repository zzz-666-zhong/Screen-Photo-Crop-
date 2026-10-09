"""Behavioral regression tests; all images are synthetic and GUI calls are mocked."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

import screen_crop as crop
from examples.generate_demo import make_scene
from train_screen_model import overlap


ROOT = Path(__file__).resolve().parents[1]


class GeometryTests(unittest.TestCase):
    def test_clicking_recrop_discards_proposal_and_accepts_new_manual_points(self):
        image = np.full((120, 160, 3), 100, np.uint8)
        proposed = np.float32([[2, 2], [155, 2], [155, 115], [2, 115]])
        expected = np.float32([[20, 15], [140, 15], [140, 100], [20, 100]])
        callbacks = []
        passes = []

        def key_events(delay):
            mouse = callbacks[0]
            passes.append(True)
            if len(passes) == 1:
                mouse(cv2.EVENT_LBUTTONDOWN, 50, 82, None, None)
            else:
                for x, y in expected:
                    mouse(cv2.EVENT_LBUTTONDOWN, int(x), int(y) + 104, None, None)
            return 13

        with patch.object(cv2, "namedWindow"), \
                patch.object(cv2, "setMouseCallback", side_effect=lambda name, cb: callbacks.append(cb)), \
                patch.object(cv2, "imshow"), \
                patch.object(cv2, "waitKey", side_effect=key_events), \
                patch.object(cv2, "getWindowProperty", return_value=1), \
                patch.object(cv2, "destroyWindow"):
            selected = crop.choose_corners(image, proposed, "1/1")
        self.assertEqual(len(passes), 2)
        np.testing.assert_array_equal(selected, expected)

    def test_unordered_perspective_corners_produce_a_rectangle(self):
        image, quad = make_scene()
        result = crop.rectify(image, quad[[2, 0, 3, 1]])
        self.assertGreater(result.shape[1], result.shape[0])
        self.assertGreater(result.shape[0], 300)
        self.assertGreater(result.std(), 30)

    def test_degenerate_corners_are_rejected(self):
        with self.assertRaises(ValueError):
            crop.order_corners(np.float32([[1, 1], [1, 1], [5, 5], [8, 8]]))

    def test_default_preserves_dark_content_and_trimming_is_opt_in(self):
        image = np.zeros((100, 120, 3), np.uint8)
        image[10:90, 15:105] = (120, 70, 180)
        args = crop.parser().parse_args(["input", "output"])
        np.testing.assert_array_equal(crop.finish_crop(image, args), image)
        args.no_trim_black = False
        trimmed = crop.finish_crop(image, args)
        self.assertEqual(trimmed.shape, (80, 90, 3))

    def test_unicode_paths_and_exif_orientation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "屏幕照片.jpg"
            exif = Image.Exif()
            exif[274] = 6
            Image.new("RGB", (40, 20), (25, 100, 180)).save(source, exif=exif)
            loaded = crop.load_image(source)
            self.assertEqual(loaded.shape, (40, 20, 3))


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "原图"
        self.output = self.root / "结果"
        self.source.mkdir()
        self.image = np.full((120, 160, 3), (70, 130, 210), np.uint8)
        self.image[20:100, 30:130] = (15, 15, 15)
        self.first = np.float32([[5, 5], [150, 5], [150, 110], [5, 110]])
        self.second = np.float32([[25, 15], [135, 15], [135, 105], [25, 105]])

    def save_source(self, name="照片.png"):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)).save(path)
        return path

    def args(self, *options):
        return crop.parser().parse_args([str(self.source), str(self.output), *options])

    def report(self, manual=False):
        path = self.output / ("manual_crop_report.csv" if manual else "crop_report.csv")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_review_recrops_same_original_and_saves_only_final_selection(self):
        source = self.save_source()
        before = source.read_bytes()
        observed = []

        def select(image, proposed, title):
            np.testing.assert_array_equal(image, self.image)
            observed.append((proposed, title))
            return self.first if len(observed) == 1 else self.second

        def preview(image, title):
            # Neither accepting initial corners nor clicking Re-crop writes a crop.
            self.assertFalse((self.output / crop.SUCCESS_FOLDER / "照片.png_cropped.png").exists())
            return "recrop" if len(observed) == 1 else "save"

        with patch.object(crop, "detect_screen", return_value=self.first), \
                patch.object(crop, "choose_corners", side_effect=select), \
                patch.object(crop, "preview_crop", side_effect=preview):
            self.assertEqual(crop.run(self.args("--review", "--debug")), 0)
        self.assertEqual(len(observed), 2)
        self.assertIsNone(observed[1][0])
        self.assertEqual(observed[0][1], observed[1][1])
        target = self.output / crop.SUCCESS_FOLDER / "照片.png_cropped.png"
        np.testing.assert_array_equal(crop.load_image(target), crop.rectify(self.image, self.second))
        self.assertEqual(source.read_bytes(), before)
        self.assertTrue((self.output / "_debug" / crop.SUCCESS_FOLDER / target.name).exists())
        self.assertEqual(self.report()[0]["status"], "ok")

    def test_manual_mode_can_recrop_repeatedly_without_detection(self):
        self.save_source()
        with patch.object(crop, "detect_screen") as detect, \
                patch.object(crop, "choose_corners", side_effect=[self.first, self.second, self.first]) as choose, \
                patch.object(crop, "preview_crop", side_effect=["recrop", "recrop", "save"]):
            self.assertEqual(crop.run(self.args("--manual")), 0)
        detect.assert_not_called()
        self.assertEqual(choose.call_count, 3)
        self.assertTrue(all(call.args[1] is None for call in choose.call_args_list))

    def test_skip_after_recrop_preserves_failure_copy_without_output(self):
        source = self.save_source()
        with patch.object(crop, "choose_corners", side_effect=[self.first, None]), \
                patch.object(crop, "preview_crop", return_value="recrop"):
            self.assertEqual(crop.run(self.args("--manual")), 0)
        self.assertEqual(self.report()[0]["status"], "skipped")
        self.assertEqual((self.output / crop.FAILURE_FOLDER / source.name).read_bytes(), source.read_bytes())
        self.assertEqual(list((self.output / crop.SUCCESS_FOLDER).iterdir()), [])

    def test_preview_skip_does_not_replace_existing_output(self):
        self.save_source()
        target = self.output / crop.SUCCESS_FOLDER / "照片.png_cropped.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"previous crop")
        with patch.object(crop, "choose_corners", return_value=self.first), \
                patch.object(crop, "preview_crop", return_value="skip"):
            self.assertEqual(crop.run(self.args("--manual", "--overwrite")), 0)
        self.assertEqual(target.read_bytes(), b"previous crop")

    def test_retry_recrops_then_removes_only_the_failure_copy(self):
        source = self.save_source()
        failed = self.output / crop.FAILURE_FOLDER / source.name
        failed.parent.mkdir(parents=True)
        failed.write_bytes(source.read_bytes())
        args = crop.parser().parse_args([str(self.output), "--retry-failed"])
        with patch.object(crop, "choose_corners", side_effect=[self.first, self.second]), \
                patch.object(crop, "preview_crop", side_effect=["recrop", "save"]), \
                patch.object(crop, "detect_screen") as detect:
            self.assertEqual(crop.run(args), 0)
        detect.assert_not_called()
        self.assertFalse(failed.exists())
        self.assertTrue(source.exists())
        self.assertEqual(self.report(manual=True)[0]["status"], "ok")

    def test_automatic_batch_retains_nested_names_and_skips_existing(self):
        self.save_source("nested/photo.png")
        self.save_source("nested/photo.jpg")
        with patch.object(crop, "detect_screen", return_value=self.first), \
                patch.object(crop, "preview_crop") as preview:
            self.assertEqual(crop.run(self.args("--recursive")), 0)
        preview.assert_not_called()
        names = {path.name for path in (self.output / crop.SUCCESS_FOLDER / "nested").iterdir()}
        self.assertEqual(names, {"photo.png_cropped.png", "photo.jpg_cropped.png"})
        with patch.object(crop, "detect_screen") as detect:
            self.assertEqual(crop.run(self.args("--recursive")), 0)
        detect.assert_not_called()
        self.assertEqual({row["status"] for row in self.report()}, {"existing"})

    def test_corrupt_image_is_copied_to_failures(self):
        source = self.source / "corrupt.jpg"
        source.write_bytes(b"not an image")
        self.assertEqual(crop.run(self.args()), 1)
        self.assertEqual((self.output / crop.FAILURE_FOLDER / source.name).read_bytes(), b"not an image")
        self.assertEqual(self.report()[0]["status"], "error")

    def test_output_inside_input_is_not_reprocessed(self):
        self.output = self.source / "output"
        self.save_source()
        with patch.object(crop, "detect_screen", return_value=self.first):
            self.assertEqual(crop.run(self.args("--recursive")), 0)
            self.assertEqual(crop.run(self.args("--recursive")), 0)
        self.assertEqual(len(self.report()), 1)


class ModelAndCLITests(unittest.TestCase):
    def test_pretrained_model_detects_synthetic_screen_without_labels(self):
        image, expected = make_scene()
        detected = crop.detect_screen(image)
        self.assertIsNotNone(detected)
        self.assertGreater(overlap(detected, expected), .85)

    def test_model_metadata_and_weight_fingerprint(self):
        metadata = json.loads((ROOT / "screen_crop_model.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["features"], crop.FEATURE_NAMES)
        self.assertEqual(metadata["trees"], 240)
        digest = hashlib.sha256((ROOT / "screen_crop_forest.xml.gz").read_bytes()).hexdigest()
        self.assertIn(digest, (ROOT / "docs/MODEL_CARD.md").read_text(encoding="utf-8"))

    def test_entry_points_work_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            for script, option in (("screen_crop.py", "--help"),
                                   ("screen_crop.py", "--version"),
                                   ("train_screen_model.py", "--help")):
                result = subprocess.run([sys.executable, str(ROOT / script), option], cwd=directory,
                                        capture_output=True, text=True, encoding="utf-8", timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
