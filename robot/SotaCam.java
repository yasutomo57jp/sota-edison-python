// SotaCam - Sota 頭部カメラから静止画(JPEG)を撮影してファイル保存する最小ツール。
// ロボット上(jdk1.8)でコンパイル/実行する。
//   javac -cp /home/vstone/lib/sotalib.jar:/home/vstone/lib/jna-4.1.0.jar SotaCam.java
//   java  -cp .:/home/vstone/lib/sotalib.jar:/home/vstone/lib/jna-4.1.0.jar \
//         -Djna.library.path=/home/vstone/lib SotaCam /dev/shm/sota_snap.jpg 1
//
// 引数: [出力パス] [サイズ番号]
//   サイズ番号: 0=QVGA 1=VGA(既定) 2=SVGA 3=XGA 4=HD720 5=SXGA 6=UXGA 7=HD1080 ...
import jp.vstone.camera.CameraCapture;

public class SotaCam {
    public static void main(String[] args) throws Exception {
        String out = (args.length > 0) ? args[0] : "/dev/shm/sota_snap.jpg";
        int size = (args.length > 1) ? Integer.parseInt(args[1])
                                     : CameraCapture.CAP_IMAGE_SIZE_VGA;

        // MJPG形式: snapGetFile が JPEG をそのままファイルに書き出す
        CameraCapture cap = new CameraCapture(size, CameraCapture.CAP_FORMAT_MJPG);
        cap.openDevice("/dev/video0");
        try {
            // 自動露出/AWBを安定させるため数フレーム捨ててから保存
            for (int i = 0; i < 6; i++) {
                cap.snapGetFile(out);
                Thread.sleep(120);
            }
        } finally {
            cap.close();
        }
        System.out.println("OK " + out);
    }
}
