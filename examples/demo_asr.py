#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sota 音声認識デモ: ロボットのマイクに話しかけると、PC側 Whisper で文字起こしする。

ロボットで arecord(16k/mono)を連続実行→PCへストリーム→VADで発話区間を切り出し→faster-whisper。

実行(PCで):
    uv run --with paramiko --with webrtcvad --with faster-whisper --with numpy \
        python3 examples/demo_asr.py <robot_ip> [秒数] [モデル]
    例: ... python3 examples/demo_asr.py 192.0.2.10 30 small

引数: <robot_ip> [seconds(省略=Ctrl+Cまで)] [model(tiny/base/small/medium, 既定small)]
"""
import os
import sys

# ソースチェックアウトから `sota_edison` を import できるよう、パッケージの src/ を import パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from sota_edison import SotaASR


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 examples/demo_asr.py <robot_ip> [seconds] [model]")
    host = sys.argv[1]
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else None
    model = sys.argv[3] if len(sys.argv) > 3 else "small"

    print("Whisperモデル読み込み中(%s, CPU)..." % model, flush=True)
    with SotaASR(host, model=model) as asr:
        _ = asr.model  # 事前ロード
        print("認識開始。ロボットのマイクに話しかけてください"
              + ("(%d秒)" % seconds if seconds else "(Ctrl+Cで終了)") + " ...", flush=True)

        def on_text(text, info):
            print("[%.1fs] %s" % (info["duration"], text), flush=True)

        try:
            results = asr.listen(on_text=on_text, seconds=seconds)
        except KeyboardInterrupt:
            results = []
            print("\n(終了)")
        print("--- 認識した発話: %d 件 ---" % len(results))


if __name__ == "__main__":
    main()
