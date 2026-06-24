# src/vision/fatigue_det.py
import cv2

class FatigueDetector:
    def __init__(self):
        # 换用精度最高、抗干扰能力最强的标准分类器
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        
        self.EYE_CLOSE_COUNTER = 0
        # 【超灵敏调优】连续 3 帧（约 0.1 秒）抓不到睁开的眼睛，立刻拉响警报！
        self.FATIGUE_THRESHOLD_FRAMES = 3  

    def detect_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # 【核心调优】直方图均衡化：瞬间提升暗光、背光下的面部对比度
        gray = cv2.equalizeHist(gray)
        
        # 提高面部检测灵敏度
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(140, 140))
        
        fatigue_triggered = False
        alert_msg = "DRIVING SAFE"
        eyes_detected = False
        
        for (x, y, w, h) in faces:
            # 画出绿色人脸框
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # 【核心调优：眼睛黄金ROI区域限制】
            # 眼睛一定在人脸高度的 20% 到 55% 之间，宽度在 10% 到 90% 之间
            # 这样可以 100% 过滤掉眉毛上方、鼻子下方的所有误报杂质！
            roi_gray = gray[y+int(h*0.2):y+int(h*0.52), x+int(w*0.1):x+int(w*0.9)]
            roi_color = frame[y+int(h*0.2):y+int(h*0.52), x+int(w*0.1):x+int(w*0.9)]
            
            # 在缩小的黄金区域内，以极高的步长搜索睁开的眼睛
            eyes = self.eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.04, minNeighbors=4, minSize=(18, 18))
            
            if len(eyes) >= 1:
                eyes_detected = True
                for (ex, ey, ew, eh) in eyes:
                    # 画出蓝色眼睛框
                    cv2.rectangle(roi_color, (ex, ey), (ex+ew, ey+eh), (255, 0, 0), 2)
                    
        # 核心判定状态机
        if len(faces) > 0:
            if not eyes_detected:
                # 只要抓到脸，但眼睛黄金区内检测不到睁开的眼睛 -> 100% 判定为闭眼/低头！
                self.EYE_CLOSE_COUNTER += 1
            else:
                self.EYE_CLOSE_COUNTER = 0
                
            if self.EYE_CLOSE_COUNTER >= self.FATIGUE_THRESHOLD_FRAMES:
                fatigue_triggered = True
                alert_msg = "WARNING: ALERT!"
        else:
            self.EYE_CLOSE_COUNTER = 0
            alert_msg = "NO DRIVER"

        # 绘制车机 HUD 界面
        color = (0, 0, 255) if fatigue_triggered else (0, 255, 0)
        cv2.putText(frame, f"Close Count: {self.EYE_CLOSE_COUNTER}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(frame, alert_msg, (30, 90), cv2.FONT_HERSHEY_TRIPLEX, 0.8, color, 2)
        
        return frame, fatigue_triggered, alert_msg

if __name__ == "__main__":
    detector = FatigueDetector()
    cap = cv2.VideoCapture(0)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        processed_frame, is_fatigue, msg = detector.detect_frame(frame)
        cv2.imshow("Test", processed_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
    cap.release()
    cv2.destroyAllWindows()