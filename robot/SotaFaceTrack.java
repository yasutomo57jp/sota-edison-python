// SotaFaceTrack - Sota の頭部カメラで顔を検出し、頭サーボで自動追従する最小CLIブリッジ。
//
// ベンダ jp.vstone.camera.CRoboCamera の StartFaceTraking() を使う。これは内部スレッドで
// VGA 顔検出を行い、顔の画面中心からのズレを PD 制御で HEAD_P/HEAD_Y に与えて頭を向ける
// (頭サーボはこのトラッカが LockServoHandle で占有する)。PC側のキャプチャループは不要。
//
// PC 側 sota_camera.py が自動デプロイ&コンパイルして SSH で実行する。
//   コンパイル: javac -encoding UTF-8 -cp .:/home/vstone/lib/* SotaFaceTrack.java
//   実行:       java -cp .:/home/vstone/lib/* -Djava.library.path=/home/vstone/lib \
//                    -Djna.library.path=/home/vstone/lib SotaFaceTrack <seconds> [pollMs] [search0/1]
//
// 出力: 起動時 "OK facetrack-ready <sec>s"、顔検出ごとに "FACE <cx> <cy> <w> <h> <smile>"、
//       終了時 "OK facetrack-done"。失敗時 "ERR ..."。

import java.awt.Rectangle;

import jp.vstone.RobotLib.CRobotMem;
import jp.vstone.RobotLib.CSotaMotion;
import jp.vstone.camera.CRoboCamera;
import jp.vstone.camera.FaceDetectResult;

public class SotaFaceTrack {

    public static void main(String[] args) {
        int seconds = args.length > 0 ? Integer.parseInt(args[0]) : 30;
        int pollMs = args.length > 1 ? Integer.parseInt(args[1]) : 300;
        boolean search = !(args.length > 2 && args[2].equals("0"));  // 既定: 顔ロスト時に探索ON
        boolean smile = args.length > 3 && args[3].equals("1");

        CRoboCamera cam = null;
        CSotaMotion motion = null;
        try {
            CRobotMem mem = new CRobotMem();
            mem.Connect();
            motion = new CSotaMotion(mem);
            motion.InitRobot_Sota();   // サーボ構成(現active memdef)で初期化。腕が初期姿勢へ動く
            motion.ServoOn();          // 現在角を保持してトルクON(頭が動かせる状態に)

            cam = new CRoboCamera("/dev/video0", motion);
            cam.setEnableFaceSearch(search);
            if (smile) cam.setEnableSmileDetect(true);
            cam.StartFaceTraking();    // 顔追従開始(頭が自動で顔を向く)
            System.out.println("OK facetrack-ready " + seconds + "s");
            System.out.flush();

            long end = System.currentTimeMillis() + seconds * 1000L;
            long nextTick = System.currentTimeMillis() + 3000L;
            while (System.currentTimeMillis() < end) {
                FaceDetectResult r = cam.getDetectResult();
                if (r != null && r.isDetect() && r.getFaceNum() > 0) {
                    Rectangle f = r.getRect(0);
                    int cx = (f != null) ? (int) f.getCenterX() : -1;
                    int cy = (f != null) ? (int) f.getCenterY() : -1;
                    int w = (f != null) ? f.width : -1;
                    int h = (f != null) ? f.height : -1;
                    int sm = smile ? r.getSmile() : -1;
                    System.out.println("FACE " + cx + " " + cy + " " + w + " " + h + " " + sm);
                    System.out.flush();
                } else if (System.currentTimeMillis() >= nextTick) {
                    // 生存確認: スレッド稼働/FPS/直近の顔数を出す(検出が出ない時の切り分け用)
                    double fps = (r != null) ? r.getFPS() : -1;
                    int fn = (r != null) ? r.getFaceNum() : -1;
                    System.out.println("TICK alive=" + cam.isAliveFaceDetectTask()
                            + " fps=" + ((int) fps) + " faceNum=" + fn);
                    System.out.flush();
                    nextTick = System.currentTimeMillis() + 3000L;
                }
                Thread.sleep(pollMs);
            }
            System.out.println("OK facetrack-done");
        } catch (Throwable t) {
            System.out.println("ERR " + t.getClass().getSimpleName() + ": " + t.getMessage());
            t.printStackTrace();
            System.exit(9);
        } finally {
            try { if (cam != null) { cam.StopFaceTraking(); cam.uninitFaceDetect(); cam.closeCapture(); } }
            catch (Throwable e) { /* ignore */ }
            try { if (motion != null) motion.ServoOff(); } catch (Throwable e) { /* ignore */ }
        }
    }
}
