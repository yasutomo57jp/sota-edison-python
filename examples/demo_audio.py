#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_audio - Sota 音声機能(フェーズ2-C)のデモ。

  # 発話(既定エンジン自動: VOICEVOX があれば優先、無ければ gTTS)
  uv run --with paramiko --with gtts python3 examples/demo_audio.py <ip> say "好きな言葉"
  uv run --with paramiko --with gtts python3 examples/demo_audio.py <ip> say "なのだ" voicevox 3

  # 任意WAVを再生
  uv run --with paramiko python3 examples/demo_audio.py <ip> play hello.wav

  # VOICEVOX 話者一覧
  uv run python3 examples/demo_audio.py - speakers

  # ロボットごとの声(VOICEVOXキャラ)を確認/設定
  uv run python3 examples/demo_audio.py <ip> voice              # 現在の声を表示
  uv run python3 examples/demo_audio.py <ip> voice 2            # 話者IDを2(四国めたん)に設定
  uv run python3 examples/demo_audio.py <ip> voice 2 voicevox   # エンジンも指定
  uv run python3 examples/demo_audio.py - voices                # 全ロボットの設定を一覧

  # マイク音源定位: 音のした方を向く(実機の前で手を叩く/呼びかける)
  uv run --with paramiko python3 examples/demo_audio.py <ip> listen

任意: どのコマンドでも --robot_voices=PATH を付けると声設定ファイルを上書きできる(既定 robot_voices.json)。
"""
import os
import sys

# ソースチェックアウトから `sota_edison` を import できるよう、パッケージの src/ を import パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from sota_edison import (SotaAudio, list_voicevox_speakers, load_robot_voices,
                        robot_voice, set_robot_voice, pop_voices_arg)


def main():
    voices_path, argv = pop_voices_arg(sys.argv)
    if len(argv) < 3:
        print(__doc__)
        return
    host = argv[1]
    cmd = argv[2]

    if cmd == "speakers":
        for name, style, sid in list_voicevox_speakers():
            print("id=%-3d %s / %s" % (sid, name, style))
        return

    if cmd == "voices":
        cfg = load_robot_voices(voices_path)
        if not cfg:
            print("(声設定ファイルなし/空)")
        for host_key, v in cfg.items():
            print("%-16s engine=%s speaker=%s" % (host_key, v.get("engine", "-"), v.get("speaker", "-")))
        return

    if cmd == "voice":
        # voice [speaker] [engine] : 指定なしで表示、指定で設定
        if len(argv) <= 3:
            v = robot_voice(host, voices_path)
            print("%s: engine=%s speaker=%s" % (host, v.get("engine", "(auto)"), v.get("speaker", "(default)")))
        else:
            speaker = int(argv[3])
            engine = argv[4] if len(argv) > 4 else None
            entry = set_robot_voice(host, speaker=speaker, engine=engine, path=voices_path)
            print("set %s -> %s" % (host, entry))
        return

    if cmd == "say":
        text = argv[3] if len(argv) > 3 else "こんにちは。ソータです。"
        engine = argv[4] if len(argv) > 4 else None
        opts = {}
        if len(argv) > 5:
            opts["speaker"] = int(argv[5])
        with SotaAudio(host, voices_path=voices_path) as a:
            print("engine:", engine or a.tts_engine)
            a.say(text, engine=engine, **opts)
            print("said:", text)
        return

    if cmd == "play":
        wav = argv[3]
        with SotaAudio(host, voices_path=voices_path) as a:
            a.play_wav(wav)
            print("played:", wav)
        return

    if cmd == "listen":
        # 音のした方向へ頭を向ける。検出と頭の旋回は実機 Java ブリッジ(SotaVoice mic)が担う
        # (音源定位は InitRobot 経由でのみ成立。要 IM 設定の実機=memdef.conf.sota_im 相当)。
        # 発話は PC 側 TTS。※InitRobot で腕が初期姿勢へ動き、トルクON→終了時に脱力する。
        seconds = int(argv[3]) if len(argv) > 3 else 25
        with SotaAudio(host, voices_path=voices_path) as a:
            print("音源定位ON(%d秒)。実機の前で、左右の斜め前から呼びかけ/手を叩いてください..." % seconds)
            state = {"greeted": False}

            def on_detect(deg, raw):
                print("  検出: %d度 → 頭を向けます" % deg)
                if not state["greeted"]:
                    state["greeted"] = True
                    try:
                        a.say("こちらの方ですか？", engine="voicevox", speaker=3)
                    except Exception as e:
                        print("  (発話スキップ: %s)" % e)

            dets = a.localize_via_bridge(seconds=seconds, turn=True, on_detect=on_detect)
            if not dets:
                print("音を検出できませんでした。")
            else:
                print("検出 %d 件: %s" % (len(dets), ", ".join("%d度" % d for d, _ in dets)))
        return

    print("unknown command:", cmd)
    print(__doc__)


if __name__ == "__main__":
    main()
