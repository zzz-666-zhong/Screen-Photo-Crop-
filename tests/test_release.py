"""Check release boundaries and metadata without publishing anything."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_release import ROOT, application_metadata, build, release_files, validate_links


class ReleaseTests(unittest.TestCase):
    def test_release_files_exclude_local_inputs_and_include_runtime_assets(self):
        files = release_files(ROOT)
        names = {p.relative_to(ROOT).as_posix() for p in files}
        for required in ("screen_crop.py", "white_border.py", "black_border.py", "crop_ui.py", "batch_state.py", "batch_status.py", "train_screen_model.py", "screen_crop_model.json",
                         "screen_crop_forest.xml.gz", "screen_crop_reflection.xml.gz",
                         "extreme_review_model/screen_crop_model.json", "extreme_review_model/screen_crop_forest.xml.gz",
                         "requirements.txt", "启动裁剪.cmd", "LICENSE"):
            self.assertIn(required, names)
        excluded = {"原图", "结果", "结果2", "识别提升结果", ".crop-env", ".venv", "dist", "github-release"}
        self.assertTrue(all(not excluded.intersection(Path(name).parts) for name in names))
        validate_links(ROOT, files)

    def test_archive_checksums_and_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = build(ROOT, Path(directory))
            checksum = archive_path.with_suffix(".zip.sha256").read_text(encoding="ascii").split()[0]
            self.assertEqual(checksum, hashlib.sha256(archive_path.read_bytes()).hexdigest())
            version, _ = application_metadata(ROOT)
            prefix = f"screen-photo-crop-v{version}/"
            with zipfile.ZipFile(archive_path) as archive:
                manifest = json.loads(archive.read(prefix + "release-manifest.json"))
                self.assertEqual(len(archive.namelist()), len(manifest["files"]) + 1)
                for name, record in manifest["files"].items():
                    payload = archive.read(prefix + name)
                    self.assertEqual(len(payload), record["bytes"])
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), record["sha256"])
            with self.assertRaises(FileExistsError):
                build(ROOT, Path(directory))

    def test_manifest_rejects_parent_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "release-files.txt").write_text("../outside.txt\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsafe release path"):
                release_files(root)


if __name__ == "__main__":
    unittest.main()
