"""Generate an original synthetic screen photo; no external image assets required."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def make_scene() -> tuple[np.ndarray, np.ndarray]:
    """Return a BGR test scene and the true picture corners in image coordinates."""
    rng = np.random.default_rng(20261009)
    picture = np.zeros((280, 400, 3), dtype=np.uint8)
    yy, xx = np.indices(picture.shape[:2])
    picture[:, :, 0] = 90 + xx // 4
    picture[:, :, 1] = 60 + yy // 3
    picture[:, :, 2] = 210 - yy // 4
    for _ in range(75):
        x, y = rng.integers([10, 10], [390, 270])
        color = tuple(int(c) for c in rng.integers(40, 240, size=3))
        cv2.circle(picture, (int(x), int(y)), int(rng.integers(4, 18)), color, -1)
    cv2.rectangle(picture, (90, 170), (220, 279), (12, 12, 12), -1)
    cv2.putText(picture, "SCREEN PHOTO", (28, 75), cv2.FONT_HERSHEY_SIMPLEX,
                1, (245, 245, 245), 2, cv2.LINE_AA)
    scene = np.full((640, 900, 3), 155, np.uint8)
    cv2.rectangle(scene, (35, 24), (865, 68), (85, 85, 85), -1)
    cv2.putText(scene, "Synthetic viewer", (55, 55), cv2.FONT_HERSHEY_SIMPLEX,
                .7, (225, 225, 225), 1, cv2.LINE_AA)
    quad = np.float32([[225, 180], [670, 150], [690, 475], [205, 495]])
    source = np.float32([[0, 0], [399, 0], [399, 279], [0, 279]])
    matrix = cv2.getPerspectiveTransform(source, quad)
    warped = cv2.warpPerspective(picture, matrix, (900, 640))
    mask = cv2.warpPerspective(np.full((280, 400), 255, np.uint8), matrix, (900, 640))
    scene[mask > 0] = warped[mask > 0]
    return scene, quad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("input/demo.png"))
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; select a new --output path.")
    scene, _ = make_scene()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(cv2.cvtColor(scene, cv2.COLOR_BGR2RGB)).save(args.output)
    print("Synthetic demo saved. Run: python screen_crop.py input output --debug")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
