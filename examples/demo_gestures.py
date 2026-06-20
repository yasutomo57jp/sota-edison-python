#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sota 名前付きジェスチャのデモ。
使い方:
    python3 examples/demo_gestures.py <robot_ip>
    python3 examples/demo_gestures.py <robot_ip> head   # 頭・体系のみ
    python3 examples/demo_gestures.py <robot_ip> arm    # 腕系のみ
    例: python3 examples/demo_gestures.py 192.0.2.10
"""
import os
import sys
import time

# ソースチェックアウトから `sota_edison` を import できるよう、パッケージの src/ を import パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from sota_edison import Sota
from sota_edison import Gestures


def run(name, fn, pause=2.0):
    print(">>> %s" % name, flush=True)
    fn()
    time.sleep(pause)


def demo_head(g):
    print("\n=== 頭・体系ジェスチャ ===", flush=True)
    run("お辞儀 bow", g.bow)
    run("うなずき(はい) nod", g.nod)
    run("いやいや(いいえ) shake_head", g.shake_head)
    run("首をかしげる tilt_head(右)", lambda: g.tilt_head("right"))
    run("きょろきょろ look_around", g.look_around)
    run("考える thinking", g.thinking)
    run("しょんぼり sad", g.sad)
    run("体を右へ turn_body(-600)", lambda: g.turn_body(-600))
    run("体を正面 turn_body(0)", lambda: g.turn_body(0))


def demo_arm(g):
    print("\n=== 腕系ジェスチャ ===", flush=True)
    run("右手を上げる raise_right_hand", lambda: (g.raise_right_hand(), g.lower_hands(700)))
    run("左手を上げる raise_left_hand", lambda: (g.raise_left_hand(), g.lower_hands(700)))
    run("バンザイ banzai", lambda: (g.banzai(), g.lower_hands(700)))
    run("手を振る wave_hand(右)", lambda: g.wave_hand("right"))
    run("手を振る wave_hand(左)", lambda: g.wave_hand("left"))
    run("ハイタッチ high_five(右)", lambda: g.high_five("right"))
    run("喜ぶ cheer", g.cheer)
    run("驚く surprise", g.surprise)
    run("拍手 clap", g.clap)
    run("指さす point(右)", lambda: g.point("right"))


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 examples/demo_gestures.py <robot_ip> [head|arm]")
    host = sys.argv[1]
    which = sys.argv[2] if len(sys.argv) > 2 else "all"
    with Sota(host) as s:
        s.servo_on()
        s.reset_pose(1200)
        time.sleep(1.0)
        g = Gestures(s)
        if which in ("all", "head"):
            demo_head(g)
        if which in ("all", "arm"):
            demo_arm(g)
        print("\n中立姿勢へ戻して終了。", flush=True)
        s.reset_pose(1200)
        time.sleep(1.0)
        s.servo_off()


if __name__ == "__main__":
    main()
