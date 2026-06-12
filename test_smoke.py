"""冒烟测试：验证 longcat_agent 能正确初始化（不实际调用 API）。"""
import inspect
from longcat_agent import chat, multi_turn, stream_chat

# 1. 函数存在且签名正确
assert callable(chat)
assert callable(multi_turn)
assert callable(stream_chat)

sig = inspect.signature(chat)
assert "user_text" in sig.parameters
assert "system_prompt" in sig.parameters

sig2 = inspect.signature(multi_turn)
assert "messages" in sig2.parameters

# 2. 模块级常量
from longcat_agent import API_KEY, BASE_URL, MODEL
assert BASE_URL == "https://api.longcat.chat"
assert MODEL == "LongCat-2.0-Preview"

print("✅ 所有冒烟测试通过")
