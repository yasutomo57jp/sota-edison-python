# サンプル（examples/）

`sota_edison` の機能を実演するサンプルスクリプト集です。

## 前提

- [uv](https://github.com/astral-sh/uv) を推奨。各スクリプトは `src` をパスに
  追加するため、パッケージをインストールせずソースチェックアウトから
  `uv run` でそのまま実行できます。依存は `--with <pkg>` で都度取り込みます。
- **ロボットの IP は実行時引数**で渡します（本書の例は一般的なドキュメント用 IP
  `192.0.2.10` / 2 台例は `192.0.2.11`。実機の IP に置き換えてください）。
  ロボットが PC からネットワーク到達可能である必要があります。
- 発話系（`demo_audio` / `demo_dialogue`）で VOICEVOX を使う場合は、
  **PC 側でローカルの VOICEVOX エンジンを起動**しておきます（Docker 等）。
  ```bash
  docker run -d --name voicevox -p 127.0.0.1:50021:50021 \
      voicevox/voicevox_engine:cpu-ubuntu20.04-latest   # 初回のみ。以後は docker start voicevox
  ```
  エンジンが無い場合は gTTS（`--with gtts`）にフォールバックします。
- 音源定位はインテリジェントマイク（IM）搭載機を想定しています。

## スクリプト一覧

### demo_all — 全基本動作
基本動作（サーボ・腕・頭・体）を順に実演します。
```bash
uv run --with paramiko python demo_all.py 192.0.2.10
```

### demo_gestures — ジェスチャ
名前付きジェスチャ（お辞儀・うなずき・手を振る等）を一通り実演します。
```bash
uv run --with paramiko python demo_gestures.py 192.0.2.10
```

### demo_vision — 撮影 / QR / 顔検出
頭部カメラで撮影し、QR 読み取りと顔検出を行います（OpenCV 使用）。
```bash
uv run --with paramiko --with opencv-python-headless --with numpy \
    python demo_vision.py 192.0.2.10
```

### demo_facetrack — 顔追従
頭が顔を自動追尾します（カメラの前で顔を動かすと頭が追う）。秒数を引数で指定。
```bash
uv run --with paramiko python demo_facetrack.py 192.0.2.10 30
```

### demo_audio — 発話 / 再生 / 音源定位 / 声設定
発話（TTS）・WAV 再生・マイク音源定位・声設定をまとめて扱うツールです。
```bash
# 発話（VOICEVOX 稼働中は自動で VOICEVOX、無ければ gTTS）
uv run --with paramiko --with gtts python demo_audio.py 192.0.2.10 say "こんにちは"
# VOICEVOX 話者を指定して発話
uv run --with paramiko --with gtts python demo_audio.py 192.0.2.10 say "なのだ" voicevox 3
# 任意 WAV を再生
uv run --with paramiko python demo_audio.py 192.0.2.10 play hello.wav
# 音源定位: 呼びかけた方向へ頭を向け発話（IM 機）
uv run --with paramiko --with gtts python demo_audio.py 192.0.2.10 listen 30
# 全ロボットの声を一覧 / VOICEVOX 話者一覧
uv run python demo_audio.py - voices
uv run python demo_audio.py - speakers
```

### demo_asr — 音声認識
話しかけると faster-whisper で文字起こしします（Ctrl+C で終了）。
末尾の引数は秒数と model（tiny/base/small/medium）。
```bash
uv run --with paramiko --with webrtcvad --with faster-whisper --with numpy \
    python demo_asr.py 192.0.2.10 30 small
```

### demo_dialogue — 2 台掛け合い
2 台の Sota がそれぞれの声で身振りを交えて交互に話す統合デモです
（VOICEVOX エンジンを起動しておくこと）。
```bash
uv run --with paramiko --with gtts python demo_dialogue.py 192.0.2.10 192.0.2.11
```

## 声の設定（--robot_voices）

ロボットごとの既定の声は同梱の `robot_voices.json` が使われます。ラボや環境固有の
IP→声 対応がある場合は、`--robot_voices=PATH`（例: `--robot_voices=robot_voices_kawalab.json`）
で別ファイルに上書きできます（環境固有ファイルはコミットしないでください）。
