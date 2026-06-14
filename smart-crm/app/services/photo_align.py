from __future__ import annotations

from pathlib import Path
from typing import Any


def align_and_compare(approved_path: Path, photo_path: Path) -> dict[str, Any]:
    """OpenCV ORB 对齐 + 像素差异（确稿 vs 大货实拍）。"""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {
            "status": "skipped",
            "detail": "OpenCV 未安装",
            "alignment": "none",
            "diff_pct": None,
        }

    if not approved_path.exists() or not photo_path.exists():
        return {
            "status": "skipped",
            "detail": "图片文件不存在",
            "alignment": "none",
            "diff_pct": None,
        }

    ref = cv2.imread(str(approved_path))
    photo = cv2.imread(str(photo_path))
    if ref is None or photo is None:
        return {
            "status": "skipped",
            "detail": "无法读取图片",
            "alignment": "none",
            "diff_pct": None,
        }

    ref_gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    photo_gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
    alignment = "resize_fallback"
    aligned = cv2.resize(photo, (ref.shape[1], ref.shape[0]))

    orb = cv2.ORB_create(800)
    kp1, des1 = orb.detectAndCompute(ref_gray, None)
    kp2, des2 = orb.detectAndCompute(photo_gray, None)
    if des1 is not None and des2 is not None and len(kp1) >= 8 and len(kp2) >= 8:
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        matches = sorted(matches, key=lambda m: m.distance)
        good = matches[: min(40, len(matches))]
        if len(good) >= 4:
            src_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            matrix, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            if matrix is not None:
                aligned = cv2.warpPerspective(photo, matrix, (ref.shape[1], ref.shape[0]))
                alignment = "orb_homography"
                inliers = int(mask.sum()) if mask is not None else len(good)
            else:
                inliers = 0
        else:
            inliers = 0
    else:
        inliers = 0

    diff = cv2.absdiff(ref, aligned)
    diff_pct = round(float(np.mean(diff)) / 255.0 * 100.0, 2)
    status = "pass"
    if diff_pct > 3.0:
        status = "warn"
    if diff_pct > 10.0:
        status = "fail"

    return {
        "status": status,
        "diff_pct": diff_pct,
        "alignment": alignment,
        "match_inliers": inliers,
        "detail": f"对齐方式 {alignment}，差异 {diff_pct}%",
    }
