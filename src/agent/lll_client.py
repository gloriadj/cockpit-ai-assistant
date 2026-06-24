# src/agent/lll_client.py
import os
import yaml
from openai import OpenAI
from src.agent.prompt_tpl import SYSTEM_PROMPT, TOOLS

class CockpitAgent:
    def __init__(self, config_path="config/config.yaml"):
        # 1. 读取配置文件
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"找不到配置文件: {config_path}，请检查路径是否正确。")
            
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
            
        # 2. 初始化 OpenAI 客户端连接本地 Ollama
        self.client = OpenAI(
            base_url=self.config["ollama"]["base_url"],
            api_key="ollama"  # 本地 Ollama 不需要真实的 key，随便填一个即可
        )
        self.model = self.config["ollama"]["model_name"]
        
        # 3. 初始化对话上下文
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def chat(self, user_input: str):
        """与用户对话，并判断是否需要调用车载工具"""
        # 记录用户的输入
        self.messages.append({"role": "user", "content": user_input})
        
        try:
            # 向本地运行的 Qwen 模型发送请求
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.7
            )
            
            response_message = response.choices[0].message
            self.messages.append(response_message)
            
            # 判断大模型是否想要“调用工具”
            if response_message.tool_calls:
                print("\n[AI Agent 状态] 🤖 检测到需要触发车载工具...")
                for tool_call in response_message.tool_calls:
                    func_name = tool_call.function.name
                    func_args = tool_call.function.arguments
                    return {
                        "type": "tool_call",
                        "function_name": func_name,
                        "arguments": func_args,
                        "reply": "收到，正在为您处理。"
                    }
            
            # 如果不需要调用工具，只是普通聊天，返回文本
            return {
                "type": "text",
                "content": response_message.content
            }
            
        except Exception as e:
            return {"type": "error", "content": f"调用 Ollama 失败，请检查模型是否启动。错误信息: {str(e)}"}

# ----- 本地测试运行入口 -----
if __name__ == "__main__":
    agent = CockpitAgent()
    print("\n=== 🚗 座舱 AI Agent 启动成功 ===")
    
    # 模拟三种不同的用户话术
    test_inputs = [
        "你好，你是谁？",
        "我肚子好饿啊，帮我找家火锅店排个号吧",
        "带我去最近的万象城"
    ]
    
    for user_str in test_inputs:
        print(f"\n👉 用户说: '{user_str}'")
        res = agent.chat(user_str)
        print(f"🤖 Agent 返回数据: {res}")