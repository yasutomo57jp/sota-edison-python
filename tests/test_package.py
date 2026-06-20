"""パッケージのトップレベルAPI(遅延re-export)のテスト。"""
import pytest

import sota_edison


def test_version_is_string():
    assert isinstance(sota_edison.__version__, str)


def test_all_lists_expected_symbols():
    for name in ["Sota", "Gestures", "SotaAudio", "SotaASR", "SotaCamera",
                 "SotaFaceTracker", "robot_voice", "pop_voices_arg"]:
        assert name in sota_edison.__all__


def test_lazy_export_core_symbol():
    # Sota は core(標準ライブラリのみ)。トップレベルからアクセスできる。
    assert isinstance(sota_edison.Sota, type)


def test_unknown_attribute_raises():
    with pytest.raises(AttributeError):
        _ = sota_edison.ThisDoesNotExist
