"""ハードウェア不要の純粋ロジックのテスト(サーボ定義・クランプ)。"""
from sota_edison.core import clamp, SERVO_DEF, INIT_POSE, NAME, ALL_IDS


def test_clamp_within_range():
    assert clamp(5, 0, 10) == 5


def test_clamp_below_low():
    assert clamp(-5, 0, 10) == 0


def test_clamp_above_high():
    assert clamp(50, 0, 10) == 10


def test_clamp_on_boundaries():
    assert clamp(0, 0, 10) == 0
    assert clamp(10, 0, 10) == 10


def test_tables_cover_all_servo_ids():
    assert set(SERVO_DEF) == set(ALL_IDS)
    assert set(NAME) == set(ALL_IDS)
    assert set(INIT_POSE) == set(ALL_IDS)


def test_init_pose_is_within_limits():
    for sid, pos in INIT_POSE.items():
        lo, hi, _offset, _bank = SERVO_DEF[sid]
        assert lo <= pos <= hi, "servo %d init %d out of [%d,%d]" % (sid, pos, lo, hi)


def test_servo_def_ranges_are_valid():
    for sid, (lo, hi, _offset, bank) in SERVO_DEF.items():
        assert lo < hi
        assert bank in (0, 1, 2, 3)
