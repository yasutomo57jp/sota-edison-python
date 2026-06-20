#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sota 顔追従デモ: 頭部カメラで顔を検出し、頭が自動で顔を追いかける。

追従(頭の旋回)は実機側(ベンダ CRoboCamera.StartFaceTraking)が PD 制御で行う。
PC 側は検出状態を表示するだけ。カメラの前に立って左右上下に動くと頭が追ってくる。

実行(PCで):
    uv run --with paramiko python3 examples/demo_facetrack.py <robot_ip> [秒数] [smile:0/1]
    例: uv run --with paramiko python3 examples/demo_facetrack.py 192.0.2.10 30

注意: 開始時に InitRobot で腕が初期姿勢へ動き、トルクON。終了時に脱力する。
"""
import os
import sys

# ソースチェックアウトから `sota_edison` を import できるよう、パッケージの src/ を import パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from sota_edison import SotaFaceTracker


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 examples/demo_facetrack.py <robot_ip> [seconds] [smile:0/1]")
    host = sys.argv[1]
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    smile = len(sys.argv) > 3 and sys.argv[3] == "1"

    with SotaFaceTracker(host) as ft:
        print("顔追従ON(%d秒)。カメラの前で顔を動かすと頭が追いかけます..." % seconds)
        n = [0]

        def on_face(cx, cy, w, h, sm):
            n[0] += 1
            msg = "  顔: 中心(%d,%d) サイズ%dx%d" % (cx, cy, w, h)
            if sm >= 0:
                msg += "  笑顔度=%d" % sm
            print(msg)

        faces = ft.track(seconds=seconds, search=True, smile=smile, on_face=on_face)
        print("検出フレーム数: %d" % len(faces))
        if not faces:
            print("顔を検出できませんでした(カメラ正面・同じ高さに顔を)。")


if __name__ == "__main__":
    main()
