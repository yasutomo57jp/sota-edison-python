// SotaVoice - Sota 実機の音声機能(純正TTS / 発話再生 / 音声認識)を呼び出す最小CLIブリッジ。
//
// PC 側の sota_audio.py が自動デプロイ＆コンパイルして SSH 経由で実行する。
// カメラ用 SotaCam.java と同じ要領で、ベンダ資産 sotalib.jar に薄く乗せている。
//
// コンパイル:
//   javac -encoding UTF-8 -cp .:/home/vstone/lib/sotalib.jar:/home/vstone/lib/jna-4.1.0.jar SotaVoice.java
// 実行:
//   java -cp .:/home/vstone/lib/sotalib.jar:/home/vstone/lib/jna-4.1.0.jar \
//        -Djna.library.path=/home/vstone/lib SotaVoice <subcommand> ...
//
// サブコマンド:
//   tts  <rate> <pitch> <intonation> <out.wav> <text...>  純正TTSでWAV生成→out.wavへコピー。"OK <path>"
//   say  <rate> <pitch> <intonation> <text...>            TTS生成して即発話(口LED同期再生)。
//   play <wav>                                            指定WAVを口LED同期で再生(CPlayWave)。
//   asr  <timeout_ms> <retry>                             音声認識。認識文字列を1行で出力。
//   yesno <timeout_ms> <retry>                            Yes/No認識。"YES"/"NO"を出力。
//
// すべて成功時 stdout 1行目に "OK ..."、失敗時 "ERR ..." を出し、終了コードで判別できる。

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;

import jp.vstone.sotatalk.TextToSpeechSota;
import jp.vstone.RobotLib.CPlayWave;
import jp.vstone.RobotLib.CRobotMem;
import jp.vstone.RobotLib.CSotaMotion;
import jp.vstone.RobotLib.CRoboSetting;
import jp.vstone.RobotLib.CRobotPose;
import jp.vstone.RobotLib.IntelligentMicControl;
import jp.vstone.sotatalk.SpeechRecog;

public class SotaVoice {

    static String join(String[] a, int from) {
        StringBuilder sb = new StringBuilder();
        for (int i = from; i < a.length; i++) {
            if (i > from) sb.append(' ');
            sb.append(a[i]);
        }
        return sb.toString();
    }

    // 純正TTSでWAVファイルを得る。生成パス(キャッシュ内)を返す。
    static String makeTTS(int rate, int pitch, int intonation, String text) {
        String path = TextToSpeechSota.getTTSFile(text, rate, pitch, intonation);
        if (path == null || !new File(path).exists()) {
            throw new RuntimeException("TTS failed (null/path missing) for: " + text);
        }
        return path;
    }

    static int cmdTTS(String[] a) throws Exception {
        // tts <rate> <pitch> <intonation> <out.wav> <text...>
        int rate = Integer.parseInt(a[1]);
        int pitch = Integer.parseInt(a[2]);
        int intonation = Integer.parseInt(a[3]);
        String out = a[4];
        String text = join(a, 5);
        String src = makeTTS(rate, pitch, intonation, text);
        Files.copy(Paths.get(src), Paths.get(out), StandardCopyOption.REPLACE_EXISTING);
        System.out.println("OK " + out);
        return 0;
    }

    static int cmdSay(String[] a) throws Exception {
        // say <rate> <pitch> <intonation> <text...>
        int rate = Integer.parseInt(a[1]);
        int pitch = Integer.parseInt(a[2]);
        int intonation = Integer.parseInt(a[3]);
        String text = join(a, 4);
        String src = makeTTS(rate, pitch, intonation, text);
        CPlayWave.PlayWave(src, true);   // beWait=true: 再生完了まで待つ(口LED同期)
        System.out.println("OK said");
        return 0;
    }

    static int cmdPlay(String[] a) throws Exception {
        // play <wav>
        String wav = a[1];
        if (!new File(wav).exists()) { System.out.println("ERR no file " + wav); return 2; }
        CPlayWave.PlayWave(wav, true);
        System.out.println("OK played");
        return 0;
    }

    // ASR は SotaAppManager(localhost:6495) 経由。CRobotMem/Motion の接続が要る。
    static SpeechRecog newRecog() {
        CRobotMem mem = new CRobotMem();
        mem.Connect();
        CSotaMotion motion = new CSotaMotion(mem);
        return new SpeechRecog(motion);
    }

    static int cmdAsr(String[] a) throws Exception {
        // asr <timeout_ms> <retry>
        int timeout = Integer.parseInt(a[1]);
        int retry = Integer.parseInt(a[2]);
        String res = newRecog().getResponse(timeout, retry);
        if (res == null) { System.out.println("ERR norecog"); return 3; }
        System.out.println("OK " + res);
        return 0;
    }

    static int cmdYesNo(String[] a) throws Exception {
        // yesno <timeout_ms> <retry>
        int timeout = Integer.parseInt(a[1]);
        int retry = Integer.parseInt(a[2]);
        String res = newRecog().getYesorNo(timeout, retry);
        if (res == null) { System.out.println("ERR norecog"); return 3; }
        System.out.println("OK " + res);
        return 0;
    }

    // マイク音源定位。InitRobot_Sota() が intelligent mic の I2C デバイスを vsmd に登録し、
    // 以後 vsmd が VoiceDetection/DetectedDirection をレジスタへ反映する。
    // 検出を1行ずつ "DIR <deg> <raw>" で出力(PC側が読む)。プロセス常駐中のみ有効。
    // 既定の intelligent mic 入り設定。実機の active memdef.conf(.sota)はマイク未登録のため、
    // .sota_im 設定を明示ロードして InitRobot し、type=2 IntelligentMic(I2C 0x3A) を vsmd に登録する。
    static final String IM_CONF = "/home/vstone/vstonemagic/memdef/memdef.conf.sota_im";
    static final byte SV_HEAD_Y = 6;       // 頭ヨー(左右)。正=ロボットの左
    static final int HEAD_Y_LIMIT = 1450;  // ±145.0度(0.1度単位)

    // 検出方向(度, 正=左/負=右)へ頭ヨーを向ける。可動域でクランプ。
    static void turnHead(CSotaMotion motion, int deg) {
        int pos = deg * 10;
        if (pos > HEAD_Y_LIMIT) pos = HEAD_Y_LIMIT;
        if (pos < -HEAD_Y_LIMIT) pos = -HEAD_Y_LIMIT;
        CRobotPose pose = new CRobotPose();
        pose.SetPose(new Byte[]{ SV_HEAD_Y }, new Short[]{ (short) pos });
        motion.play(pose, 500);
    }

    static int cmdMic(String[] a) throws Exception {
        // mic <seconds> [pollMs] [turn:0/1] [confPath]
        int seconds = a.length > 1 ? Integer.parseInt(a[1]) : 20;
        int pollMs = a.length > 2 ? Integer.parseInt(a[2]) : 100;
        boolean turn = a.length > 3 && a[3].equals("1");
        String conf = a.length > 4 ? a[4] : IM_CONF;
        CRobotMem mem = new CRobotMem();
        mem.Connect();
        CSotaMotion motion = new CSotaMotion(mem);
        CRoboSetting setting = CRoboSetting.LoadSettingFile(conf);
        if (setting == null) {
            System.out.println("ERR cannot load setting: " + conf);
            return 4;
        }
        if (!motion.InitRobot(setting)) {  // servo初期化 + initI2C(LED2基 + IntelligentMic登録)
            System.out.println("ERR InitRobot failed");
            return 4;
        }
        IntelligentMicControl mic = new IntelligentMicControl(motion);
        mic.setMode(IntelligentMicControl.MIC_MODE_AUTO_DIRECTION);
        System.out.println("OK mic-ready " + seconds + "s");
        System.out.flush();
        long end = System.currentTimeMillis() + seconds * 1000L;
        int last = -999;
        while (System.currentTimeMillis() < end) {
            if (mic.isVoiseDetection()) {
                Integer deg = mic.getDetectedDirectionDeg();
                Integer raw = mic.getDetectedDirectionRaw();
                if (deg != null && raw != null && raw != last) {
                    System.out.println("DIR " + deg + " " + raw);
                    System.out.flush();
                    last = raw;
                    if (turn) turnHead(motion, deg);  // 検出方向へ頭を向ける
                }
            } else {
                last = -999;
            }
            Thread.sleep(pollMs);
        }
        mic.setMode(IntelligentMicControl.MIC_MODE_NO_USE);
        System.out.println("OK mic-done");
        return 0;
    }

    public static void main(String[] args) {
        try {
            if (args.length == 0) { System.out.println("ERR no subcommand"); System.exit(1); }
            String sub = args[0];
            int rc;
            if (sub.equals("tts"))        rc = cmdTTS(args);
            else if (sub.equals("say"))   rc = cmdSay(args);
            else if (sub.equals("play"))  rc = cmdPlay(args);
            else if (sub.equals("asr"))   rc = cmdAsr(args);
            else if (sub.equals("yesno")) rc = cmdYesNo(args);
            else if (sub.equals("mic"))   rc = cmdMic(args);
            else { System.out.println("ERR unknown subcommand " + sub); rc = 1; }
            System.exit(rc);
        } catch (Throwable t) {
            System.out.println("ERR " + t.getClass().getSimpleName() + ": " + t.getMessage());
            t.printStackTrace();
            System.exit(9);
        }
    }
}
