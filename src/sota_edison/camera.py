#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sota_camera - Sota 頭部カメラから PC へ静止画を取得するラッパー。

実機側に撮影用の小さな Java ツール(robot/SotaCam.java, ベンダ libsotacamv4l2 を使用)を
自動デプロイ＆コンパイルし、SSH で撮影 → JPEG を SFTP で PC に取得する。

依存: paramiko（実行は `uv run --with paramiko python3 ...` を想定）

使い方:
    from sota_camera import SotaCamera
    with SotaCamera("192.0.2.10") as cam:
        path = cam.capture("snap.jpg", size="VGA")   # ローカルに snap.jpg を保存
"""
import os
import time
import paramiko

ROBOT_LIB = "/home/vstone/lib"
ROBOT_WORK = "/home/vstone/lib-users"   # 777。撮影ツールを置く
JAVA = "/home/vstone/java/jdk1.8.0_40/bin/java"
JAVAC = "/home/vstone/java/jdk1.8.0_40/bin/javac"
REMOTE_SNAP = "/dev/shm/sota_snap.jpg"

# CAP_IMAGE_SIZE のインデックス
SIZES = {
    "QVGA": 0, "VGA": 1, "SVGA": 2, "XGA": 3, "HD720": 4,
    "SXGA": 5, "UXGA": 6, "HD1080": 7, "QXGA": 8, "5M": 9,
}

_JAVA_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "robot", "SotaCam.java")
_CP = "%s/sotalib.jar:%s/jna-4.1.0.jar" % (ROBOT_LIB, ROBOT_LIB)


class SotaCamera(object):
    def __init__(self, host, user="root", password="edison00", timeout=15):
        self.host = host
        self.cli = paramiko.SSHClient()
        self.cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.cli.connect(host, username=user, password=password, timeout=timeout,
                         look_for_keys=False, allow_agent=False)

    # ---- 低レベル ----
    def _exec(self, cmd, timeout=60):
        stdin, stdout, stderr = self.cli.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err

    def _exists(self, path):
        rc, _, _ = self._exec("test -e %s" % path)
        return rc == 0

    # ---- デプロイ ----
    def ensure_deployed(self, force=False):
        """撮影ツール(SotaCam.class)が無ければ Java ソースを送ってコンパイルする。"""
        class_path = "%s/SotaCam.class" % ROBOT_WORK
        if not force and self._exists(class_path):
            return
        sftp = self.cli.open_sftp()
        sftp.put(_JAVA_SRC, "%s/SotaCam.java" % ROBOT_WORK)
        sftp.close()
        rc, out, err = self._exec(
            "cd %s && %s -encoding UTF-8 -cp %s SotaCam.java" % (ROBOT_WORK, JAVAC, _CP))
        if rc != 0 or not self._exists(class_path):
            raise RuntimeError("SotaCam compile failed:\n%s\n%s" % (out, err))

    # ---- 撮影 ----
    def capture(self, local_path="sota_snap.jpg", size="VGA", settle=True):
        """カメラで1枚撮影してローカルに保存し、保存先パスを返す。

        size: "QVGA"/"VGA"/"SVGA"/"XGA"/"HD720"/... もしくは整数インデックス。
        """
        self.ensure_deployed()
        idx = SIZES.get(size, size) if isinstance(size, str) else size
        cmd = ("cd %s && %s -cp .:%s -Djna.library.path=%s SotaCam %s %d"
               % (ROBOT_WORK, JAVA, _CP, ROBOT_LIB, REMOTE_SNAP, idx))
        rc, out, err = self._exec(cmd, timeout=40)
        if rc != 0 or not self._exists(REMOTE_SNAP):
            raise RuntimeError("capture failed:\n%s\n%s" % (out, err))
        sftp = self.cli.open_sftp()
        sftp.get(REMOTE_SNAP, local_path)
        sftp.close()
        return local_path

    def close(self):
        try:
            self.cli.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


# OpenCV(java) native の場所。顔検出は CRoboCamera(OpenCV+PUX native)を使う。
_OPENCV_LIB = "/usr/local/share/OpenCV/java"
_FT_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "robot", "SotaFaceTrack.java")


class SotaFaceTracker(object):
    """頭部カメラで顔を検出し、頭サーボで自動追従する(ベンダ CRoboCamera.StartFaceTraking)。

    追従(頭の旋回)は実機側スレッドが PD 制御で行う。PC 側は検出状態(FACE行)を受け取るだけ。
    ※開始時に InitRobot で腕が初期姿勢へ動き、トルクON。終了時に脱力する。

        with SotaFaceTracker("192.0.2.10") as ft:
            ft.track(seconds=30, on_face=lambda cx, cy, w, h, smile: print(cx, cy))
    """

    def __init__(self, host, user="root", password="edison00", timeout=15):
        self.host = host
        self.cli = paramiko.SSHClient()
        self.cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.cli.connect(host, username=user, password=password, timeout=timeout,
                         look_for_keys=False, allow_agent=False)

    def _exec(self, cmd, timeout=60):
        stdin, stdout, stderr = self.cli.exec_command(cmd, timeout=timeout)
        rc = stdout.channel.recv_exit_status()
        return rc, stdout.read().decode("utf-8", "replace"), stderr.read().decode("utf-8", "replace")

    def _exists(self, path):
        rc, _, _ = self._exec("test -e %s" % path)
        return rc == 0

    def ensure_deployed(self, force=False):
        cls = "%s/SotaFaceTrack.class" % ROBOT_WORK
        if not force and self._exists(cls):
            return
        sftp = self.cli.open_sftp()
        sftp.put(_FT_SRC, "%s/SotaFaceTrack.java" % ROBOT_WORK)
        sftp.close()
        rc, out, err = self._exec(
            "cd %s && %s -encoding UTF-8 -cp '.:%s/*' SotaFaceTrack.java" % (ROBOT_WORK, JAVAC, ROBOT_LIB))
        if not self._exists(cls):
            raise RuntimeError("SotaFaceTrack compile failed:\n%s\n%s" % (out, err))

    def track(self, seconds=30, poll_ms=300, search=True, smile=False, on_face=None):
        """顔追従を seconds 秒実行。各検出で on_face(cx, cy, w, h, smile) を呼ぶ。

        search=True: 顔ロスト時に頭を振って探索。返り値は検出 [(cx, cy, w, h, smile), ...]。
        """
        self.ensure_deployed()
        lp = "%s:%s" % (ROBOT_LIB, _OPENCV_LIB)
        cmd = ("cd %s && %s -cp '.:%s/*' -Djava.library.path='%s' -Djna.library.path=%s "
               "SotaFaceTrack %d %d %d %d 2>&1"
               % (ROBOT_WORK, JAVA, ROBOT_LIB, lp, ROBOT_LIB,
                  seconds, poll_ms, 1 if search else 0, 1 if smile else 0))
        chan = self.cli.get_transport().open_session()
        chan.settimeout(seconds + 40)
        chan.exec_command(cmd)
        faces, buf = [], b""
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
                    if s.startswith("FACE"):
                        p = s.split()
                        rec = tuple(int(x) for x in p[1:6])
                        faces.append(rec)
                        if on_face:
                            on_face(*rec)
                    elif s.startswith("OK facetrack-done") or s.startswith("ERR"):
                        if s.startswith("ERR"):
                            raise RuntimeError("facetrack: " + s)
                        deadline = 0
            elif chan.exit_status_ready() and not chan.recv_ready():
                break
            else:
                time.sleep(0.05)
        try:
            chan.close()
        except Exception:
            pass
        return faces

    def close(self):
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
    if len(sys.argv) < 2:
        sys.exit("usage: python3 sota_camera.py <robot_ip> [output] [size]")
    host = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "sota_snap.jpg"
    size = sys.argv[3] if len(sys.argv) > 3 else "VGA"
    with SotaCamera(host) as cam:
        p = cam.capture(out, size=size)
        print("saved:", p)
