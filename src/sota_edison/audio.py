#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sota_audio - Sota の音声まわり(発話TTS / WAV再生 / マイク音源定位)を
PC から扱うラッパー。フェーズ2-C。

構成（ハイブリッド）:
- **WAV再生**: PC で用意した WAV を SFTP で実機 /dev/shm へ送り、`aplay` で再生。
  経路は実機 ALSA default(`vssnd`→`dmix`→USB CODEC, 44100Hz)。依存は paramiko のみ。
- **TTS(発話)**: PC 側で音声を生成して WAV にし、上記で再生する「方式B」。
  対応エンジン:
    * "voicevox" … ローカル VOICEVOX エンジン(HTTP, 既定 127.0.0.1:50021)。高品質・無料・キャラ声多数。
    * "gtts"     … gTTS(Google翻訳TTS, オンライン)。手軽。
  **ロボットごとの声**: `robot_voices.json`(IP→{engine,speaker}) で個体別の既定キャラを設定でき、
  `SotaAudio(host)` が接続先に応じて自動適用する(`say(speaker=...)`の明示指定が優先)。
  既定ファイルは robot_voices.json。デモは `--robot_voices=PATH` で別ファイル(例: ラボ固有のIP対応表)に上書き可。
  `set_robot_voice(host, speaker, engine)` / `examples/demo_audio.py <ip> voice <id>` で設定。
    * "sota"     … 純正Java ブリッジ(robot/SotaVoice.java)経由(既定では使わない)。
  発話中は口LEDが音声レベルに同期して光る(memdef が口LED ch を AudioOutValue@138 に紐付け、
  vssnd が再生時に更新)。光らない環境では `say(..., mouth_sync=True)` で CPlayWave 経由に切替。
  ※注意: 実機(Edison)は **ソフト再起動でUSBホストが立ち上がらず USB音声CODEC/カメラを見失う**
    ことがある(dwc3 host 未起動・USB gadgetモードで起動)。その場合は**電源を入れ直す**(full power cycle)。
- **マイク音源定位**: vsmd 共有メモリ(TCP6498)の MicMode/VoiceDetection/DetectedDirection を
  扱う API を用意（`start_localization`/`sound_direction_deg`/`turn_to_sound`）。
  ※ 音源定位には Vstone インテリジェントマイク(I2C 0x3A, type-2 デバイス)が必要。これは設定
    `memdef.conf.sota_im` に定義されており、`CRobotMotion.InitRobot` がそれを読んだ時のみ vsmd に登録される。
    実機の **稼働中 memdef.conf が非IMの .sota プロファイルだとマイク未登録**で検出されない。
    → 恒久有効化: active `memdef.conf` を `.sota_im` に差し替えて再起動。IM搭載の実機で
      この手順により音源定位の検出を確認済(`DIR 180`)。検出は散発的で VAD 調整(sotavoice/vad.ini)に余地。
    `robot/SotaVoice.java mic` は `.sota_im` を明示ロードして登録＋方向をストリーム出力する。

依存: paramiko（+ TTSエンジンに応じ gtts / VOICEVOXエンジン / ffmpeg）。
実行は `uv run --with paramiko [--with gtts] python3 ...` を想定。

使い方:
    from sota_audio import SotaAudio
    with SotaAudio("192.0.2.10") as a:
        a.play_wav("hello.wav")               # 任意のWAVを再生
        a.say("こんにちは。ソータです。")        # TTS(既定エンジン)で発話
        a.say("ずんだもんなのだ", speaker=3)     # VOICEVOX 話者ID指定

    # マイク音源定位（sotapy と連携して音の方を向く）
    from sotapy import Sota
    with Sota("192.0.2.10") as s, SotaAudio("192.0.2.10") as a:
        s.servo_on()
        a.start_localization()
        deg = a.wait_for_sound(timeout=10)     # 音を検出したら方向(度)を返す
        if deg is not None:
            a.turn_to_sound(s, deg)
"""
import io
import json
import os
import subprocess
import time
import wave

import paramiko

# vsmd 共有メモリ レジスタ(byteアドレス)。sotapy と同じ TCP6498 を使う。
A_AUDIO_OUT = 136          # 出力音声レベル(発話中>0)
A_MIC_MODE = 152           # 0=NO_USE,1=FRONT,2=AUTO_DIRECTION
A_VOICE_DETECT = 154       # 音声検出フラグ(!=0 で検出)
A_DETECTED_DIR = 156       # 音源方向(下表の raw インデックス)

MIC_NO_USE = 0
MIC_FRONT = 1
MIC_AUTO_DIRECTION = 2

# IntelligentMicControl.getDetectedDirectionDeg() と同じ対応(raw→度)。
# 度の符号: 負=ロボットの右(R) / 正=ロボットの左(L) / 0=正面 / 180=後方。
#   ※ sotapy の HEAD_Y も「正=ロボットの左」なので head_yaw(度*10) で素直に向ける。
DIR_DEG = {0: -90, 1: -120, 2: -150, 3: 180, 4: 150, 5: 120,
           6: 90, 7: 60, 8: 30, 9: 0, 10: -30, 11: -60}

REMOTE_WAV = "/dev/shm/sota_play.wav"
ROBOT_WORK = "/home/vstone/lib-users"
JAVA = "/home/vstone/java/jdk1.8.0_40/bin/java"
JAVAC = "/home/vstone/java/jdk1.8.0_40/bin/javac"
# sotalib + 依存(gson 等)をまとめて読むためワイルドカード classpath を使う。
ROBOT_CP = ".:/home/vstone/lib/*"
ROBOT_JNA = "/home/vstone/lib"
_JAVA_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "robot", "SotaVoice.java")

# 実機スピーカーが素直に鳴らせる正規フォーマット(tone再生で実証済)。
OUT_RATE = 44100
OUT_CH = 1


# ============================ TTS エンジン(PC側) ============================
def tts_gtts(text, out_wav, lang="ja", **_):
    """gTTS でテキスト→WAV(44100/mono)。要ネット接続・ffmpeg。"""
    from gtts import gTTS  # 遅延 import(未使用時は不要)
    mp3 = out_wav + ".mp3"
    gTTS(text=text, lang=lang).save(mp3)
    _ffmpeg_to_wav(mp3, out_wav)
    try:
        os.remove(mp3)
    except OSError:
        pass
    return out_wav


def tts_voicevox(text, out_wav, speaker=3, host="127.0.0.1", port=50021,
                 timeout=30, **_):
    """ローカル VOICEVOX エンジン(HTTP)でテキスト→WAV(44100/mono)。

    speaker: 話者ID(例 3=ずんだもんノーマル, 2=四国めたん 等)。`list_voicevox_speakers()` 参照。
    """
    import json
    import urllib.parse
    import urllib.request
    base = "http://%s:%d" % (host, port)
    q = urllib.parse.urlencode({"text": text, "speaker": speaker})
    # 1) audio_query: 合成パラメータを生成
    req = urllib.request.Request(base + "/audio_query?" + q, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        query = r.read()
    # 2) synthesis: WAV(24000Hz)を生成
    req = urllib.request.Request(
        base + "/synthesis?speaker=%d" % speaker, data=query,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        wav24 = r.read()
    # 3) 実機向けに 44100/mono へ整える
    raw = out_wav + ".vv.wav"
    with open(raw, "wb") as f:
        f.write(wav24)
    _ffmpeg_to_wav(raw, out_wav)
    try:
        os.remove(raw)
    except OSError:
        pass
    return out_wav


def list_voicevox_speakers(host="127.0.0.1", port=50021, timeout=10):
    """VOICEVOX の話者一覧 [(name, style, id), ...] を返す(エンジン稼働時)。"""
    import json
    import urllib.request
    url = "http://%s:%d/speakers" % (host, port)
    with urllib.request.urlopen(url, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = []
    for spk in data:
        for st in spk.get("styles", []):
            out.append((spk.get("name"), st.get("name"), st.get("id")))
    return out


def voicevox_available(host="127.0.0.1", port=50021, timeout=3):
    import urllib.request
    try:
        urllib.request.urlopen("http://%s:%d/version" % (host, port), timeout=timeout)
        return True
    except Exception:
        return False


def _ffmpeg_to_wav(src, dst, rate=OUT_RATE, ch=OUT_CH):
    """ffmpeg で任意音声→ PCM s16 WAV(rate/ch) に変換。"""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
         "-ar", str(rate), "-ac", str(ch), "-sample_fmt", "s16", dst],
        check=True)
    return dst


TTS_ENGINES = {"gtts": tts_gtts, "voicevox": tts_voicevox}

# ロボットIPごとの既定の声(エンジン/話者)。robot_voices.json で設定。
_VOICES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "robot_voices.json")


def load_robot_voices(path=None):
    """声設定ファイルを読み {host: {"engine","speaker"}, ...} を返す(無ければ空)。
    path 省略時は既定の robot_voices.json。--robot_voices で別ファイルを渡せる。"""
    path = path or _VOICES_PATH
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except (OSError, ValueError):
        return {}


def robot_voice(host, path=None):
    """指定ロボットの既定の声 {"engine","speaker"} を返す(host→default→{}の順)。"""
    cfg = load_robot_voices(path)
    return cfg.get(host) or cfg.get("default") or {}


def pop_voices_arg(argv):
    """argv から '--robot_voices=PATH' を取り除き (path or None, 残りのargv) を返す。
    デモ共通: 既定は robot_voices.json、このオプションでラボ固有ファイル等に上書きできる。"""
    path, rest = None, []
    for a in argv:
        if a.startswith("--robot_voices="):
            path = a.split("=", 1)[1]
        else:
            rest.append(a)
    return path, rest


def set_robot_voice(host, speaker=None, engine=None, path=None):
    """声設定ファイルにロボットの声を設定/更新する(既定 robot_voices.json)。"""
    path = path or _VOICES_PATH
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    entry = data.get(host, {}) if isinstance(data.get(host), dict) else {}
    if speaker is not None:
        entry["speaker"] = int(speaker)
    if engine is not None:
        entry["engine"] = engine
    data[host] = entry
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return entry


# ================================ 本体 ================================
class SotaAudio(object):
    def __init__(self, host, user="root", password="edison00", timeout=15,
                 tts_engine=None, tts_opts=None, mem=None, voices_path=None):
        """host: 実機IP。tts_engine: "voicevox"/"gtts"/None(自動)。
        tts_opts: エンジンへ渡す既定オプション(dict, 例 {"speaker":3})。
        mem: 既存の sotapy.Mem を共有したい場合に渡す(無ければ遅延生成)。
        voices_path: 声設定ファイル(省略時 robot_voices.json)。"""
        self.host = host
        self.cli = paramiko.SSHClient()
        self.cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.cli.connect(host, username=user, password=password, timeout=timeout,
                         look_for_keys=False, allow_agent=False)
        self._mem = mem
        # ロボットIPごとの既定の声(声設定ファイル)。明示引数(tts_engine/tts_opts)が優先。
        vcfg = robot_voice(host, voices_path)
        opts = {}
        if "speaker" in vcfg:
            opts["speaker"] = vcfg["speaker"]
        opts.update(tts_opts or {})
        self.tts_opts = opts
        self.tts_engine = tts_engine or vcfg.get("engine") or self._auto_engine()

    def _auto_engine(self):
        """利用可能な PC側TTS を自動選択(VOICEVOX があれば優先、無ければ gTTS)。"""
        vv = self.tts_opts.get("host", "127.0.0.1"), self.tts_opts.get("port", 50021)
        if voicevox_available(vv[0], vv[1]):
            return "voicevox"
        return "gtts"

    # ---- 低レベル SSH ----
    def _exec(self, cmd, timeout=60):
        stdin, stdout, stderr = self.cli.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err

    def _put(self, local, remote):
        sftp = self.cli.open_sftp()
        sftp.put(local, remote)
        sftp.close()

    def _get(self, remote, local):
        sftp = self.cli.open_sftp()
        sftp.get(remote, local)
        sftp.close()

    def _exists(self, path):
        rc, _, _ = self._exec("test -e %s" % path)
        return rc == 0

    # ---- 共有メモリ(TCP6498) ----
    @property
    def mem(self):
        if self._mem is None:
            from sotapy import Mem
            self._mem = Mem(self.host)
        return self._mem

    # ============================ WAV 再生 ============================
    def play_wav(self, local_wav, wait=True, remote=REMOTE_WAV, mouth_sync=False):
        """ローカルの WAV を実機へ送って再生する。

        mouth_sync=False: `aplay`(default device=vssnd→dmix→CODEC)。軽量。
        mouth_sync=True : 実機 Java の `CPlayWave`(SotaVoice play)で再生。発話に合わせ口LEDが光る
                          (ベンダの口LED音声同期を利用)。JVM起動で数秒の遅延あり。
        wait=True なら再生終了まで待つ。
        """
        if not os.path.exists(local_wav):
            raise IOError("no such file: %s" % local_wav)
        self._put(local_wav, remote)
        if mouth_sync:
            rc, out, err = self._run_bridge("play %s" % remote, timeout=120)
            line = (out.strip().splitlines() or [""])[-1] if out else ""
            if wait and "OK" not in out:
                raise RuntimeError("mouth-sync play failed:\n%s\n%s" % (out, err))
            return "OK" in out
        cmd = "aplay -q %s" % remote
        if not wait:
            cmd = "nohup %s >/dev/null 2>&1 &" % cmd
        rc, out, err = self._exec(cmd, timeout=120)
        if wait and rc != 0:
            raise RuntimeError("aplay failed rc=%d:\n%s\n%s" % (rc, out, err))
        return rc == 0

    def play_remote(self, remote_path, wait=True):
        """すでに実機上にある WAV を再生する。"""
        cmd = "aplay -q %s" % remote_path
        if not wait:
            cmd = "nohup %s >/dev/null 2>&1 &" % cmd
        rc, out, err = self._exec(cmd, timeout=120)
        if wait and rc != 0:
            raise RuntimeError("aplay failed:\n%s\n%s" % (out, err))
        return rc == 0

    # ============================ 発話(TTS) ============================
    def synth(self, text, out_wav=None, engine=None, **opts):
        """テキストを PC側で WAV 合成して保存パスを返す(再生はしない)。"""
        engine = engine or self.tts_engine
        fn = TTS_ENGINES.get(engine)
        if fn is None:
            raise ValueError("unknown tts engine: %s" % engine)
        if out_wav is None:
            out_wav = "/tmp/sota_tts_%s.wav" % engine
        merged = dict(self.tts_opts)
        merged.update(opts)
        return fn(text, out_wav, **merged)

    def say(self, text, engine=None, wait=True, mouth_sync=False, **opts):
        """テキストを合成して実機スピーカーから発話する。

        口LED同期: 実機の memdef は口LED(2nd LEDドライバ ch)を `AudioOutValue@138` に紐付けており、
        既定の `aplay`(vssnd経由)再生でも音声レベルに合わせて口LEDが光る想定(=mouth_sync=False)。
        もし環境により光らない場合は mouth_sync=True でベンダ `CPlayWave` 経由に切替(JVM起動で数秒遅延)。
        """
        wav = self.synth(text, engine=engine, **opts)
        return self.play_wav(wav, wait=wait, mouth_sync=mouth_sync)

    # ===================== マイク 音源定位 =====================
    # 注意: 音源定位は IntelligentMic(I2C 0x3A) が memdef.conf.sota_im 経由で vsmd 登録された
    # 場合のみレジスタが更新される。実機の稼働中設定が非IMだと常に0。詳細はモジュール冒頭の注記参照。
    def set_mic_mode(self, mode):
        """MicMode を設定。MIC_AUTO_DIRECTION で音源方向検出を有効化。"""
        self.mem.w_u16(A_MIC_MODE, mode)
        return self.mem.r_u16(A_MIC_MODE)

    def start_localization(self):
        return self.set_mic_mode(MIC_AUTO_DIRECTION)

    def stop_localization(self):
        return self.set_mic_mode(MIC_NO_USE)

    def voice_detected(self):
        return self.mem.r_u16(A_VOICE_DETECT) != 0

    def sound_direction_deg(self):
        """現在の音源方向(度)。負=右/正=左/0=正面/180=後方。未確定時は None。"""
        raw = self.mem.r_u16(A_DETECTED_DIR)
        return DIR_DEG.get(raw)

    def wait_for_sound(self, timeout=10.0, poll=0.1):
        """音声検出されるまで待ち、方向(度)を返す。timeout で None。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.voice_detected():
                return self.sound_direction_deg()
            time.sleep(poll)
        return None

    def turn_to_sound(self, sota, deg=None, msec=600):
        """音源方向へ頭(必要なら体)を向ける。sota は sotapy.Sota。

        deg 未指定なら現在の検出方向を使う。頭ヨー可動域(±145°)を超える分は体で回す。
        """
        if deg is None:
            deg = self.sound_direction_deg()
        if deg is None:
            return None
        head_limit = 145  # HEAD_Y は ±1450(0.1度)
        if abs(deg) <= head_limit:
            sota.look(yaw=int(deg * 10), msec=msec)
        else:
            # 頭だけでは向けない → 体で回してから頭で微調整
            body = max(-120, min(120, deg))
            sota.body_yaw(int(body * 10), msec=max(msec, 800))
            rest = deg - body
            sota.look(yaw=int(max(-head_limit, min(head_limit, rest)) * 10), msec=msec)
        return deg

    def localize_via_bridge(self, seconds=20, poll_ms=100, turn=False, on_detect=None):
        """実機 Java ブリッジ(SotaVoice mic)経由で音源定位を実行する。

        音源定位の検出は **この InitRobot 経由でのみ成立**する(pure-Python の
        register poll では検出されない)。turn=True なら検出方向へ Java 側で頭を向ける。
        on_detect(deg, raw) は各検出で呼ばれる。検出 [(deg, raw), ...] を返す。
        ※ InitRobot がサーボにトルクを入れ初期姿勢へ動かし、終了時に脱力する。
        """
        self.ensure_voice_bridge()
        argstr = "mic %d %d %d" % (seconds, poll_ms, 1 if turn else 0)
        cmd = ("cd %s && %s -cp '%s' -Djna.library.path=%s SotaVoice %s 2>&1"
               % (ROBOT_WORK, JAVA, ROBOT_CP, ROBOT_JNA, argstr))
        chan = self.cli.get_transport().open_session()
        chan.settimeout(seconds + 40)
        chan.exec_command(cmd)
        detections = []
        buf = b""
        deadline = time.time() + seconds + 35
        while time.time() < deadline:
            if chan.recv_ready():
                data = chan.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, _, buf = buf.partition(b"\n")
                    s = line.decode("utf-8", "replace").strip()
                    if s.startswith("DIR"):
                        parts = s.split()
                        deg, raw = int(parts[1]), int(parts[2])
                        detections.append((deg, raw))
                        if on_detect:
                            on_detect(deg, raw)
                    elif s.startswith("OK mic-done"):
                        deadline = 0
            elif chan.exit_status_ready() and not chan.recv_ready():
                break
            else:
                time.sleep(0.05)
        try:
            chan.close()
        except Exception:
            pass
        return detections

    # ===================== 純正TTS Java ブリッジ(任意) =====================
    def ensure_voice_bridge(self, force=False):
        """robot/SotaVoice.java を実機にデプロイ＆コンパイル(純正TTS/ASR用)。"""
        cls = "%s/SotaVoice.class" % ROBOT_WORK
        if not force and self._exists(cls):
            return
        self._put(_JAVA_SRC, "%s/SotaVoice.java" % ROBOT_WORK)
        rc, out, err = self._exec(
            "cd %s && %s -encoding UTF-8 -cp '%s' SotaVoice.java"
            % (ROBOT_WORK, JAVAC, ROBOT_CP))
        if not self._exists(cls):
            raise RuntimeError("SotaVoice compile failed:\n%s\n%s" % (out, err))

    def _run_bridge(self, argstr, timeout=60):
        """実機 Java ブリッジ SotaVoice を所定の引数で実行し (rc, out, err) を返す。"""
        self.ensure_voice_bridge()
        cmd = ("cd %s && LANG=en_US.UTF-8 %s -Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8 "
               "-cp '%s' -Djna.library.path=%s SotaVoice %s"
               % (ROBOT_WORK, JAVA, ROBOT_CP, ROBOT_JNA, argstr))
        return self._exec(cmd, timeout=timeout)

    def say_native(self, text, rate=11, pitch=13, intonation=11):
        """実機内蔵(Vstone純正)TTSで発話(口LED同期)。利用には Vstone SDK 側の対応が必要。"""
        rc, out, err = self._run_bridge("say %d %d %d %s" % (rate, pitch, intonation, text))
        line = (out.strip().splitlines() or [""])[0]
        if not line.startswith("OK"):
            raise RuntimeError("native TTS failed: %s\n%s" % (out, err))
        return True

    def close(self):
        try:
            if self._mem is not None:
                self._mem.close()
        except Exception:
            pass
        try:
            self.cli.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


if __name__ == "__main__":
    import sys
    voices_path, argv = pop_voices_arg(sys.argv)
    if len(argv) < 2:
        sys.exit("usage: python3 sota_audio.py [--robot_voices=PATH] <robot_ip> [text]")
    host = argv[1]
    text = argv[2] if len(argv) > 2 else "こんにちは。ソータです。"
    with SotaAudio(host, voices_path=voices_path) as a:
        print("TTS engine:", a.tts_engine)
        a.say(text)
        print("said:", text)
