"""
Eval 1: 基础能力 — 两种 SDK 都能正常返回文本
"""

import pytest

from conftest import run_benchmark

MESSAGES = [{"role": "user", "content": "请用一句话介绍你自己"}]


@pytest.mark.parametrize("sdk", ["anthropic", "openai"])
def test_basic_responds(sdk):
    text, latency, usage = run_benchmark(sdk, MESSAGES)
    assert len(text) > 0, f"{sdk}: 返回空文本"
    assert latency < 30, f"{sdk}: 延迟过高 {latency:.1f}s"
    assert usage["output_tokens"] > 0, f"{sdk}: output_tokens 为 0"
    print(f"\n[{sdk}] latency={latency:.2f}s  tokens={usage}  reply={text[:60]}...")
