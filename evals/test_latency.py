"""
Eval 2: 延迟对比 — 多轮对话 & 长输出的延迟表现
各跑 3 次取平均，不做严格断言，输出对比表。
"""
import pytest

from conftest import run_benchmark

MULTI_TURN = [
    {"role": "user",      "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮你的？"},
    {"role": "user",      "content": "帮我写一首五言绝句，关于春天"},
]

LONG_OUTPUT = [
    {"role": "user", "content": "列出 20 个 Python 常用标准库模块，每个一行"},
]

REPEAT = 3  # 每个场景跑几次


def _avg_latency(sdk, messages, repeat=REPEAT, max_tokens=1024):
    latencies = []
    for _ in range(repeat):
        _, lat, usage = run_benchmark(sdk, messages, max_tokens=max_tokens)
        latencies.append(lat)
    return sum(latencies) / len(latencies), usage


@pytest.mark.parametrize("sdk", ["anthropic", "openai"])
def test_multi_turn_latency(sdk):
    avg, usage = _avg_latency(sdk, MULTI_TURN, max_tokens=512)
    print(f"\n[{sdk}] multi-turn avg={avg:.2f}s  tokens={usage}")
    assert avg < 15  # 多轮也不应太慢


@pytest.mark.parametrize("sdk", ["anthropic", "openai"])
def test_long_output_latency(sdk):
    avg, usage = _avg_latency(sdk, LONG_OUTPUT, max_tokens=1024)
    print(f"\n[{sdk}] long-output avg={avg:.2f}s  tokens={usage}")
    assert avg < 20
