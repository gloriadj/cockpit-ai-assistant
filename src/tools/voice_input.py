# src/tools/voice_input.py
import sounddevice as sd
import numpy as np
from scipy.io import wavfile
import os

class VoiceRecorder:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        os.makedirs("src/tools", exist_ok=True)
        self.output_path = "src/tools/user_input.wav"

    def record_audio(self, duration=4):
        """录制指定秒数的音频并保存"""
        print(f"\n[🎙️ 车载麦克风] 正在录音中（请说话，限时 {duration} 秒）...")
        
        # 【已修复】将 sampler_rate 改为 samplerate
        recording = sd.rec(
            int(duration * self.sample_rate), 
            samplerate=self.sample_rate, 
            channels=1, 
            dtype='int16'
        )
        sd.wait()  # 等待录音结束
        
        print("[🎙️ 车载麦克风] 录音结束，正在保存音频文件...")
        # 保存为本地 wav 文件
        wavfile.write(self.output_path, self.sample_rate, recording)
        print(f"[🎙️ 车载麦克风] 音频已成功保存至: {self.output_path}")
        return self.output_path

if __name__ == "__main__":
    # 本地测试录音
    recorder = VoiceRecorder()
    recorder.record_audio(duration=3)  # 测试录音3秒