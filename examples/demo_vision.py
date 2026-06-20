#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sota カメラのビジョンデモ: 撮影 → QR読み取り＋顔検出 → 注釈画像を保存。

実行(PCで):
    uv run --with paramiko --with opencv-python-headless --with numpy \
        python3 examples/demo_vision.py <robot_ip>
    例: ... python3 examples/demo_vision.py 192.0.2.10

引数: <robot_ip> [出力画像パス] [サイズ]
"""
import os
import sys
import time

# ソースチェックアウトから `sota_edison` を import できるよう、パッケージの src/ を import パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from sota_edison import SotaCamera
from sota_edison import vision as sv


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 examples/demo_vision.py <robot_ip> [out_path] [size]")
    host = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "captures/live.jpg"
    size = sys.argv[3] if len(sys.argv) > 3 else "VGA"

    t0 = time.time()
    with SotaCamera(host) as cam:
        path = cam.capture(out, size=size)
    t_cap = time.time() - t0

    qrs = sv.detect_qr(path)
    faces = sv.detect_faces(path)
    w, h = sv.image_size(path)

    print("撮影: %s (%dx%d)  所要 %.1f秒" % (path, w, h, t_cap))
    print("QRコード: %d 件" % len(qrs))
    for q in qrs:
        print("   -> %r" % q["text"])
    print("顔: %d 件" % len(faces))
    for f in faces:
        print("   -> 中心(%d,%d) サイズ %dx%d" % (f["cx"], f["cy"], f["w"], f["h"]))

    annotated = out.rsplit(".", 1)[0] + "_annotated.jpg"
    sv.annotate(path, annotated, faces=faces, qrs=qrs)
    print("注釈画像:", annotated)


if __name__ == "__main__":
    main()
