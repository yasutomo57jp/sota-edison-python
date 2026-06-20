#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sota_asr - Sota のマイク音声を PC 側で音声認識(Whisper)するモジュール。

構成:
- ロボットで `arecord`(16kHz/mono/S16_LE)を連続実行し、生PCMを SSH 経由で PC にストリーム。
- PC 側で **webrtcvad により発話区間(VAD)を切り出し**、区間ごとに **faster-whisper** で文字起こし。
- 音声認識は PC 側で完結する(クラウドへ送らない)。GPU不可環境を想定し CPU(int8)で動かす。

依存(PC): paramiko, webrtcvad, faster-whisper, numpy
  実行例: uv run --with paramiko --with webrtcvad --with faster-whisper --with numpy \
              python3 demo/demo_asr.py 192.0.2.10

使い方:
    from sota_asr import SotaASR
    with SotaASR("192.0.2.10", model="small") as asr:
        asr.listen(on_text=lambda text, info: print(text))
"""
import collections
import time

import numpy as np
import paramiko

RATE = 16000
CHANNELS = 1
FRAME_MS = 30                       # webrtcvad フレーム長(10/20/30のいずれか)
FRAME_BYTES = int(RATE * FRAME_MS / 1000) * 2   # 16bit mono => *2

# 実機の録音コマンド。実機では **system-mode pulseaudio が USB マイクを占有**しているため、
# `pasuspender` で一時的に pulse を退避してから arecord で直接 hw を掴む(plug で 16k/mono へ)。
# ※pasuspender 中は pulse 再生が止まるので、別個体で発話させて本機で録る使い方(クロステスト)が前提。
#   マイクが USB の不安定状態で開けない場合は実機の電源を入れ直すと回復する。
ARECORD_CMD = ("pasuspender -- arecord -D plughw:CODEC -f S16_LE -r %d -c %d -t raw -q -"
               % (RATE, CHANNELS))


def pcm16_to_float32(pcm_bytes):
    """16bit LE PCM bytes -> float32 [-1,1] numpy 配列。"""
    return np.frombuffer(pcm_bytes, dtype="<i2").astype(np.float32) / 32768.0


class _VadSegmenter:
    """webrtcvad で連続フレームから発話区間を切り出す collector。

    発話頭が切れないよう、トリガ判定窓(短い・敏感)とは別に長めのプリロール(発話前の数百ms)を
    常時保持し、発話確定時にそれを先頭へ含める。
    """

    def __init__(self, aggressiveness=2, trigger_window_ms=150, start_ratio=0.6,
                 preroll_ms=500, min_speech_ms=150, end_silence_ms=700):
        import webrtcvad
        self.vad = webrtcvad.Vad(aggressiveness)
        self.tw = max(1, trigger_window_ms // FRAME_MS)
        self.start_ratio = start_ratio
        self.preroll_n = max(1, preroll_ms // FRAME_MS)
        self.min_speech = max(1, min_speech_ms // FRAME_MS)
        self.end_silence = max(1, end_silence_ms // FRAME_MS)
        self.reset()

    def reset(self):
        self.tring = collections.deque(maxlen=self.tw)       # トリガ判定窓(is_speechのbool)
        self.preroll = collections.deque(maxlen=self.preroll_n)  # プリロール音声(frame bytes)
        self.triggered = False
        self.voiced = []          # 発話中に貯めるフレーム(bytes)
        self.silence_run = 0

    def push(self, frame):
        """1フレーム(FRAME_BYTES)を投入。発話が確定したらその区間bytesを返す(無ければ None)。"""
        is_speech = self.vad.is_speech(frame, RATE)
        if not self.triggered:
            self.preroll.append(frame)
            self.tring.append(is_speech)
            if sum(self.tring) >= self.start_ratio * self.tring.maxlen:
                self.triggered = True
                self.voiced = list(self.preroll)   # プリロール(発話頭含む)を先頭に
                self.silence_run = 0
            return None
        # 発話中
        self.voiced.append(frame)
        if is_speech:
            self.silence_run = 0
        else:
            self.silence_run += 1
            if self.silence_run >= self.end_silence:
                seg = b"".join(self.voiced)
                spoke = len(self.voiced) - self.silence_run
                self.reset()
                if spoke >= self.min_speech:
                    return seg
                return None
        return None

    def flush(self):
        """ストリーム終了時、発話中なら残りを返す。"""
        if self.triggered and len(self.voiced) >= self.min_speech:
            seg = b"".join(self.voiced)
            self.reset()
            return seg
        self.reset()
        return None


class SotaASR(object):
    def __init__(self, host, user="root", password="edison00", timeout=15,
                 model="small", device="cpu", compute_type="int8", lang="ja",
                 vad_aggressiveness=2):
        self.host = host
        self.lang = lang
        self.cli = paramiko.SSHClient()
        self.cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.cli.connect(host, username=user, password=password, timeout=timeout,
                         look_for_keys=False, allow_agent=False)
        self._model_args = (model, device, compute_type)
        self._model = None
        self._vad_aggr = vad_aggressiveness

    # ---- Whisper(遅延ロード) ----
    @property
    def model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            name, device, ctype = self._model_args
            self._model = WhisperModel(name, device=device, compute_type=ctype)
        return self._model

    def transcribe(self, pcm_bytes):
        """16bit PCM の1発話を文字起こしして文字列を返す。"""
        audio = pcm16_to_float32(pcm_bytes)
        segments, _info = self.model.transcribe(
            audio, language=self.lang, beam_size=1, vad_filter=False)
        return "".join(s.text for s in segments).strip()

    # ---- 連続認識 ----
    def listen(self, on_text=None, seconds=None, on_segment=None):
        """マイクに話しかけると、発話ごとに認識して on_text(text, info) を呼ぶ。

        seconds=None で停止(KeyboardInterrupt)まで継続。on_segment(pcm_bytes) は
        切り出した生音声を受け取りたい場合のコールバック(任意)。
        認識結果のリストを返す。
        """
        seg = _VadSegmenter(aggressiveness=self._vad_aggr)
        self._kill_capture()   # 念のため残存 arecord を掃除してからマイクを掴む
        chan = self.cli.get_transport().open_session()
        chan.settimeout(1.0)
        chan.exec_command(ARECORD_CMD)
        results = []
        buf = b""
        deadline = (time.time() + seconds) if seconds else None
        try:
            while True:
                if deadline and time.time() > deadline:
                    break
                try:
                    data = chan.recv(8192)
                except Exception:
                    if chan.exit_status_ready():
                        break
                    continue
                if not data:
                    if chan.exit_status_ready():
                        break
                    continue
                buf += data
                while len(buf) >= FRAME_BYTES:
                    frame, buf = buf[:FRAME_BYTES], buf[FRAME_BYTES:]
                    segment = seg.push(frame)
                    if segment is not None:
                        self._emit(segment, results, on_text, on_segment)
        finally:
            try:
                tail = seg.flush()
                if tail:
                    self._emit(tail, results, on_text, on_segment)
            except Exception:
                pass
            try:
                chan.close()
            except Exception:
                pass
            # 実機に残った arecord/pasuspender を確実に終了(掴みっぱなしでデバイスが
            # wedge するのを防ぐ)。中断(KeyboardInterrupt)時もこの finally で掃除される。
            self._kill_capture()
        return results

    def _kill_capture(self):
        try:
            i, o, e = self.cli.exec_command("killall arecord pasuspender 2>/dev/null; true")
            o.channel.recv_exit_status()
        except Exception:
            pass

    def _emit(self, segment, results, on_text, on_segment):
        if on_segment:
            try:
                on_segment(segment)
            except Exception:
                pass
        dur = len(segment) / 2.0 / RATE
        text = self.transcribe(segment)
        info = {"duration": dur}
        if text:
            results.append(text)
            if on_text:
                on_text(text, info)

    def close(self):
        try:
            self.cli.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
