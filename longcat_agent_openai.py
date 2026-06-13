"""
LongCat Agent — OpenAI Python SDK 版
使用 OpenAI Python SDK 调用 LongCat API（OpenAI 兼容格式）
"""

import os
from openai import OpenAI

# === 配置 ===
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_file):
    for _line in open(_env_file):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

API_KEY = os.environ.get("LONGCAT_API_KEY", "")
BASE_URL = "https://api.longcat.chat/openai"  # OpenAI 兼容端点
MODEL = "LongCat-2.0-Preview"

if not API_KEY:
    raise RuntimeError("LONGCAT_API_KEY 未设置，请在 .env 文件中配置")

# === 初始化客户端 ===
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)


def chat(user_text: str, system_prompt: str = "你是一个有用的中文助手。") -> str:
    """单轮对话：发送用户消息，返回模型回复文本。"""
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )
    return resp.choices[0].message.content or ""


def multi_turn(messages: list[dict], system_prompt: str = "你是一个有用的中文助手。") -> str:
    """多轮对话：传入完整消息历史，返回模型回复文本。"""
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "system", "content": system_prompt}] + messages,
    )
    return resp.choices[0].message.content or ""


def stream_chat(user_text: str, system_prompt: str = "你是一个有用的中文助手。") -> None:
    """流式单轮对话：逐块打印模型输出。"""
    stream = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
    print()  # 换行


# === CLI 入口 ===
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print('用法: python longcat_agent_openai.py "你的消息" [--stream]')
        sys.exit(1)

    user_msg = sys.argv[1]
    use_stream = "--stream" in sys.argv

    if use_stream:
        stream_chat(user_msg)
    else:
        reply = chat(user_msg)
        print(reply)
