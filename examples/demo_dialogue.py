#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2台の Sota が交互に「身振りを交えて」話す掛け合いデモ。

- 各ロボットは robot_voices.json の自分の声(IPに対応する声。未登録IPは既定の声)で発話。
- 発話と同時にジェスチャ(sota_gestures)を行う(別スレッドで身振り、本線で発話)。
- say() は再生完了まで待つので、自然に交互(片方が話し終わってから次)になる。
- 発話中は口LEDが声に同期。再生が一時的に失敗しても1回リトライして続行する。

実行(PCで, VOICEVOX エンジンが起動していること):
    uv run --with paramiko --with gtts python3 examples/demo_dialogue.py <robot_a_ip> <robot_b_ip>
    例: uv run --with paramiko --with gtts python3 examples/demo_dialogue.py 192.0.2.10 192.0.2.11

引数: <A機IP> <B機IP>
任意: --robot_voices=PATH で声設定ファイルを上書き(既定 robot_voices.json)
"""
import os
import sys
import threading
import time

# ソースチェックアウトから `sota_edison` を import できるよう、パッケージの src/ を import パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from sota_edison import SotaAudio, robot_voice, pop_voices_arg
from sota_edison import Sota
from sota_edison import Gestures

# 掛け合い台本: ("A"/"B", セリフ, ジェスチャ関数 or None)。ジェスチャは Gestures を受け取る。
DIALOGUE = [
    ("A", "こんにちは。ぼくはソータエー、ずんだもんの声なのだ。", lambda g: g.wave_hand("right")),
    ("B", "こんにちは。わたしはソータビー、四国めたんよ。",       lambda g: g.wave_hand("left")),
    ("A", "今日は二人で、かけあいのテストをするのだ。",           lambda g: g.nod()),
    ("B", "そうね。声も身振りも、交互に出るか確認しましょう。",   lambda g: g.nod()),
    ("A", "ぼくの声は元気が取り柄。ずんだもんなのだ。",           lambda g: g.raise_right_hand()),
    ("B", "わたしはおっとり、四国めたん。よろしくね。",           lambda g: g.tilt_head("right")),
    ("A", "口のライトも、声に合わせて光っているのだ。",           lambda g: g.point("right")),
    ("B", "ほんとね。ちゃんと同期しているわ。",                   lambda g: g.nod()),
    ("A", "それじゃあ、息を合わせて締めるのだ。せーの。",         lambda g: g.thinking()),
    ("B", "せーの。",                                             lambda g: g.nod()),
    ("A", "ソータ、掛け合いデモ、成功なのだ！",                   lambda g: g.banzai()),
    ("B", "成功です。ありがとうございました。",                   lambda g: g.bow()),
]


def safe_say(audio, line):
    """発話。一時的な再生失敗は1回リトライし、それでも失敗なら続行。"""
    for attempt in range(2):
        try:
            audio.say(line)
            return True
        except Exception as e:
            if attempt == 0:
                time.sleep(1.0)
            else:
                print("  (発話失敗・スキップ: %s)" % e, flush=True)
    return False


def gesture_then_reset(sota, gestures, gfn):
    """ジェスチャを実行し、最後に初期姿勢へ戻す(別スレッドで呼ぶ)。"""
    try:
        if gfn:
            gfn(gestures)
    except Exception as e:
        print("  (ジェスチャskip: %s)" % e, flush=True)
    try:
        sota.reset_pose(msec=500)
    except Exception:
        pass


def main():
    voices_path, argv = pop_voices_arg(sys.argv)
    if len(argv) < 3:
        sys.exit("usage: python3 examples/demo_dialogue.py [--robot_voices=PATH] <robot_a_ip> <robot_b_ip>")
    ip_a = argv[1]
    ip_b = argv[2]
    print("A機: %s %s" % (ip_a, robot_voice(ip_a, voices_path)), flush=True)
    print("B機: %s %s" % (ip_b, robot_voice(ip_b, voices_path)), flush=True)

    # 各ロボット: サーボ(ジェスチャ用)+ オーディオ(発話用)
    sa, sb = Sota(ip_a), Sota(ip_b)
    aa, ab = SotaAudio(ip_a, voices_path=voices_path), SotaAudio(ip_b, voices_path=voices_path)
    motion = {"A": sa, "B": sb}
    gest = {"A": Gestures(sa), "B": Gestures(sb)}
    audio = {"A": aa, "B": ab}
    try:
        for s in (sa, sb):
            s.servo_on()
            s.reset_pose(msec=600)
        for who, line, gfn in DIALOGUE:
            print("[%s] %s" % (who, line), flush=True)
            # 身振り(別スレッド)と発話(本線)を同時に
            t = threading.Thread(target=gesture_then_reset,
                                 args=(motion[who], gest[who], gfn))
            t.start()
            safe_say(audio[who], line)
            t.join()
            time.sleep(0.3)
    finally:
        for s in (sa, sb):
            try:
                s.reset_pose(msec=600)
                s.servo_off()
            except Exception:
                pass
        for c in (aa, ab, sa, sb):
            try:
                c.close()
            except Exception:
                pass
    print("--- 掛け合い終了 ---", flush=True)


if __name__ == "__main__":
    main()
