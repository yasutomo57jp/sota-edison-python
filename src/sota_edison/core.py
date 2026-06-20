#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sotapy - ロボット Sota (Intel Edison版 / ファーム vs-rc020) を
PCから Python で制御するための軽量ライブラリ。

- 依存ライブラリ無し（Python標準ライブラリのみ）。
- ロボット常駐の vsmd_edison が TCP 6498 で公開している
  共有メモリ(レジスタマップ)へ読み書きしてサーボを制御する。

プロトコル(ポート6498, ASCIIテキスト):
  接続時バナー : "#vs-rc020 (...)\n"
  書込         : "w <4桁hexアドレス> <byte0> <byte1> ...\r\n"   (リトルエンディアン)
  読出         : "R <4桁hexアドレス> <size10進>\r\n"
                 → 応答 "#<addr> <b0> <b1> ...\r\n"

サーボ単位は 0.1度 (例: 900 = 90.0度)。

使い方の例:
    from sotapy import Sota
    with Sota("192.0.2.10") as sota:
        sota.servo_on()
        sota.reset_pose()
        sota.raise_right_hand()
        sota.head_yaw(45)       # 顔を右に45度
        sota.body_yaw(-30)      # 体を左に30度
"""

import socket
import time

# ---- サーボID（部位）定数 -------------------------------------------------
SV_BODY_Y = 1      # 体(腰)の左右回転
SV_L_SHOULDER = 2  # 左肩 (左腕の上げ下げ)
SV_L_ELBOW = 3     # 左肘
SV_R_SHOULDER = 4  # 右肩 (右腕の上げ下げ)
SV_R_ELBOW = 5     # 右肘
SV_HEAD_Y = 6      # 頭ヨー (左右)
SV_HEAD_P = 7      # 頭ピッチ (上下)
SV_HEAD_R = 8      # 頭ロール (傾げ)

ALL_IDS = [1, 2, 3, 4, 5, 6, 7, 8]

NAME = {
    1: "BODY_Y", 2: "L_SHOULDER", 3: "L_ELBOW", 4: "R_SHOULDER",
    5: "R_ELBOW", 6: "HEAD_Y", 7: "HEAD_P", 8: "HEAD_R",
}

# memdef.conf (Sota_Normal) より: id -> (min, max, offset, readAngleBank)
SERVO_DEF = {
    1: (-1200, 1200,    0, 3),
    2: (-1400, 1000,  105, 0),
    3: (-900,   300,    0, 1),
    4: (-1000, 1400, -105, 0),
    5: (-300,   900,    0, 1),
    6: (-1450, 1450,    0, 3),
    7: (-290,    80,    0, 2),
    8: (-250,   250,    0, 2),
}

# 初期姿勢(直立・腕下げ)。単位0.1度。
INIT_POSE = {1: 0, 2: -900, 3: 0, 4: 900, 5: 0, 6: 0, 7: 0, 8: 0}

# ---- レジスタ(byte)アドレス ----------------------------------------------
A_FIRMWARE_REV = 16
A_MASTER_PERIOD = 64
A_SERVO_EN = 72
A_SERVO_SEND_EN = 74
A_SERVO_BUS_PROTOCOL = 160
A_SERVO_BUS_NUM = 161
A_SERVO_BUS_IDS = 162
A_READ_PROTO = {0: 192, 1: 208, 2: 224, 3: 240}
A_READ_NUM = {0: 193, 1: 209, 2: 225, 3: 241}
A_READ_IDS = {0: 194, 1: 210, 2: 226, 3: 242}
A_TIMER_LIST = 496        # 補間タイマースロット (slot0 を使用)
A_POS_TARGET = 2560       # +id*2
A_TORQUE_TARGET = 2624    # +id*2
A_POS_TRIGGER_PTR = 2816  # +id*2
A_TORQUE_TRIGGER_PTR = 2880  # +id*2
A_POS_OUTPUT = 3072       # +id*2
A_POS_REMAIN = 3328       # +id*2  補間残り時間(サイクル)。0で完了。
A_POS_LIMIT_LOW = 3584    # +id*2
A_POS_LIMIT_HIGH = 3648   # +id*2
A_READ_POS = 3712         # +id*2
A_SERVO_OFFSET = 3776     # +id*2

TIMER_SLOT_ADDR = A_TIMER_LIST  # slot0
TORQUE_ON = 100


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class Mem(object):
    """vsmd の共有メモリへ TCP(6498) でアクセスする低レベルクライアント。"""

    def __init__(self, host, port=6498, timeout=3.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock = None
        self.buf = b""
        self.connect()

    def connect(self):
        self.close()
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock.settimeout(self.timeout)
        self.buf = b""
        self._readline()  # 接続時バナーを読み捨てる

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None

    def _readline(self):
        while b"\n" not in self.buf:
            d = self.sock.recv(4096)
            if not d:
                break
            self.buf += d
        line, _, self.buf = self.buf.partition(b"\n")
        return line.decode("ascii", "replace").strip()

    # --- 書き込み（リトルエンディアン） ---
    def _write(self, addr, data_bytes):
        cmd = "w %04x" % addr
        for b in data_bytes:
            cmd += " %02x" % (b & 0xFF)
        cmd += "\r\n"
        for _ in range(3):
            try:
                self.sock.sendall(cmd.encode("ascii"))
                return True
            except Exception:
                self.connect()
        return False

    def w_s16(self, addr, value):
        value = int(value) & 0xFFFF
        return self._write(addr, [value & 0xFF, (value >> 8) & 0xFF])

    def w_u16(self, addr, value):
        return self.w_s16(addr, value)

    def w_u8(self, addr, value):
        return self._write(addr, [int(value) & 0xFF])

    def w_u8_array(self, addr, values):
        return self._write(addr, [int(v) & 0xFF for v in values])

    # --- 読み出し ---
    def _read(self, addr, size):
        cmd = ("R %04x %d\r\n" % (addr, size)).encode("ascii")
        for _ in range(3):
            try:
                self.sock.sendall(cmd)
                toks = self._readline().split()
                if len(toks) >= 1 + size:
                    return [int(t, 16) for t in toks[1:1 + size]]
            except Exception:
                pass
            self.connect()
        raise IOError("read failed at addr 0x%04x" % addr)

    def r_s16(self, addr):
        b = self._read(addr, 2)
        v = b[0] | (b[1] << 8)
        return v - 0x10000 if v & 0x8000 else v

    def r_u16(self, addr):
        b = self._read(addr, 2)
        return b[0] | (b[1] << 8)

    def r_u8(self, addr):
        return self._read(addr, 1)[0]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class Sota(object):
    """Sota の高レベル制御。角度はすべて 0.1度単位の int。"""

    def __init__(self, host, auto_init=True):
        self.mem = Mem(host)
        self.master_period = 16666.6667
        if auto_init:
            self.init()

    # ---------------- 初期化 ----------------
    def init(self, force=False):
        """ロボットをサーボ制御可能な状態にする(InitRobot相当)。

        未設定(BusNum!=8)のロボットには全設定を書き込む。設定済みなら省略。
        """
        rev = self.mem.r_u16(A_FIRMWARE_REV)
        if rev < 20:
            raise RuntimeError("vsmd firmware too old: rev=%d" % rev)
        try:
            self.master_period = float(self._read_u32(A_MASTER_PERIOD))
        except Exception:
            pass

        busnum = self.mem.r_u8(A_SERVO_BUS_NUM)
        if force or busnum != len(ALL_IDS):
            self._write_servo_config()
        return True

    def _read_u32(self, addr):
        b = self.mem._read(addr, 4)
        return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)

    def _write_servo_config(self):
        m = self.mem
        m.w_u8(A_SERVO_BUS_PROTOCOL, 1)
        m.w_u8(A_SERVO_BUS_NUM, len(ALL_IDS))
        m.w_u8_array(A_SERVO_BUS_IDS, ALL_IDS)
        m.w_s16(A_SERVO_SEND_EN, 1)
        m.w_s16(A_SERVO_EN, 0)  # 設定中は脱力
        # リミット・オフセット
        for sid, (lo, hi, off, _bank) in SERVO_DEF.items():
            m.w_s16(A_POS_LIMIT_LOW + sid * 2, lo)
            m.w_s16(A_POS_LIMIT_HIGH + sid * 2, hi)
            m.w_s16(A_SERVO_OFFSET + sid * 2, off)
        # 角度読み取りバンク設定
        banks = {0: [], 1: [], 2: [], 3: []}
        for sid, (_lo, _hi, _off, bank) in SERVO_DEF.items():
            banks[bank].append(sid)
        for bank, ids in banks.items():
            m.w_u8(A_READ_PROTO[bank], 1)
            m.w_u8(A_READ_NUM[bank], len(ids))
            if ids:
                m.w_u8_array(A_READ_IDS[bank], ids)
        # トリガポインタを共通タイマースロットへ
        for sid in ALL_IDS:
            m.w_u16(A_POS_TRIGGER_PTR + sid * 2, TIMER_SLOT_ADDR)
            m.w_u16(A_TORQUE_TRIGGER_PTR + sid * 2, TIMER_SLOT_ADDR)
        time.sleep(0.2)  # vsmd が実機角度を読み込むのを待つ

    # ---------------- サーボ ON/OFF ----------------
    def servo_on(self, settle_ms=300):
        """脱力状態から、現在角度を目標にしてトルクON→ServoEN=1。急動作を防ぐ。"""
        m = self.mem
        # 現在の実測角度(無効なら出力値)を目標に設定して飛び出しを防ぐ
        for sid in ALL_IDS:
            cur = m.r_s16(A_READ_POS + sid * 2)
            if cur == -32768 or cur == 0:
                cur = m.r_s16(A_POS_OUTPUT + sid * 2)
            lo, hi, _o, _b = SERVO_DEF[sid]
            m.w_s16(A_POS_TARGET + sid * 2, clamp(cur, lo, hi))
            m.w_s16(A_TORQUE_TARGET + sid * 2, TORQUE_ON)
            m.w_u16(A_POS_TRIGGER_PTR + sid * 2, TIMER_SLOT_ADDR)
            m.w_u16(A_TORQUE_TRIGGER_PTR + sid * 2, TIMER_SLOT_ADDR)
        self._trigger(100)
        time.sleep(0.12)
        m.w_s16(A_SERVO_EN, 1)
        time.sleep(settle_ms / 1000.0)

    def servo_off(self):
        """全サーボ脱力。"""
        self.mem.w_s16(A_SERVO_EN, 0)

    # ---------------- 低レベル pose 再生 ----------------
    def _trigger(self, msec):
        cycles = int(round(msec * 1000.0 / self.master_period))
        cycles = clamp(cycles, 1, 65535)
        self.mem.w_u16(TIMER_SLOT_ADDR, cycles)

    def play(self, pose, msec=800, wait=True):
        """pose = {servo_id: 角度(0.1度)} を msec かけて補間動作。"""
        m = self.mem
        ids = list(pose.keys())
        for sid, deg in pose.items():
            lo, hi, _o, _b = SERVO_DEF[sid]
            m.w_s16(A_POS_TARGET + sid * 2, clamp(int(deg), lo, hi))
            m.w_u16(A_POS_TRIGGER_PTR + sid * 2, TIMER_SLOT_ADDR)
        self._trigger(msec)
        if wait:
            self.wait_motion(ids, msec)

    def wait_motion(self, ids, msec):
        """補間完了まで待つ。

        補間は概ね msec で完了する(タイマースロットはトリガ受理後すぐ65535へ戻るため
        完了判定には使えない)。所要時間スリープ後、各サーボの残り補間時間が0になるのを
        確認する。
        """
        time.sleep(msec / 1000.0)
        deadline = time.time() + 0.6
        while time.time() < deadline:
            if all(self.mem.r_u16(A_POS_REMAIN + sid * 2) in (0, 65535)
                   for sid in ids):
                return
            time.sleep(0.02)

    # ---------------- 状態取得 ----------------
    def get_read_pos(self):
        """各サーボの実測角度 {id: 0.1度}。"""
        return {sid: self.mem.r_s16(A_READ_POS + sid * 2) for sid in ALL_IDS}

    def get_target(self):
        return {sid: self.mem.r_s16(A_POS_TARGET + sid * 2) for sid in ALL_IDS}

    # ---------------- 高レベル動作 ----------------
    def reset_pose(self, msec=1000):
        """初期姿勢(直立・腕下げ)へ。"""
        self.play(dict(INIT_POSE), msec)

    def set_servo(self, servo_id, deg, msec=800, wait=True):
        """単一サーボを指定角度(0.1度)へ。"""
        self.play({servo_id: deg}, msec, wait)

    # --- 腕 (実機検証済みの姿勢。顔に当たらず自然に手が上がる) ---
    def raise_right_hand(self, msec=800):
        """右手を上げる(右肩を上方へ + 右肘をわずかに曲げる)。"""
        self.play({SV_R_SHOULDER: -500, SV_R_ELBOW: 200}, msec)

    def raise_left_hand(self, msec=800):
        """左手を上げる(右手の鏡写し)。"""
        self.play({SV_L_SHOULDER: 500, SV_L_ELBOW: -200}, msec)

    def lower_right_hand(self, msec=800):
        self.play({SV_R_SHOULDER: INIT_POSE[SV_R_SHOULDER], SV_R_ELBOW: 0}, msec)

    def lower_left_hand(self, msec=800):
        self.play({SV_L_SHOULDER: INIT_POSE[SV_L_SHOULDER], SV_L_ELBOW: 0}, msec)

    def raise_both_hands(self, msec=800):
        """両手を上げる(バンザイ)。"""
        self.play({SV_R_SHOULDER: -500, SV_R_ELBOW: 200,
                   SV_L_SHOULDER: 500, SV_L_ELBOW: -200}, msec)

    # --- 頭 ---
    def head_yaw(self, deg10, msec=600):
        """顔を左右に向ける。正=ロボットから見て一方向(実機で確認)。単位0.1度。"""
        self.set_servo(SV_HEAD_Y, deg10, msec)

    def head_pitch(self, deg10, msec=600):
        """顔を上下に向ける。単位0.1度。"""
        self.set_servo(SV_HEAD_P, deg10, msec)

    def head_roll(self, deg10, msec=600):
        """顔を傾げる。単位0.1度。"""
        self.set_servo(SV_HEAD_R, deg10, msec)

    def look(self, yaw=0, pitch=0, roll=0, msec=600):
        """頭の向きをまとめて指定(0.1度)。"""
        self.play({SV_HEAD_Y: yaw, SV_HEAD_P: pitch, SV_HEAD_R: roll}, msec)

    # --- 体 ---
    def body_yaw(self, deg10, msec=800):
        """体(腰)を指定角度に向ける。単位0.1度。"""
        self.set_servo(SV_BODY_Y, deg10, msec)

    def close(self):
        self.mem.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
