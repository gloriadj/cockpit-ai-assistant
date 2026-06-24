# app.py
import streamlit as st
import folium
from streamlit_folium import st_folium
import time
import cv2
import subprocess
from src.agent.bridge import CockpitBridge

# 1. 基础配置
st.set_page_config(page_title="Next-Gen AI 智能座舱系统", layout="wide", page_icon="🚗")

# 2. 全局 session 状态初始化
if "bridge" not in st.session_state:
    st.session_state.bridge = CockpitBridge()
    st.session_state.bridge.start_vision_system()
    st.session_state.chat_history = []
    st.session_state.map_center = [31.2304, 121.4737]  # 起点：上海人民广场
    st.session_state.route_points = []                 # 核心红线点集
    st.session_state.last_music_time = 0
    st.session_state.recording_active = False
    st.session_state.is_processing = False             # 算路专用保护锁

bridge = st.session_state.bridge
v_status = bridge.fatigue_status

# ==================== 🛡️ 氛围灯与主动安全干预 ====================
if v_status["is_fatigue"]:
    st.markdown("<style>.stApp { background-color: #4a0000 !important; transition: background-color 0.2s; }</style>", unsafe_allow_html=True)
    current_time = time.time()
    if current_time - st.session_state.last_music_time > 3:
        st.session_state.last_music_time = current_time
        subprocess.Popen(["say", "-v", "Tingting", "警告！检测到疲劳驾驶，请立即清醒！"])
else:
    st.markdown("<style>.stApp { background-color: #0e1117 !important; transition: background-color 0.4s; }</style>", unsafe_allow_html=True)

st.title("🚗 Next-Gen 多模态 AI 智能座舱交互系统")
st.markdown("---")

left_col, right_col = st.columns([1, 1.2])

# ==================== 左侧面板：安全感知区 ====================
with left_col:
    st.header("🛡️ 安全感知中心")
    if v_status["is_fatigue"]:
        st.error(f"🚨 状态：检测到重度疲劳！")
    else:
        st.success(f"🟢 状态：安全驾驶中")
        
    if v_status["current_frame"] is not None:
        rgb_show = cv2.cvtColor(v_status["current_frame"], cv2.COLOR_BGR2RGB)
        st.image(rgb_show, channels="RGB", use_container_width=True)

# ==================== 右侧面板：地图与任意动态导航 ====================
with right_col:
    st.header("🤖 交互式车机中心")
    
    # Folium 地图渲染核心
    m = folium.Map(location=st.session_state.map_center, zoom_start=12)
    if st.session_state.route_points:
        folium.PolyLine(st.session_state.route_points, color="#FF0000", weight=8, opacity=0.9).add_to(m)
        folium.Marker(st.session_state.map_center, popup="目的地", icon=folium.Icon(color="red")).add_to(m)
    
    # ✨【抗高频重绘干预】：动态控制地图 key，防止路线渲染被秒刷
    map_key = f"map_{st.session_state.map_center[0]}_{len(st.session_state.route_points)}"
    st_folium(m, height=320, width=650, key=map_key)
    
    st.markdown("---")
    st.subheader("🎙️ 车载交互控制")
    
    final_user_cmd = None
    btn_col, text_col = st.columns([1, 1.8])
    
    with btn_col:
        st.write("") 
        if st.button("🎤 激活车载麦克风 (说3秒)", type="primary", use_container_width=True):
            st.session_state.recording_active = True
            with st.spinner("🔊 录音中，请对 Mac 说出目的地..."):
                recognized_text = bridge.listen_and_recognize(duration=3)
            
            # ✨【修复核心】：解除“新天地”的强力绑架，真正获取语音识别出的内容
            if recognized_text and recognized_text != "ERROR_TIMEOUT":
                final_user_cmd = recognized_text
            else:
                # 默默在后台报备，界面不做大红大黄的警告，保持座舱优雅
                print("[系统车机通知]：本次语音识别未触发，建议改用文本键入。")
                # 播报一段轻柔的硬件女声提示，让测试更拟真
                subprocess.Popen(["say", "-v", "Tingting", "没听清，请尝试再次说话或打字"])
                
            st.session_state.recording_active = False

    with text_col:
        with st.form(key="navigation_form", clear_on_submit=True):
            input_text = st.text_input("💬 输入指令（如：‘我饿了’、‘导航去迪士尼’、‘我要去静安寺’）", value="")
            submit_button = st.form_submit_button(label="发送指令", use_container_width=True)
            if submit_button and input_text:
                final_user_cmd = input_text

    # 统一算路分发
    if final_user_cmd:
        st.session_state.is_processing = True  # 锁定刷新
        st.session_state.chat_history.append({"role": "user", "content": final_user_cmd})
        
        with st.spinner("车机正在为您动态调用高德全路网规划..."):
            res = bridge.handle_user_command(final_user_cmd)
            
        reply_text = res.get("reply", "服务暂时没有响应。")
        st.session_state.chat_history.append({"role": "assistant", "content": reply_text})
        
        if "nav_data" in res and res["nav_data"]["status"] == "success":
            points_str = res["nav_data"]["points"]
            parsed_points = []
            for step_poly in points_str:
                for coor_pair in step_poly.split(";"):
                    if coor_pair and "," in coor_pair:
                        lng, lat = coor_pair.split(",")
                        parsed_points.append([float(lat), float(lng)])
            if parsed_points:
                st.session_state.route_points = parsed_points
                st.session_state.map_center = parsed_points[-1]  # 聚焦终点
                
        st.session_state.is_processing = False  # 释放锁
        st.rerun()

    st.markdown("---")
    for msg in st.session_state.chat_history[-2:]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# 🚀 只有在非工作状态下才允许自刷新摄像头画面
if not st.session_state.recording_active and not st.session_state.is_processing:
    time.sleep(0.04)
    st.rerun()