"""Prepare an isolated runtime and launch the cropper (standard library only)."""

from __future__ import annotations

import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEPENDENCIES = {
    "numpy": ((1, 24), (3, 0)),
    "opencv-python": ((4, 8), (5, 0)),
    "Pillow": ((10, 0), (13, 0)),
}


def runtime_problem() -> str | None:
    """Detect missing dependencies and incompatible OpenCV installations."""
    if sys.version_info < (3, 10):
        return "需要 Python 3.10 或更新版本 / Python 3.10+ is required."
    for name, (minimum, maximum) in DEPENDENCIES.items():
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return f"缺少依赖 / Missing dependency: {name}"
        numbers = re.findall(r"\d+", installed)
        version = tuple(int(n) for n in numbers[:2])
        if not minimum <= version < maximum:
            return f"依赖版本不兼容 / Incompatible dependency: {name} {installed}"
    try:
        import cv2
        import numpy
        from PIL import Image, ImageTk
        import tkinter as tk
        if not callable(getattr(getattr(cv2, "ml", None), "RTrees_create", None)):
            return "OpenCV 缺少随机森林模块 / OpenCV is missing ml.RTrees_create."
        tk.Tcl()
    except Exception as exc:
        return f"无法加载运行环境 / Runtime import failed: {exc}"
    return None


def environment_python(root: Path) -> Path:
    relative = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return root / ".crop-env" / relative


def probe(python: Path, root: Path) -> tuple[bool, str]:
    if not python.is_file():
        return False, "项目独立环境尚未安装 / The project environment is not installed."
    code = (
        "import sys; sys.path.insert(0, " + repr(str(root)) + "); "
        "from launch_crop import runtime_problem; "
        "problem=runtime_problem(); print(problem or 'Runtime ready'); "
        "sys.exit(1 if problem else 0)"
    )
    try:
        result = subprocess.run([str(python), "-c", code], cwd=root, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=60,
                                env={**os.environ, "PYTHONUTF8": "1"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    return result.returncode == 0, (result.stdout.strip() or result.stderr.strip())


def ensure_environment(root: Path = ROOT) -> Path:
    root = root.resolve()
    python = environment_python(root)
    ready, reason = probe(python, root)
    if ready:
        return python
    if sys.version_info < (3, 10):
        raise RuntimeError("请先安装 Python 3.10+ / Install Python 3.10+ first.")
    print(reason, flush=True)
    print("准备本项目的独立环境 / Preparing the project's isolated environment...", flush=True)
    environment = root / ".crop-env"
    # Incomplete environments can be repaired in place; do not remove user files.
    if not python.is_file():
        subprocess.run([sys.executable, "-m", "venv", str(environment)], cwd=root, check=True)
    elif not probe_python(python):
        raise RuntimeError(
            "已有 .crop-env 的 Python 无法运行。请将该旧环境重命名后再次启动。\n"
            "The existing .crop-env Python cannot run; rename the old environment and restart."
        )
    print("首次安装或修复需要联网下载依赖 / Setup or repair downloads dependencies.", flush=True)
    uv = shutil.which("uv")
    if uv:
        subprocess.run([uv, "pip", "install", "--python", str(python),
                        "-r", str(root / "requirements.txt")], cwd=root, check=True)
    else:
        # A failed first setup may leave python.exe present but pip uninstalled.
        pip_check = subprocess.run([str(python), "-m", "pip", "--version"], cwd=root,
                                   capture_output=True, timeout=30)
        if pip_check.returncode != 0:
            subprocess.run([str(python), "-m", "ensurepip", "--upgrade"], cwd=root, check=True)
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                        "--no-input", "--timeout", "30", "--retries", "2",
                        "-r", str(root / "requirements.txt")], cwd=root, check=True)
    ready, reason = probe(python, root)
    if not ready:
        raise RuntimeError(reason)
    print("环境已就绪 / Environment ready.", flush=True)
    return python


def probe_python(python: Path) -> bool:
    try:
        return subprocess.run([str(python), "-c", "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"],
                              capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_application(script: str, argv: list[str], root: Path = ROOT) -> int:
    if script not in {"screen_crop.py", "train_screen_model.py"}:
        raise ValueError("Unknown project entry point.")
    root = root.resolve()
    python = ensure_environment(root)
    # Preserve relative input/output paths when direct execution switches runtime.
    return subprocess.call([str(python), str(root / script), *argv], cwd=Path.cwd(),
                           env={**os.environ, "PYTHONUTF8": "1"})


def main(argv: list[str] | None = None, *, script: str = "screen_crop.py") -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv == ["--setup-only"]:
            ensure_environment()
            return 0
        return run_application(script, argv)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"启动失败 / Launch failed: {exc}\n"
              "请检查联网状态；也可按 README 手动安装依赖。 / Check connectivity or follow README setup.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
