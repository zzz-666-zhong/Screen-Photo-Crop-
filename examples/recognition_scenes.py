"""Deterministic synthetic recognition fixtures; no external photos or labels."""

from __future__ import annotations

import cv2
import numpy as np


KINDS = ("color", "square", "gray", "gray-square", "dark", "blur", "small", "low-contrast")


def make_scene(kind: str, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    if kind not in KINDS:
        raise ValueError(f"Unknown scene kind: {kind}")
    rng = np.random.default_rng(9200 + seed)
    square = "square" in kind
    ph, pw = (280, 280) if square else (280, 390)
    yy, xx = np.indices((ph, pw))
    picture = np.zeros((ph, pw, 3), np.uint8)
    picture[..., 0] = 75 + xx // 5
    picture[..., 1] = 65 + yy // 4
    picture[..., 2] = 190 - yy // 5
    for _ in range(65):
        x, y = rng.integers([12, 12], [pw-12, ph-12])
        color = tuple(int(c) for c in rng.integers(30, 240, 3))
        cv2.circle(picture, (int(x), int(y)), int(rng.integers(5, 18)), color, -1)
    cv2.putText(picture, "PHOTO", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, .9, (240, 240, 240), 2)
    cv2.rectangle(picture, (60, 185), (140, ph-1), (8, 8, 8), -1)
    background = 152
    if kind in {"gray", "gray-square", "low-contrast"}:
        gray = cv2.cvtColor(picture, cv2.COLOR_BGR2GRAY)
        if kind == "low-contrast":
            gray = np.uint8(100 + gray.astype(float) * .22)
            background = 155
        picture = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if kind == "dark":
        picture = np.uint8(picture.astype(float) * .24)
        background = 95
    scene = np.full((600, 840, 3), background, np.uint8)
    cv2.rectangle(scene, (26, 24), (814, 58), (72, 72, 72), -1)
    cv2.putText(scene, "LOCAL VIEWER", (45, 47), cv2.FONT_HERSHEY_SIMPLEX, .55, (200, 200, 200), 1)
    width = 280 if square else 405
    height = 300
    if kind == "small":
        width, height = 112, 85
    x = int(rng.integers(125, 200))
    y = int(rng.integers(125, 170))
    quad = np.float32([[x+12, y+18], [x+width-12, y],
                       [x+width+8, y+height-15], [x, y+height]])
    quad += rng.integers(-6, 7, (4, 2)).astype(np.float32)
    matrix = cv2.getPerspectiveTransform(np.float32([[0,0],[pw-1,0],[pw-1,ph-1],[0,ph-1]]), quad)
    pixels = cv2.warpPerspective(picture, matrix, (840, 600))
    mask = cv2.warpPerspective(np.full((ph,pw), 255, np.uint8), matrix, (840,600))
    scene[mask > 0] = pixels[mask > 0]
    if kind == "blur":
        scene = cv2.GaussianBlur(scene, (9, 9), 2.4)
    return scene, quad
