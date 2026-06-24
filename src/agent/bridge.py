# src/agent/bridge.py
import threading
import time
import os
import json
import yaml

import cv2

from src.vision.fatigue_det import FatigueDetector
from src.agent.lll_client import CockpitAgent
from src.tools.car_services import CarServices
from src.tools.voice_input import VoiceRecorder


class CockpitBridge:
    def __init__(self, config_path="config/config.yaml"):
        # 读取配置（ASR / 高德 key 等）
        cfg = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        asr_cfg = cfg.get("asr", {})
        self.asr_model_size = asr_cfg.get("model_size", "small")
        self.asr_compute_type = asr_cfg.get("compute_type", "int8")
        self.asr_language = asr_cfg.get("language", "zh")
        amap_key = cfg.get("map_api", {}).get("key", "")

        self.detector = FatigueDetector()
        self.agent = CockpitAgent()
        self.services = CarServices(amap_key=amap_key)
        self.recorder = VoiceRecorder()

        # faster-whisper 模型懒加载（第一次用到时才加载，避免拖慢启动）
        self._whisper_model = None

        self.fatigue_status = {
            "is_fatigue": False,
            "msg": "DRIVING SAFE",
            "current_frame": None,
        }

        self.is_running = False
        self.vision_thread = None
        self.cap = None

    # ==================== 视觉守护线程 ====================
    def start_vision_system(self):
        if not self.is_running:
            self.is_running = True
            self.cap = cv2.VideoCapture(0)
            self.vision_thread = threading.Thread(
                target=self._vision_loop, daemon=True)
            self.vision_thread.start()
            print("[系统调度] 🟢 后台视觉守护线程已启动 ...")

    def stop_vision_system(self):
        self.is_running = False
        if self.cap:
            self.cap.release()

    def _vision_loop(self):
        while self.is_running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.03)
                continue
            frame = cv2.flip(frame, 1)
            processed_frame, is_fatigue, msg = self.detector.detect_frame(frame)
            self.fatigue_status["is_fatigue"] = is_fatigue
            self.fatigue_status["msg"] = msg
            self.fatigue_status["current_frame"] = processed_frame
            time.sleep(0.04)

    # ==================== 本地语音识别（faster-whisper）====================
    def _get_whisper(self):
        """懒加载并缓存 faster-whisper 模型"""
        if self._whisper_model is None:
            from faster_whisper import WhisperModel
            print(f"[ASR] 正在加载 faster-whisper 模型："
                  f"{self.asr_model_size}（首次会自动下载，请稍候）...")
            # Mac 用 CPU + int8 即可，无需 GPU
            self._whisper_model = WhisperModel(
                self.asr_model_size,
                device="cpu",
                compute_type=self.asr_compute_type,
            )
            print("[ASR] ✅ 模型加载完成")
        return self._whisper_model

    def listen_and_recognize(self, duration=3):
        """录音 -> 本地 whisper 中文识别。完全离线、免 key。"""
        try:
            wav_path = self.recorder.record_audio(duration=duration)
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 100:
                return "ERROR_TIMEOUT"

            model = self._get_whisper()
            segments, info = model.transcribe(
                wav_path,
                language=self.asr_language,
                vad_filter=True,                 # 过滤静音，减少幻听
                beam_size=5,
                initial_prompt="导航 目的地 餐厅 我饿了 迪士尼 静安寺 人民广场 虹桥",
            )
            text = "".join(seg.text for seg in segments)
            # 去掉空格和常见中英文标点
            for ch in " ，。！？、,.!?…":
                text = text.replace(ch, "")
            text = text.strip()

            if text:
                print(f"[ASR whisper 识别] 🎙️: {text}")
                return text
            print("[ASR] 未识别到有效语音（可能没说话或太轻）")
            return "ERROR_TIMEOUT"
        except Exception as e:
            print(f"[ASR 全局异常]: {e}")
            return "ERROR_TIMEOUT"

    # ==================== 指令分发 ====================
    def handle_user_command(self, user_text):
        print(f"\n[Bridge 中枢] 💬 处理指令: '{user_text}'")

        is_food_query = any(
            w in user_text for w in ["饿", "餐厅", "吃", "美食", "饭店", "外卖"])

        destination = None
        if "导航去" in user_text or "导航到" in user_text:
            destination = (user_text.replace("导航去", "").replace("导航到", "")
                           .replace("“", "").replace("”", ""))
        elif "带我去" in user_text:
            destination = (user_text.replace("带我去", "")
                           .replace("“", "").replace("”", ""))
        elif "去" in user_text and len(user_text) > 1 and not is_food_query:
            destination = (user_text.replace("去", "")
                           .replace("“", "").replace("”", ""))

        # 1. 先让大模型解析意图（可覆盖上面的规则匹配结果）
        agent_res = self.agent.chat(user_text)
        if agent_res["type"] == "tool_call":
            if agent_res["function_name"] == "start_navigation":
                try:
                    args = json.loads(agent_res["arguments"])
                    destination = args.get("destination", destination)
                except Exception:
                    pass
            elif agent_res["function_name"] == "search_and_queue_restaurant":
                is_food_query = True

        # 2. 分支 A：美食 -> 取号 + 导航
        if is_food_query:
            rest = self.services.search_and_queue_restaurant(cuisine_type="美食")
            target = rest["restaurant"]
            nav = self.services.start_navigation(target)
            if nav["status"] == "success":
                reply = (f"为您找到【{target}】。{rest['queue_msg']}。"
                         f"已规划好路线，全程 {nav['distance']} 公里，"
                         f"预计 {nav['duration']} 分钟，导航已开启。")
            else:
                reply = (f"为您推荐【{target}】。{rest['queue_msg']}。"
                         f"不过暂时没能定位到它的具体位置。")
            self.services.tts_speak(reply)
            return {"reply": reply, "nav_data": nav}

        # 3. 分支 B：纯导航
        if destination:
            destination = destination.strip(",.。!！ ")
            nav = self.services.start_navigation(destination)
            if nav["status"] == "success":
                est = "（直线估算）" if nav.get("estimated") else ""
                reply = (f"收到，已规划前往【{destination}】的路线{est}。"
                         f"全程 {nav['distance']} 公里，预计 {nav['duration']} 分钟，"
                         f"请安全驾驶。")
                self.services.tts_speak(reply)
                return {"reply": reply, "nav_data": nav}
            else:
                reply = f"抱歉，没能在地图上找到【{destination}】，请换个说法或更具体的地名。"
                self.services.tts_speak(reply)
                return {"reply": reply, "nav_data": nav}

        # 4. 分支 C：普通闲聊
        if agent_res["type"] == "text" and agent_res.get("content"):
            reply = agent_res["content"]
        else:
            reply = f"听到您说：'{user_text}'。需要导航或找附近美食吗？"
        self.services.tts_speak(reply)
        return {"reply": reply}