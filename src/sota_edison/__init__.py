"""sota_edison - PC から Vstone Sota(Intel Edison版) をネットワーク越し(TCP)に制御する Python ライブラリ。

主要シンボルはトップレベルから import できる(遅延ロード)。重い依存(paramiko / opencv /
faster-whisper など)は、その機能を実際に使うサブモジュールを参照したときに初めて読み込まれる。

    from sota_edison import Sota                # サーボ制御(core, 標準ライブラリのみ)
    from sota_edison import SotaAudio           # 音声(audio, 要 paramiko)
    from sota_edison import vision as sv        # 画像処理(要 opencv)
"""
import importlib

__version__ = "0.1.0"

# 公開シンボル -> 定義サブモジュール
_EXPORTS = {
    "Sota": "core",
    "NAME": "core",
    "ALL_IDS": "core",
    "INIT_POSE": "core",
    "Gestures": "gestures",
    "GESTURE_LIST": "gestures",
    "SotaCamera": "camera",
    "SotaFaceTracker": "camera",
    "SotaAudio": "audio",
    "robot_voice": "audio",
    "load_robot_voices": "audio",
    "set_robot_voice": "audio",
    "pop_voices_arg": "audio",
    "list_voicevox_speakers": "audio",
    "SotaASR": "asr",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name):
    mod = _EXPORTS.get(name)
    if mod is None:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    module = importlib.import_module("." + mod, __name__)
    return getattr(module, name)


def __dir__():
    return sorted(list(globals()) + __all__)
