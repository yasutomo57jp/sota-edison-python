#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sota 全動作デモ。
使い方:
    python3 examples/demo_all.py <robot_ip>
    例: python3 examples/demo_all.py 192.0.2.10
"""
import os
import sys
import time

# ソースチェックアウトから `sota_edison` を import できるよう、パッケージの src/ を import パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from sota_edison import Sota, NAME, ALL_IDS


def show(s, ids=ALL_IDS):
    rp = s.get_read_pos()
    tg = s.get_target()
    print("   " + "  ".join("%s=%d(目標%d)" % (NAME[i], rp[i], tg[i]) for i in ids))


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 examples/demo_all.py <robot_ip>")
    host = sys.argv[1]
    print("=== Sota デモ @ %s ===" % host)

    with Sota(host) as s:          # 接続 + 自動初期化(未設定なら全設定書込み)
        print("初期化完了。トルクONにします。")
        s.servo_on()
        print("中立姿勢へ。")
        s.reset_pose(1500)
        time.sleep(0.5)

        print("\n[1] 顔を左右に向ける (HEAD_Y)")
        s.head_yaw(600); time.sleep(0.8)    # ロボットの左
        s.head_yaw(-600); time.sleep(0.8)   # ロボットの右
        s.head_yaw(0); time.sleep(0.5)

        print("[2] 顔を上下に向ける (HEAD_P)")
        s.head_pitch(60); time.sleep(0.8)    # 上
        s.head_pitch(-250); time.sleep(0.8)  # 下
        s.head_pitch(0); time.sleep(0.5)

        print("[3] 首を傾げる (HEAD_R)")
        s.head_roll(200); time.sleep(0.8)
        s.head_roll(-200); time.sleep(0.8)
        s.head_roll(0); time.sleep(0.5)

        print("[4] 体を回す (BODY_Y)")
        s.body_yaw(600); time.sleep(0.8)
        s.body_yaw(-600); time.sleep(0.8)
        s.body_yaw(0); time.sleep(0.5)

        print("[5] 右手を上げる")
        s.raise_right_hand(); time.sleep(1.0)
        s.lower_right_hand(); time.sleep(0.5)

        print("[6] 左手を上げる")
        s.raise_left_hand(); time.sleep(1.0)
        s.lower_left_hand(); time.sleep(0.5)

        print("[7] 両手を上げる (バンザイ)")
        s.raise_both_hands(); time.sleep(1.2)
        s.reset_pose(1200); time.sleep(0.5)

        print("\n最終実測角度:")
        show(s)
        print("\nデモ終了。サーボを脱力します。")
        s.servo_off()


if __name__ == "__main__":
    main()
