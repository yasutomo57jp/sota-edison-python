#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sota_gestures - Sota の名前付きジェスチャ集（Human-Robot Interaction 向け）。

`sotapy.Sota` のインスタンスを渡して使う:

    from sotapy import Sota
    from sota_gestures import Gestures
    with Sota("192.0.2.10") as s:
        s.servo_on()
        g = Gestures(s)
        g.bow()
        g.nod()
        g.wave_hand("right")

角度は 0.1度単位。各サーボはライブラリ側で可動範囲にクランプされる。
既知の向き: head_yaw 正=ロボットの左 / head_pitch 正=上 / 腕上げは顔非干渉に調整済み。
"""
import time

from .core import (INIT_POSE,
                   SV_BODY_Y, SV_L_SHOULDER, SV_L_ELBOW,
                   SV_R_SHOULDER, SV_R_ELBOW,
                   SV_HEAD_Y, SV_HEAD_P, SV_HEAD_R)

# rest(初期姿勢)の肩・肘
R_SH_REST = INIT_POSE[SV_R_SHOULDER]   # 900
L_SH_REST = INIT_POSE[SV_L_SHOULDER]   # -900
R_EL_REST = INIT_POSE[SV_R_ELBOW]      # 0
L_EL_REST = INIT_POSE[SV_L_ELBOW]      # 0


class Gestures(object):
    def __init__(self, sota):
        self.s = sota

    # ------------------------------------------------------------------
    # 共通ヘルパ
    # ------------------------------------------------------------------
    def _osc(self, servo, center, amp, times=2, half_ms=350, return_center=True):
        """servo を center±amp で times 回ゆらす。最後は center へ戻す。"""
        for _ in range(times):
            self.s.set_servo(servo, center + amp, half_ms)
            self.s.set_servo(servo, center - amp, half_ms)
        if return_center:
            self.s.set_servo(servo, center, half_ms)

    def neutral(self, msec=800):
        """初期姿勢へ。"""
        self.s.reset_pose(msec)

    # ------------------------------------------------------------------
    # あいさつ・対話の基本
    # ------------------------------------------------------------------
    def bow(self, depth=-200, hold=0.6, msec=600):
        """お辞儀（頭を深く下げて会釈）。"""
        self.s.head_pitch(depth, msec)
        time.sleep(hold)
        self.s.head_pitch(0, msec)

    def nod(self, times=2, msec=300):
        """うなずき（はい）。頭を上下に振る。"""
        self._osc(SV_HEAD_P, center=-60, amp=110, times=times, half_ms=msec)
        self.s.head_pitch(0, msec)

    def shake_head(self, times=2, msec=300):
        """いやいや（いいえ）。頭を左右に振る。"""
        self._osc(SV_HEAD_Y, center=0, amp=430, times=times, half_ms=msec)

    def tilt_head(self, side="right", amount=220, hold=1.0, msec=500):
        """首をかしげる（考え中/ん?）。side: right/left。"""
        sign = 1 if side == "right" else -1
        self.s.head_roll(sign * amount, msec)
        time.sleep(hold)
        self.s.head_roll(0, msec)

    def raise_right_hand(self, msec=800):
        """右手を上げる。"""
        self.s.raise_right_hand(msec)

    def raise_left_hand(self, msec=800):
        """左手を上げる。"""
        self.s.raise_left_hand(msec)

    def banzai(self, msec=800):
        """両手を上げる（バンザイ）。"""
        self.s.raise_both_hands(msec)

    def wave_hand(self, side="right", times=3, msec=260):
        """手を振る（バイバイ）。腕を上げて前腕を左右に振る。

        肘は顔に当たらない安全域(<=300)で振る。
        """
        if side == "right":
            self.s.play({SV_R_SHOULDER: -500, SV_R_ELBOW: 50}, 700)
            self._osc(SV_R_ELBOW, center=50, amp=250, times=times,
                      half_ms=msec, return_center=False)
        else:
            self.s.play({SV_L_SHOULDER: 500, SV_L_ELBOW: -50}, 700)
            self._osc(SV_L_ELBOW, center=-50, amp=250, times=times,
                      half_ms=msec, return_center=False)
        self.lower_hands(700)

    def high_five(self, side="right", hold=1.5, msec=700):
        """ハイタッチ（片腕を前方やや上に伸ばして相手の手を待つ）。"""
        if side == "right":
            self.s.play({SV_R_SHOULDER: -150, SV_R_ELBOW: 250}, msec)
        else:
            self.s.play({SV_L_SHOULDER: 150, SV_L_ELBOW: -250}, msec)
        time.sleep(hold)
        self.lower_hands(msec)

    def lower_hands(self, msec=700):
        """両腕を初期位置（下げ）へ戻す。"""
        self.s.play({SV_R_SHOULDER: R_SH_REST, SV_R_ELBOW: R_EL_REST,
                     SV_L_SHOULDER: L_SH_REST, SV_L_ELBOW: L_EL_REST}, msec)

    # ------------------------------------------------------------------
    # 相づち・感情表現
    # ------------------------------------------------------------------
    def cheer(self, msec=600):
        """喜ぶ（両手を上げて頭を弾ませる）。"""
        self.s.raise_both_hands(msec)
        self._osc(SV_HEAD_P, center=-20, amp=70, times=2, half_ms=240)
        self.s.head_pitch(0, 300)
        self.lower_hands(msec)

    def sad(self, hold=1.5, msec=800):
        """しょんぼり（頭をうつむけて静止）。"""
        self.s.play({SV_HEAD_P: -230, SV_HEAD_R: 80}, msec)
        time.sleep(hold)
        self.s.look(0, 0, 0, msec)

    def surprise(self, hold=0.8, msec=250):
        """驚く（頭をさっと上げ、両腕を少し上げる）。"""
        self.s.play({SV_HEAD_P: 70, SV_R_SHOULDER: 350, SV_L_SHOULDER: -350}, msec)
        time.sleep(hold)
        self.s.head_pitch(0, 400)
        self.lower_hands(500)

    def thinking(self, hold=1.8, msec=900):
        """考える人ポーズ（右手をあご元へ、左手を右肘へ添え、首をかしげる）。"""
        self.s.play({SV_R_SHOULDER: -300, SV_R_ELBOW: 600,
                     SV_L_SHOULDER: -350, SV_L_ELBOW: -650,
                     SV_HEAD_Y: 200, SV_HEAD_P: 30, SV_HEAD_R: 200}, msec)
        time.sleep(hold)
        self.s.look(0, 0, 0, 500)
        self.lower_hands(msec)

    def clap(self, times=5, msec=180):
        """拍手（両手を体の前(お腹あたり)で合わせて小刻みに叩く）。"""
        self.s.play({SV_R_SHOULDER: 550, SV_R_ELBOW: 680,
                     SV_L_SHOULDER: -550, SV_L_ELBOW: -680}, 700)
        for _ in range(times):
            self.s.play({SV_R_ELBOW: 900, SV_L_ELBOW: -900}, msec)
            self.s.play({SV_R_ELBOW: 680, SV_L_ELBOW: -680}, msec)
        self.lower_hands(700)

    # ------------------------------------------------------------------
    # 注意誘導・身体表現
    # ------------------------------------------------------------------
    def point(self, side="right", hold=1.5, msec=700):
        """指さす（片腕を前方へ伸ばし、頭をその方向へ向ける）。"""
        if side == "right":
            self.s.play({SV_R_SHOULDER: 100, SV_R_ELBOW: 0, SV_HEAD_Y: -350}, msec)
        else:
            self.s.play({SV_L_SHOULDER: -100, SV_L_ELBOW: 0, SV_HEAD_Y: 350}, msec)
        time.sleep(hold)
        self.s.head_yaw(0, msec)
        self.lower_hands(msec)

    def look_around(self, msec=900):
        """きょろきょろ見回す。頭ヨーを左右に走査。"""
        self.s.head_yaw(500, msec)
        self.s.head_yaw(-500, msec)
        self.s.head_yaw(0, msec)

    def turn_body(self, deg10, msec=900):
        """体を指定角度に向ける（body_yaw のエイリアス）。"""
        self.s.body_yaw(deg10, msec)

    def idle_breathing(self, cycles=3, msec=900):
        """アイドル微動（肩・頭をゆっくり周期運動して生命感を出す）。"""
        for _ in range(cycles):
            self.s.play({SV_R_SHOULDER: R_SH_REST - 40,
                         SV_L_SHOULDER: L_SH_REST + 40,
                         SV_HEAD_P: 15}, msec)
            self.s.play({SV_R_SHOULDER: R_SH_REST,
                         SV_L_SHOULDER: L_SH_REST,
                         SV_HEAD_P: 0}, msec)


# ジェスチャ名→説明（デモ・一覧用）
GESTURE_LIST = [
    ("bow", "お辞儀"),
    ("nod", "うなずき(はい)"),
    ("shake_head", "いやいや(いいえ)"),
    ("tilt_head", "首をかしげる"),
    ("raise_right_hand", "右手を上げる"),
    ("raise_left_hand", "左手を上げる"),
    ("banzai", "バンザイ(両手)"),
    ("wave_hand", "手を振る(バイバイ)"),
    ("high_five", "ハイタッチ"),
    ("cheer", "喜ぶ"),
    ("sad", "しょんぼり"),
    ("surprise", "驚く"),
    ("thinking", "考える"),
    ("clap", "拍手"),
    ("point", "指さす"),
    ("look_around", "きょろきょろ"),
    ("idle_breathing", "アイドル微動"),
]
