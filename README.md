# sota-edison-python

PC から Vstone **Sota**（Intel Edison 版）をネットワーク越し（TCP）に Python で
制御するライブラリ＋サンプル集です。ロボットには何もインストール不要で、
サーボ／ジェスチャ、カメラ／ビジョン、音声（TTS／音声認識／音源定位）までを
まとめて扱えます。HRI・展示・教育デモなどでの利用を想定しています。

- パッケージのインポート名: `sota_edison`（配布名: `sota-edison-python`）
- ロボット常駐の `vsmd_edison`（サーボ制御ドライバ, ファーム `vs-rc020`）が公開する
  TCP ポート **6498** にアクセスして制御します。
- ロボットの IP アドレスは実行時引数で指定します（本書の例は一般的なドキュメント用 IP
  `192.0.2.10` / 2 台例は `192.0.2.11`。実機の IP に置き換えてください）。

## 主な機能

- **サーボ制御**（`core`）: 頭・腕・腰の各サーボを角度指定で動かす `Sota` クラス。
- **名前付きジェスチャ**（`gestures`）: お辞儀・うなずき・手を振る・考える等、HRI 向けの動作集（`Gestures`）。
- **カメラ／ビジョン**（`camera`, `vision`）: 頭部カメラ撮影、QR 読み取り、顔検出、顔追従（`SotaCamera`, `SotaFaceTracker`）。
- **音声**（`audio`）: TTS（VOICEVOX／gTTS）発話・WAV 再生・口 LED 同期・マイク音源定位（`SotaAudio`）。
- **音声認識**（`asr`）: マイク音声を PC へ送り Whisper（faster-whisper）で文字起こし（`SotaASR`）。
- **対話操作ツール**（`interactive`）: 1 動作ずつ確認できる CLI（コンソールスクリプト `sota-interactive`）。
- **サンプル**（`examples/`）: 全動作デモ、ジェスチャ、ビジョン、顔追従、音声、音声認識、2 台掛け合いデモなど。

## インストール

[uv](https://github.com/astral-sh/uv) の利用を推奨します。

```bash
# 開発インストール（ソースチェックアウトから）
uv pip install -e .
# もしくは
pip install .
```

コア依存は `paramiko`（SSH/SCP）です。用途に応じて extras を追加します。

| extra | 内容 | 追加される依存 |
|-------|------|----------------|
| `.[tts]` | gTTS による発話 | `gTTS` |
| `.[vision]` | 撮影画像の QR/顔検出 | `opencv-python-headless`, `numpy` |
| `.[asr]` | 音声認識 | `faster-whisper`, `webrtcvad`, `numpy` |
| `.[all]` | 上記すべて | — |
| `.[dev]` | 開発/テスト | `pytest` |

```bash
uv pip install -e ".[all]"     # すべての追加機能を有効化
```

なお、`examples/` 配下のスクリプトはソースチェックアウトからそのまま `uv run` で
実行できます（各スクリプトが `src` をパスに追加するため、インストール不要）。
その場合は依存を `uv run --with <pkg> ...` で都度取り込めます。

## ライブラリの使い方

最小コード例です。`with` で接続すると自動初期化されます。

```python
from sota_edison import Sota

with Sota("192.0.2.10") as sota:   # 接続 + 自動初期化
    sota.servo_on()                  # トルクON（現在姿勢を保持して開始）
    sota.reset_pose()                # 直立・腕下げの初期姿勢へ

    sota.raise_right_hand()          # 右手を上げる
    sota.raise_left_hand()           # 左手を上げる
    sota.raise_both_hands()          # 両手を上げる（バンザイ）

    sota.head_yaw(600)               # 顔を左右に向ける（+でロボットの左）
    sota.head_pitch(-200)            # 顔を上下に向ける（+で上）
    sota.look(yaw=300, pitch=-100)   # 頭の向きをまとめて指定
    sota.body_yaw(400)               # 体（腰）を回す

    sota.servo_off()                 # 脱力
```

発話（TTS）は `SotaAudio` で行います。

```python
from sota_edison import SotaAudio

with SotaAudio("192.0.2.10") as a:        # tts_engine 省略時は自動選択
    a.say("こんにちは。ソータです。")           # 既定エンジンで発話（口LED同期）
    a.say("ずんだもんなのだ", engine="voicevox", speaker=3)
    a.play_wav("hello.wav")                  # 任意WAVを再生
```

トップレベルからは主要シンボルを直接インポートできます（遅延 re-export）。

```python
from sota_edison import (
    Sota, Gestures, SotaCamera, SotaFaceTracker, SotaAudio, SotaASR,
    robot_voice, pop_voices_arg, load_robot_voices, set_robot_voice,
    list_voicevox_speakers,
)
from sota_edison import vision as sv        # 画像解析サブモジュール
```

### 名前付きジェスチャ（HRI向け）

```python
from sota_edison import Sota, Gestures

with Sota("192.0.2.10") as s:
    s.servo_on()
    g = Gestures(s)
    g.bow(); g.nod(); g.wave_hand("right"); g.thinking()
```

| ジェスチャ | メソッド | 内容 |
|------------|----------|------|
| お辞儀 | `bow()` | 頭を下げて会釈 |
| うなずき | `nod()` | はい（頭を上下） |
| いやいや | `shake_head()` | いいえ（頭を左右） |
| 首をかしげる | `tilt_head("right"/"left")` | 考え中/ん? |
| 右手/左手を上げる | `raise_right_hand()` / `raise_left_hand()` | 挙手 |
| バンザイ | `banzai()` | 両手を上げる |
| 手を振る | `wave_hand("right"/"left")` | バイバイ |
| ハイタッチ | `high_five("right"/"left")` | 片腕を前へ |
| 喜ぶ | `cheer()` | 両手を上げて頭を弾ませる |
| しょんぼり | `sad()` | うつむく |
| 驚く | `surprise()` | 頭を上げ腕を開く |
| 考える | `thinking()` | 右手をあご元、左手を右肘へ添える |
| 拍手 | `clap()` | 体の前で手を叩く |
| 指さす | `point("right"/"left")` | 片腕を前へ＋頭を向ける |
| きょろきょろ | `look_around()` | 頭を左右に走査 |
| アイドル微動 | `idle_breathing()` | 肩・頭の微小周期運動 |
| 体を向ける | `turn_body(deg)` | 腰を回す |

すべて実機で検証・調整済み（顔への干渉なし）。

## サンプル

各サンプルは `examples/` 配下にあります。スクリプトごとの説明と実行コマンドは
[`examples/README.md`](examples/README.md) を参照してください。代表的な実行例:

```bash
# 基本動作を一通り実演
uv run --with paramiko python examples/demo_all.py 192.0.2.10

# 発話（TTS）
uv run --with paramiko --with gtts python examples/demo_audio.py 192.0.2.10 say "こんにちは"

# 2 台で掛け合い
uv run --with paramiko --with gtts python examples/demo_dialogue.py 192.0.2.10 192.0.2.11
```

## VOICEVOX エンジンの準備（発話に VOICEVOX を使う場合）

発話で VOICEVOX を使う場合は、実行マシン側でローカルに VOICEVOX エンジンを起動しておきます
（gTTS だけを使うなら不要）。Docker が手軽です。

```bash
# 初回のみ: イメージ取得＋コンテナ作成＋起動（CPU 版。GPU 版は nvidia 系イメージ）
docker run -d --name voicevox -p 127.0.0.1:50021:50021 \
    voicevox/voicevox_engine:cpu-ubuntu20.04-latest

# 2 回目以降: 起動 / 停止
docker start voicevox
docker stop voicevox

# 動作確認（バージョンが返れば OK）
curl -s http://127.0.0.1:50021/version
```

`SotaAudio` は VOICEVOX が起動していれば自動で使用し、無ければ gTTS にフォールバックします。
ポート（既定 `127.0.0.1:50021`）を変える場合は `say(..., host=..., port=...)` で指定できます。

## 声の設定

ロボットごとの既定の声は `robot_voices.json`（パッケージ同梱）に
IP→`{engine, speaker}` の対応で定義します。`SotaAudio(host)` や
`examples/demo_audio.py <ip> say ...` が接続先に応じて自動適用します
（`say(speaker=..)` の明示指定が優先）。

ラボや環境ごとに固有の IP→声 対応がある場合は、別ファイルに分けて
`--robot_voices=PATH`（例: `--robot_voices=robot_voices_kawalab.json`）で
上書きできます。こうした環境固有ファイルはリポジトリにコミットしないでください。

---

# 技術リファレンス

以下は制御方式・プロトコル・サーボ構成・アーキテクチャの技術情報です。

## 制御方式の概要

ロボット常駐の `vsmd_edison`（サーボ制御ドライバ）が共有メモリ
（レジスタマップ `/dev/shm/vsmd_mem`）を保持し、シリアル `/dev/ttyMFD1` の
サーボと 60Hz で同期します。**TCP 6498** がそのレジスタへの read/write 窓口で、
PC 側ライブラリはこのポートにテキストコマンドを送ることでロボットを制御します。
ロボットには本ライブラリ用の常駐プロセスをインストールする必要はありません。

- サーボ制御は Python 標準ライブラリのみで成立（追加依存なし）。
- 音声・カメラ機能は実機側のベンダ Java ツールや `aplay`/`arecord` を併用し、
  PC↔実機間のファイル転送・コマンド実行に `paramiko`（SSH/SCP）を使用します。

## TCP 6498 プロトコル

`vsmd` のレジスタへ ASCII テキストでアクセスします（値はリトルエンディアン）。

- **書込**: `w <4桁hexアドレス> <byte0> <byte1> ...\r\n`
- **読出**: `R <4桁hexアドレス> <size>\r\n` → 応答 `#<addr> <b0> <b1> ...\r\n`

サーボを動かす流れ:

1. 目標角度を `InterpServoPosTarget`（アドレス `2560 + id×2`）に書く。
2. 補間タイマースロット（アドレス `496`）へ所要サイクル数を書く。
3. `vsmd` が現在角度 → 目標角度へ補間して動かす。

未初期化のロボット（`ServoBusNum=0`）には `Sota.init()` がサーボ構成
（ID・リミット・オフセット・読取りバンク）を書き込みます。設定済みなら省略します。

口 LED は `memdef` が口 LED ch を `AudioOutValue@138` に紐付けており、`vssnd` が
再生時に更新するため、`aplay` 経由の発話で声に同期して光ります。

## サーボ構成（8軸）

| ID | 定数 | 部位 | 可動範囲(0.1度) |
|----|------|------|----------------|
| 1 | `SV_BODY_Y` | 体(腰)の回転 | -1200〜1200 |
| 2 | `SV_L_SHOULDER` | 左肩(左腕の上下) | -1400〜1000 |
| 3 | `SV_L_ELBOW` | 左肘 | -900〜300 |
| 4 | `SV_R_SHOULDER` | 右肩(右腕の上下) | -1000〜1400 |
| 5 | `SV_R_ELBOW` | 右肘 | -300〜900 |
| 6 | `SV_HEAD_Y` | 頭ヨー(左右) | -1450〜1450 |
| 7 | `SV_HEAD_P` | 頭ピッチ(上下) | -290〜80 |
| 8 | `SV_HEAD_R` | 頭ロール(傾げ) | -250〜250 |

**角度の単位は 0.1度**（例: `600` = 60.0度）。各サーボは可動範囲で自動クランプされます。

向きの実機確認結果:
- `head_yaw` 正 → ロボットの**左**（見ている人から見て右）
- `head_pitch` 正 → **上**、負 → 下
- 右手/左手上げ・両手上げは顔に当たらない姿勢に調整済み

### できる動作一覧（`Sota`）

| 動作 | メソッド | 使うサーボ |
|------|----------|-----------|
| 右手を上げる | `raise_right_hand()` / `lower_right_hand()` | 右肩(4), 右肘(5) |
| 左手を上げる | `raise_left_hand()` / `lower_left_hand()` | 左肩(2), 左肘(3) |
| 両手を上げる | `raise_both_hands()` | 両肩・両肘 |
| 顔を左右に向ける | `head_yaw(deg)` | 頭ヨー(6) |
| 顔を上下に向ける | `head_pitch(deg)` | 頭ピッチ(7) |
| 首を傾げる | `head_roll(deg)` | 頭ロール(8) |
| 頭の向きをまとめて | `look(yaw, pitch, roll)` | 頭6,7,8 |
| 体を回す | `body_yaw(deg)` | 体ヨー(1) |
| 任意サーボを角度指定 | `set_servo(id, deg)` | 任意 |
| 任意の複合姿勢 | `play({id: deg, ...}, msec)` | 任意 |
| 初期姿勢へ | `reset_pose()` | 全部 |
| 実測角度の取得 | `get_read_pos()` | 全部 |

## アーキテクチャ（モジュール構成）

src-layout でコードは `src/sota_edison/` 配下にあります。

| モジュール | 役割 |
|------------|------|
| `core` | サーボ制御本体（`Sota` クラス）。TCP 6498 でレジスタを read/write。 |
| `gestures` | 名前付きジェスチャ集（`Gestures` クラス, HRI 向け）。 |
| `camera` | 頭部カメラ撮影（`SotaCamera`）・顔追従（`SotaFaceTracker`）。 |
| `vision` | 取得画像の QR 読み取り・顔検出・描画（OpenCV）。 |
| `audio` | 発話（TTS: VOICEVOX/gTTS）・WAV 再生・口 LED 同期・マイク音源定位（`SotaAudio`）。 |
| `asr` | 音声認識（マイク→PC へストリーム→VAD 切り出し→Whisper, `SotaASR`）。 |
| `interactive` | 対話的に 1 動作ずつ動かす CLI（コンソールスクリプト `sota-interactive`）。 |

各機能の実機側の仕組み:

- **カメラ**: 撮影は実機側のベンダ Java（libsotacamv4l2）で行い、画像を PC に
  取得して OpenCV で解析する。撮影ツール（`robot/SotaCam.java`）は初回に自動デプロイ＆
  コンパイルされる（実機に jdk1.8 と sotalib.jar が必要、いずれも導入済み）。
  撮影は 1 枚あたり約 4 秒（JVM 起動＋露出安定）。
- **顔追従**: ベンダ `CRoboCamera.StartFaceTraking()` を使い、実機側スレッドが VGA で
  顔検出し、顔の画面中心からのズレを PD 制御で HEAD_P/HEAD_Y に与えて頭を向ける
  （頭サーボはトラッカが占有）。PC 側はキャプチャループ不要で検出状態を受け取るだけ。
  顔検出には十分な明るさが必要。
- **音声（発話）**: PC 側で音声を生成し、WAV を実機へ送って `aplay` で鳴らす方式。
  WAV は実機 ALSA（`vssnd`→`dmix`→USB CODEC, 44100Hz）で再生する。
- **音源定位**: インテリジェントマイク（IM）搭載機向け。検出は実機 Java の `InitRobot`
  経由でのみ成立するため、実用は `SotaAudio.localize_via_bridge()`（実機 Java ブリッジ
  `SotaVoice mic`）を使う。マイクは I2C デバイス（0x3A）で定義される。
- **音声認識**: 実機で `pasuspender -- arecord`（16kHz/mono）を連続実行→SSH で
  ストリーム→PC で 30ms フレームを webrtcvad にかけ、発話を区切って faster-whisper で
  文字起こし（PC で完結、CPU int8）。発話頭を切らないようプリロール（~500ms）を含める。
  実機は system pulseaudio が USB マイクを占有するため取得に `pasuspender` を使う。

実機側ブリッジ（`robot/`）:

| ファイル | 役割 |
|----------|------|
| `robot/SotaCam.java` | 撮影ツール（自動デプロイ/コンパイルされる） |
| `robot/SotaFaceTrack.java` | 顔追従ツール（`CRoboCamera.StartFaceTraking`） |
| `robot/SotaVoice.java` | 音源定位 `mic` ＋発話再生 `play` のブリッジ |

## ディレクトリ構成

```
src/sota_edison/   制御ライブラリ本体（core, gestures, camera, vision, audio, asr, interactive）
examples/          サンプル・デモスクリプト
tests/             テスト（pytest）
robot/             実機（Edison）側の Java ブリッジ
```

## ライセンス

MIT License（[`LICENSE`](LICENSE) を参照）。

## 注意

- 本ライブラリは**実機（ハードウェア）を動かします**。ジェスチャや顔追従で頭・腕・腰が
  動くため、周囲に十分なスペースを確保し、安全に十分注意して使用してください。
- **顔検出・顔追従には十分な明るさが必要**（暗所だとカメラ画像が真っ黒で顔を検出できない）。
- **音源定位はインテリジェントマイク搭載機が必要**です。
- 発話には PC 側 TTS（VOICEVOX/gTTS）を用いる。VOICEVOX を使う場合の準備は
  上記「[VOICEVOX エンジンの準備](#voicevox-エンジンの準備発話に-voicevox-を使う場合)」を参照。
- 本リポジトリは**非公式**であり、Vstone 社とは一切関係ありません。
- 利用は**自己責任**でお願いします。
