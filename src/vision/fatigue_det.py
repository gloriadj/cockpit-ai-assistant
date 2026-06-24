# src/vision/fatigue_det.py
import time
import cv2
import numpy as np
import mediapipe as mp


class FatigueDetector:
    """
    基于 MediaPipe Face Mesh + EAR(眼睛纵横比) 的疲劳检测。
    原理：用面部关键点直接“测量”眼睛睁开程度（EAR），
    EAR 越小=眼睛越闭。当 EAR 持续低于阈值超过设定秒数，判定疲劳。
    比 Haar 的“检测到/检测不到眼睛”稳得多，且只有一个直观阈值可调。

    === 调灵敏度只看这两个常量 ===
      EAR_THRESHOLD        : 闭眼判定阈值。睁眼≈0.3，闭眼≈0.1。
                             调大(如0.25)=更灵敏(更容易判定闭眼)；
                             调小(如0.18)=更不灵敏。
      FATIGUE_CLOSE_SECONDS: 连续闭眼多少秒才报警(过滤正常眨眼)。
    """

    # ============ 灵敏度调节区 ============
    EAR_THRESHOLD = 0.15
    FATIGUE_CLOSE_SECONDS = 2.0
    # ====================================

    # MediaPipe Face Mesh 计算 EAR 用的 6 个关键点(顺序: 角,上,上,角,下,下)
    LEFT_EYE = [362, 385, 387, 263, 373, 380]
    RIGHT_EYE = [33, 160, 158, 133, 153, 144]

    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,        # 提升眼部精度
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.eyes_closed_since = None     # 开始闭眼的时间戳；None=当前睁眼
        self.last_ear = 0.0

    @staticmethod
    def _eye_aspect_ratio(pts, idxs):
        p1, p2, p3, p4, p5, p6 = (pts[i] for i in idxs)
        vertical = np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)
        horizontal = 2.0 * np.linalg.norm(p1 - p4)
        return float(vertical / horizontal) if horizontal > 0 else 0.0

    def detect_frame(self, frame):
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        fatigue_triggered = False
        alert_msg = "DRIVING SAFE"
        now = time.time()

        if results.multi_face_landmarks:
            lm = results.multi_face_landmarks[0].landmark
            pts = np.array([[p.x * w, p.y * h] for p in lm])

            ear_l = self._eye_aspect_ratio(pts, self.LEFT_EYE)
            ear_r = self._eye_aspect_ratio(pts, self.RIGHT_EYE)
            ear = (ear_l + ear_r) / 2.0
            self.last_ear = ear

            # 画出双眼的 12 个关键点(蓝色)和人脸框(绿色)
            for idx in self.LEFT_EYE + self.RIGHT_EYE:
                x, y = int(pts[idx][0]), int(pts[idx][1])
                cv2.circle(frame, (x, y), 2, (255, 0, 0), -1)
            x0, y0 = pts[:, 0].min(), pts[:, 1].min()
            x1, y1 = pts[:, 0].max(), pts[:, 1].max()
            cv2.rectangle(frame, (int(x0), int(y0)),
                          (int(x1), int(y1)), (0, 255, 0), 2)

            # ===== 时间驱动状态机 =====
            if ear < self.EAR_THRESHOLD:
                if self.eyes_closed_since is None:
                    self.eyes_closed_since = now
                closed_for = now - self.eyes_closed_since
                if closed_for >= self.FATIGUE_CLOSE_SECONDS:
                    fatigue_triggered = True
                    alert_msg = "WARNING: ALERT!"
            else:
                self.eyes_closed_since = None

            closed_disp = (round(now - self.eyes_closed_since, 1)
                           if self.eyes_closed_since else 0.0)
            color = (0, 0, 255) if fatigue_triggered else (0, 255, 0)
            cv2.putText(frame, f"EAR: {ear:.2f}", (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame, f"Eye-closed: {closed_disp}s", (30, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame, alert_msg, (30, 115),
                        cv2.FONT_HERSHEY_TRIPLEX, 0.8, color, 2)
        else:
            # 没检测到人脸
            self.eyes_closed_since = None
            alert_msg = "NO DRIVER"
            cv2.putText(frame, alert_msg, (30, 50),
                        cv2.FONT_HERSHEY_TRIPLEX, 0.8, (0, 255, 255), 2)

        return frame, fatigue_triggered, alert_msg


if __name__ == "__main__":
    detector = FatigueDetector()
    cap = cv2.VideoCapture(0)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        processed_frame, is_fatigue, msg = detector.detect_frame(frame)
        cv2.imshow("Test", processed_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()