"""Verify isolated setup, dependency repair, argument forwarding, and failure handling."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import launch_crop


class StartupTests(unittest.TestCase):
    def setUp(self):
        no_uv = patch.object(launch_crop.shutil, "which", return_value=None)
        no_uv.start()
        self.addCleanup(no_uv.stop)

    def test_valid_environment_does_not_install_anything(self):
        root = Path("project")
        with patch.object(launch_crop, "probe", return_value=(True, "ready")), \
                patch.object(launch_crop.subprocess, "run") as run:
            result = launch_crop.ensure_environment(root)
        self.assertEqual(result, launch_crop.environment_python(root.resolve()))
        run.assert_not_called()

    def test_missing_environment_is_created_and_dependencies_installed_in_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.object(launch_crop, "probe", side_effect=[(False, "missing"), (True, "ready")]), \
                    patch.object(launch_crop.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                python = launch_crop.ensure_environment(root)
            create, pip_check, install = [call.args[0] for call in run.call_args_list]
            self.assertEqual(create[1:3], ["-m", "venv"])
            self.assertEqual(create[3], str(root / ".crop-env"))
            self.assertEqual(install[:4], [str(python), "-m", "pip", "install"])
            self.assertEqual(install[-1], str(root / "requirements.txt"))

    def test_incompatible_environment_is_repaired_without_recreating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            python = launch_crop.environment_python(root)
            python.parent.mkdir(parents=True)
            python.write_bytes(b"placeholder")
            with patch.object(launch_crop, "probe", side_effect=[(False, "OpenCV 5"), (True, "ready")]), \
                    patch.object(launch_crop, "probe_python", return_value=True), \
                    patch.object(launch_crop.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertEqual(launch_crop.ensure_environment(root), python)
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args[0][1:4], ["-m", "pip", "install"])

    def test_interrupted_setup_recovers_missing_pip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            python = launch_crop.environment_python(root)
            python.parent.mkdir(parents=True)
            python.write_bytes(b"placeholder")
            with patch.object(launch_crop, "probe", side_effect=[(False, "missing pip"), (True, "ready")]), \
                    patch.object(launch_crop, "probe_python", return_value=True), \
                    patch.object(launch_crop.subprocess, "run",
                                 side_effect=[subprocess.CompletedProcess([], 1),
                                              subprocess.CompletedProcess([], 0),
                                              subprocess.CompletedProcess([], 0)]) as run:
                launch_crop.ensure_environment(root)
            self.assertEqual(run.call_args_list[1].args[0], [str(python), "-m", "ensurepip", "--upgrade"])

    def test_paths_and_review_flags_are_forwarded_without_shell_interpretation(self):
        root = Path("project").resolve()
        python = launch_crop.environment_python(root)
        argv = ["原图 with spaces", "结果", "--review", "--overwrite"]
        with patch.object(launch_crop, "ensure_environment", return_value=python), \
                patch.object(launch_crop.subprocess, "call", return_value=0) as call:
            self.assertEqual(launch_crop.run_application("screen_crop.py", argv, root), 0)
        self.assertEqual(call.call_args.args[0], [str(python), str(root / "screen_crop.py"), *argv])
        self.assertEqual(call.call_args.kwargs["cwd"], Path.cwd())
        self.assertNotIn("shell", call.call_args.kwargs)

    def test_existing_uv_installs_into_the_project_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            python = launch_crop.environment_python(root)
            python.parent.mkdir(parents=True)
            python.write_bytes(b"placeholder")
            with patch.object(launch_crop, "probe", side_effect=[(False, "missing"), (True, "ready")]), \
                    patch.object(launch_crop, "probe_python", return_value=True), \
                    patch.object(launch_crop.shutil, "which", return_value="uv.exe"), \
                    patch.object(launch_crop.subprocess, "run") as run:
                launch_crop.ensure_environment(root)
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0],
                             ["uv.exe", "pip", "install", "--python", str(python),
                              "-r", str(root / "requirements.txt")])

    def test_setup_only_does_not_open_the_application(self):
        with patch.object(launch_crop, "ensure_environment") as ensure, \
                patch.object(launch_crop, "run_application") as run:
            self.assertEqual(launch_crop.main(["--setup-only"]), 0)
        ensure.assert_called_once()
        run.assert_not_called()

    def test_failed_install_returns_an_actionable_error(self):
        with patch.object(launch_crop, "ensure_environment",
                          side_effect=subprocess.CalledProcessError(1, ["pip", "install"])):
            self.assertEqual(launch_crop.main(["--setup-only"]), 2)

    def test_installed_runtime_satisfies_the_project_requirements(self):
        self.assertIsNone(launch_crop.runtime_problem())


if __name__ == "__main__":
    unittest.main()
