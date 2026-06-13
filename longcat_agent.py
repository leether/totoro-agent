"""
LongCat Agent — 最小实现
使用 Anthropic Python SDK 调用 LongCat API
"""

import os
import anthropic

# === 配置 ===
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_file):
    for _line in open(_env_file):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

API_KEY = os.environ.get("LONGCAT_API_KEY", "")
BASE_URL = "https://api.longcat.chat/anthropic"
MODEL = "LongCat-2.0-Preview"

if not API_KEY:
    raise RuntimeError("LONGCAT_API_KEY 未设置，请在 .env 文件中配置")

# === 初始化客户端 ===
client = anthropic.Anthropic(
    api_key=API_KEY,
    base_url=BASE_URL,
    default_headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    },
)


def chat(user_text: str, system_prompt: str = "你是一个有用的中文助手。") -> str:
    """单轮对话：发送用户消息，返回模型回复文本。"""
    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    )
    # message.content 是 ContentBlock 列表，取 text 类型
    return "".join(block.text for block in message.content if block.type == "text")


def multi_turn(messages: list[dict], system_prompt: str = "你是一个有用的中文助手。") -> str:
    """多轮对话：传入完整消息历史，返回模型回复文本。"""
    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )
    return "".join(block.text for block in message.content if block.type == "text")


def stream_chat(user_text: str, system_prompt: str = "你是一个有用的中文助手。") -> None:
    """流式单轮对话：逐块打印模型输出。"""
    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
    print()  # 换行


# === CLI 入口 ===
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print('用法: python longcat_agent.py "你的消息" [--stream]')
        sys.exit(1)

    user_msg = sys.argv[1]
    use_stream = "--stream" in sys.argv

    if use_stream:
        stream_chat(user_msg)
    else:
        reply = chat(user_msg)
        print(reply)
