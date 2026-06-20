#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sota_vision - Sota カメラ画像の解析（QRコード読み取り・顔検出）。

PC 側で OpenCV を使って処理する。実行は:
    uv run --with opencv-python-headless --with numpy python3 sota_vision.py <画像>

関数:
    detect_qr(image_path)      -> [{"text":..., "points":[[x,y],...]}, ...]
    detect_faces(image_path)   -> [{"x","y","w","h","cx","cy"}, ...]
    annotate(image_path, out_path, faces=, qrs=)  検出枠を描いて保存
"""
import os


def _imread(image_path):
    import cv2
    img = cv2.imread(image_path)
    if img is None:
        raise IOError("画像を読めません: %s" % image_path)
    return img


def detect_qr(image_path):
    """画像中の QR コードを全て読み取る。"""
    import cv2
    img = _imread(image_path)
    det = cv2.QRCodeDetector()
    results = []
    try:
        ok, infos, points, _ = det.detectAndDecodeMulti(img)
    except cv2.error:
        ok = False
    if ok and points is not None:
        for text, pts in zip(infos, points):
            if text:
                results.append({"text": text, "points": pts.astype(int).tolist()})
    return results


def detect_faces(image_path, scale_factor=1.1, min_neighbors=5, min_size=40):
    """正面顔を検出して矩形リストを返す（Haar 特徴, OpenCV 同梱）。"""
    import cv2
    img = _imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(
        gray, scaleFactor=scale_factor, minNeighbors=min_neighbors,
        minSize=(min_size, min_size))
    out = []
    for (x, y, w, h) in faces:
        out.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h),
                    "cx": int(x + w / 2), "cy": int(y + h / 2)})
    return out


def image_size(image_path):
    img = _imread(image_path)
    h, w = img.shape[:2]
    return w, h


def annotate(image_path, out_path, faces=None, qrs=None):
    """検出結果(顔/QR)を画像に描画して保存する。"""
    import cv2
    img = _imread(image_path)
    for f in (faces or []):
        cv2.rectangle(img, (f["x"], f["y"]), (f["x"] + f["w"], f["y"] + f["h"]),
                      (0, 255, 0), 2)
    for q in (qrs or []):
        import numpy as np
        pts = np.array(q["points"], dtype=int)
        cv2.polylines(img, [pts], True, (0, 0, 255), 2)
        cv2.putText(img, q["text"][:20], tuple(pts[0]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    cv2.imwrite(out_path, img)
    return out_path


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "sota_snap.jpg"
    w, h = image_size(path)
    qrs = detect_qr(path)
    faces = detect_faces(path)
    print("画像: %s (%dx%d)" % (path, w, h))
    print("QRコード: %d 件" % len(qrs))
    for q in qrs:
        print("   -> %r" % q["text"])
    print("顔: %d 件" % len(faces))
    for f in faces:
        print("   -> 中心(%d,%d) サイズ%dx%d" % (f["cx"], f["cy"], f["w"], f["h"]))
    if qrs or faces:
        out = os.path.splitext(path)[0] + "_annotated.jpg"
        annotate(path, out, faces=faces, qrs=qrs)
        print("注釈画像:", out)
