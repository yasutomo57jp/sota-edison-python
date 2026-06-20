"""声設定(robot_voices.json)読み込み・CLI上書き引数のテスト。ハードウェア不要。"""
import json

import pytest

from sota_edison import (pop_voices_arg, load_robot_voices, robot_voice,
                         set_robot_voice)


def test_pop_voices_arg_extracts_path():
    path, rest = pop_voices_arg(["prog", "--robot_voices=foo.json", "192.0.2.10", "192.0.2.11"])
    assert path == "foo.json"
    assert rest == ["prog", "192.0.2.10", "192.0.2.11"]


def test_pop_voices_arg_absent():
    path, rest = pop_voices_arg(["prog", "192.0.2.10"])
    assert path is None
    assert rest == ["prog", "192.0.2.10"]


def test_pop_voices_arg_only_equals_form_is_recognized():
    # '--robot_voices'(=なし) はオプションとして扱わず argv に残す
    path, rest = pop_voices_arg(["prog", "--robot_voices", "x"])
    assert path is None
    assert "--robot_voices" in rest


def test_load_skips_comment_keys(tmp_path):
    p = tmp_path / "v.json"
    p.write_text(json.dumps({
        "_comment": "ignore me",
        "default": {"engine": "voicevox", "speaker": 3},
        "192.0.2.50": {"engine": "gtts", "speaker": 1},
    }), encoding="utf-8")
    voices = load_robot_voices(str(p))
    assert "_comment" not in voices
    assert "192.0.2.50" in voices


def test_robot_voice_lookup_and_default_fallback(tmp_path):
    p = tmp_path / "v.json"
    p.write_text(json.dumps({
        "default": {"engine": "voicevox", "speaker": 3},
        "192.0.2.50": {"engine": "gtts", "speaker": 1},
    }), encoding="utf-8")
    assert robot_voice("192.0.2.50", str(p))["engine"] == "gtts"
    # 未登録ホストは default にフォールバック
    assert robot_voice("10.0.0.1", str(p))["speaker"] == 3


def test_missing_file_returns_empty():
    assert load_robot_voices("/no/such/voices.json") == {}


def test_packaged_default_voices_loads():
    # 同梱の robot_voices.json が読める(パッケージデータ)
    assert isinstance(load_robot_voices(), dict)


def test_set_robot_voice_roundtrip(tmp_path):
    p = tmp_path / "v.json"
    p.write_text(json.dumps({"default": {"engine": "voicevox", "speaker": 3}}), encoding="utf-8")
    entry = set_robot_voice("192.0.2.77", speaker=5, engine="gtts", path=str(p))
    assert entry == {"speaker": 5, "engine": "gtts"}
    again = robot_voice("192.0.2.77", str(p))
    assert again["speaker"] == 5 and again["engine"] == "gtts"
