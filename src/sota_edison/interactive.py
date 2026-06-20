#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sota 対話操作ツール。1動作ずつ自分のペースで動かして確認できる。

使い方(インストール後):
    sota-interactive 192.0.2.10
  または:
    python3 -m sota_edison.interactive 192.0.2.10

コマンド(プロンプトに入力):
  [基本動作]
    rh / lh / bh      右手上げ / 左手上げ / 両手上げ
    dh                両手下げ(初期姿勢)
    y <deg>           顔を左右 (例: y 600 で +60度。+はロボットの左)
    p <deg>           顔を上下 (+は上)
    r <deg>           首を傾げ
    b <deg>           体を回す
    s <id> <deg>      サーボ単体 (id 1..8) を指定角度へ
    reset             初期姿勢へ
    read              現在の実測角度を表示
    on / off          トルク ON / OFF(脱力)
    q                 終了(脱力して切断)
  [ジェスチャ] g <名前> または名前を直接入力
    bow お辞儀 / nod うなずき / shake_head いやいや / tilt_head 首かしげ
    wave_hand 手を振る / high_five ハイタッチ / banzai バンザイ
    cheer 喜ぶ / sad しょんぼり / surprise 驚く / thinking 考える / clap 拍手
    point 指さす / look_around きょろきょろ / idle_breathing アイドル微動
    gestures          ジェスチャ名の一覧を表示
    例: thinking      / wave_hand left / tilt_head left / point right

角度は 0.1度単位(600 = 60.0度)。可動範囲で自動クランプ。
"""
import sys
from .core import Sota, NAME, ALL_IDS
from .gestures import Gestures, GESTURE_LIST

HELP = __doc__
GESTURE_NAMES = set(name for name, _desc in GESTURE_LIST)


def main():
    if len(sys.argv) < 2:
        print("使い方: sota-interactive <robot_ip>  (または python3 -m sota_edison.interactive <robot_ip>)")
        sys.exit(1)
    host = sys.argv[1]
    print("接続中... %s" % host)
    s = Sota(host)
    s.servo_on()
    g = Gestures(s)
    print("接続OK。トルクON。コマンド一覧は help。")
    print(HELP)

    try:
        while True:
            try:
                line = input("sota> ").strip()
            except EOFError:
                break
            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()
            try:
                if cmd in ("q", "quit", "exit"):
                    break
                elif cmd in ("help", "h", "?"):
                    print(HELP)
                elif cmd == "gestures":
                    for name, desc in GESTURE_LIST:
                        print("  %-16s %s" % (name, desc))
                elif cmd == "g" and len(parts) >= 2 and parts[1] in GESTURE_NAMES:
                    getattr(g, parts[1])(*[a for a in parts[2:]])
                elif cmd in GESTURE_NAMES:
                    getattr(g, cmd)(*[a for a in parts[1:]])
                elif cmd == "rh":
                    s.raise_right_hand()
                elif cmd == "lh":
                    s.raise_left_hand()
                elif cmd == "bh":
                    s.raise_both_hands()
                elif cmd == "dh":
                    s.lower_right_hand(); s.lower_left_hand()
                elif cmd == "reset":
                    s.reset_pose()
                elif cmd == "on":
                    s.servo_on()
                elif cmd == "off":
                    s.servo_off()
                elif cmd == "read":
                    rp = s.get_read_pos()
                    for i in ALL_IDS:
                        print("  id%d %-11s %6d" % (i, NAME[i], rp[i]))
                elif cmd == "y":
                    s.head_yaw(int(parts[1]))
                elif cmd == "p":
                    s.head_pitch(int(parts[1]))
                elif cmd == "r":
                    s.head_roll(int(parts[1]))
                elif cmd == "b":
                    s.body_yaw(int(parts[1]))
                elif cmd == "s":
                    s.set_servo(int(parts[1]), int(parts[2]))
                else:
                    print("不明なコマンド: %s  (help で一覧)" % cmd)
            except (IndexError, ValueError):
                print("引数が不正です。help を参照。")
            except Exception as e:
                # 一時的な通信エラー等でセッションを落とさない
                print("エラー: %s （再試行してください）" % e)
    finally:
        print("\n脱力して終了します。")
        s.servo_off()
        s.close()


if __name__ == "__main__":
    main()
