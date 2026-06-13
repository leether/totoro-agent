"""
共享 fixtures：为 Anthropic / OpenAI 两种客户端提供统一的评测接口。
"""
import os
import time

# 从 .env 读取
_env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_file):
    for _line in open(_env_file):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

API_KEY  = os.environ["TOTORO_API_KEY"]
MODEL    = "LongCat-2.0-Preview"


def _anthropic_call(messages, max_tokens=512):
    import anthropic
    client = anthropic.Anthropic(
        api_key=API_KEY,
        base_url="https://api.longcat.chat/anthropic",
        default_headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
    )
    t0 = time.perf_counter()
    msg = client.messages.create(model=MODEL, max_tokens=max_tokens, messages=messages)
    latency = time.perf_counter() - t0
    text = "".join(b.text for b in msg.content if b.type == "text")
    usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
    return text, latency, usage


def _openai_call(messages, max_tokens=512):
    from openai import OpenAI
    client = OpenAI(api_key=API_KEY, base_url="https://api.longcat.chat/openai")
    t0 = time.perf_counter()
    resp = client.chat.completions.create(model=MODEL, max_tokens=max_tokens, messages=messages)
    latency = time.perf_counter() - t0
    text = resp.choices[0].message.content or ""
    usage = {"input_tokens": resp.usage.prompt_tokens, "output_tokens": resp.usage.completion_tokens}
    return text, latency, usage


# ===== 统一评测接口 =====
def run_benchmark(sdk: str, messages: list[dict], max_tokens: int = 512):
    """sdk = 'anthropic' | 'openai'，返回 (text, latency_sec, usage)"""
    if sdk == "anthropic":
        return _anthropic_call(messages, max_tokens)
    elif sdk == "openai":
        return _openai_call(messages, max_tokens)
    else:
        raise ValueError(f"unknown sdk: {sdk}")
