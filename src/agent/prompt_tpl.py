# src/agent/prompt_tpl.py

# 1. 设定 AI 的角色（System Prompt）
SYSTEM_PROMPT = """你是一款高端智能汽车的专属座舱 AI 助手。
你的目标是贴心、高效地为驾驶员和乘客提供服务。你说话风格应该科技、温暖且简练，字数不宜过多。
你可以通过调用工具来帮用户解决实际问题（如寻找餐厅、导航等）。"""

# 2. 告诉大模型它能调用的函数结构 (Tools Schema)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_and_queue_restaurant",
            "description": "根据用户的喜好或需求，搜索附近的餐厅，并自动进行取号排队。",
            "parameters": {
                "type": "object",
                "properties": {
                    "cuisine_type": {
                        "type": "string",
                        "description": "菜系或餐厅类型，例如：火锅、川菜、麦当劳、西餐。如果用户没提，可以不传。"
                    },
                    "preference": {
                        "type": "string",
                        "description": "用户的其他偏好，例如：人少、靠窗、评分高。"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_navigation",
            "description": "规划路线并开启导航到指定目的地。",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "导航的目的地名称，例如：万象城、某某餐厅。"
                    }
                },
                "required": ["destination"]
            }
        }
    }
]