"""
Eval 4: 流式输出 — 两种 SDK 流式模式是否正常
收集所有流式 chunk，最终拼接文本与非流式一致。
"""
import pytest

from conftest import API_KEY, MODEL

MESSAGES = [{"role": "user", "content": "请用一句话介绍你自己"}]


def _anthropic_stream():
    import anthropic
    client = anthropic.Anthropic(
        api_key=API_KEY,
        base_url="https://api.longcat.chat/anthropic",
        default_headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
    )
    chunks = []
    with client.messages.stream(model=MODEL, max_tokens=256, messages=MESSAGES) as stream:
        for text in stream.text_stream:
            chunks.append(text)
    return "".join(chunks)


def _openai_stream():
    from openai import OpenAI
    client = OpenAI(api_key=API_KEY, base_url="https://api.longcat.chat/openai")
    chunks = []
    stream = client.chat.completions.create(
        model=MODEL, max_tokens=256, stream=True, messages=MESSAGES,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            chunks.append(delta)
    return "".join(chunks)


@pytest.mark.parametrize("stream_fn", [_anthropic_stream, _openai_stream])
def test_stream_returns_text(stream_fn):
    text = stream_fn()
    assert len(text) > 0, "流式返回空文本"
    print(f"\n[{stream_fn.__name__}] stream result: {text[:80]}...")


def test_stream_nonstream_consistency():
    """两种 SDK 的流式和非流式结果应大致相近（字数比 0.5x~2x）。"""
    a_text, _, _ = run_benchmark_safe("anthropic")
    a_stream = _anthropic_stream()
    o_text, _, _ = run_benchmark_safe("openai")
    o_stream = _openai_stream()

    def ratio(a, b):
        return max(len(a), 1) / max(len(b), 1)

    print(f"\nanthropic: non-stream={len(a_text)} chars, stream={len(a_stream)} chars, ratio={ratio(a_text, a_stream):.2f}")
    print(f"openai:    non-stream={len(o_text)} chars, stream={len(o_stream)} chars, ratio={ratio(o_text, o_stream):.2f}")

    assert 0.5 < ratio(a_text, a_stream) < 2.0
    assert 0.5 < ratio(o_text, o_stream) < 2.0


def run_benchmark_safe(sdk, messages=None, max_tokens=256):
    from conftest import run_benchmark
    if messages is None:
        messages = MESSAGES
    return run_benchmark(sdk, messages, max_tokens)
