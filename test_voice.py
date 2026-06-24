# test_voice.py
import os
import time
import subprocess
from src.tools.voice_input import VoiceRecorder

def test_microphone():
    print("====== 🎙️ 智能座舱麦克风收音底层硬件自检 ======")
    recorder = VoiceRecorder()
    
    duration = 3
    print(f"\n[1/3] 准备开始录音，时长 {duration} 秒...")
    print(">>> 🔴 请对着 Mac 麦克风大声说：'导航去迪士尼' 🔴")
    
    start_time = time.time()
    wav_path = recorder.record_audio(duration=duration)
    end_time = time.time()
    
    print(f"[2/3] 录音动作结束。耗时: {round(end_time - start_time, 2)} 秒")
    print(f"音频实际生成路径: {wav_path}")
    
    if not os.path.exists(wav_path):
        print("❌ 严重错误：物理文件根本没有被创建！麦克风底层命令可能崩溃了。")
        return
        
    file_size = os.path.getsize(wav_path)
    print(f"生成音频文件大小: {file_size} 字节 (Bytes)")
    
    if file_size < 1000:
        print("❌ 严重错误：生成的文件几乎没有任何数据（空音频）。Mac 没有捕获到输入波形！")
        return
        
    print("\n[3/3] 🔊 正在调用底层硬件尝试回放您刚才的录音...")
    try:
        subprocess.run(["afplay", wav_path], check=True)
        print("🟢 自检圆满成功！如果您听到了自己的声音，说明硬件收音 100% 正常！")
    except Exception as e:
        print(f"⚠️ 回放失败，但文件已生成。错误信息: {e}")

if __name__ == "__main__":
    test_microphone()
