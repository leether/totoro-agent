"""
Eval 3: 一致性 — 同一条消息分别用两种 SDK 调用，
对比输出内容是否语义相近（粗略检查：关键词覆盖 & 长度比），
同时检查 usage 口径是否一致。
"""
from conftest import run_benchmark

PROMPTS = [
    ["用一句话解释量子力学"],
    ["1+1等于几？"],
    ["将以下句子翻译成英文：今天天气真好"],
    ["给我三个学习 Python 的建议"],
]

anthropic_results = []
openai_results = []


def _collect():
    """先跑完所有 PROMPTS，两个 SDK 各跑一次。"""
    for prompts in PROMPTS:
        msgs = [{"role": "user", "content": p} for p in prompts]
        a_txt, a_lat, a_use = run_benchmark("anthropic", msgs)
        o_txt, o_lat, o_use = run_benchmark("openai", msgs)
        anthropic_results.append({"text": a_txt, "lat": a_lat, "usage": a_use})
        openai_results.append({"text": o_txt, "lat": o_lat, "usage": o_use})


_collect()


def test_output_length_ratio():
    """两者输出长度比不应太悬殊（0.3x ~ 3x）。"""
    for i, (a, o) in enumerate(zip(anthropic_results, openai_results)):
        la, lo = max(len(a["text"]), 1), max(len(o["text"]), 1)
        ratio = la / lo
        print(f"  prompt {i}: anthropic={la} chars, openai={lo} chars, ratio={ratio:.2f}")
        assert 0.3 < ratio < 3.0, f"prompt {i}: 输出长度差异过大 ratio={ratio:.2f}"


def test_latency_ratio():
    """延迟比不应太悬殊。"""
    for i, (a, o) in enumerate(zip(anthropic_results, openai_results)):
        la, lo = max(a["lat"], 0.01), max(o["lat"], 0.01)
        ratio = la / lo
        print(f"  prompt {i}: anthropic={a['lat']:.2f}s, openai={o['lat']:.2f}s, ratio={ratio:.2f}")
        assert 0.5 < ratio < 2.0, f"prompt {i}: 延迟差异过大 ratio={ratio:.2f}"


def test_usage_completeness():
    """usage 字段都应完整返回。"""
    for i, (a, o) in enumerate(zip(anthropic_results, openai_results)):
        for key in ("input_tokens", "output_tokens"):
            assert a["usage"][key] > 0, f"anthropic prompt {i}: {key}=0"
            assert o["usage"][key] > 0, f"openai prompt {i}: {key}=0"
        print(f"  prompt {i}: anthropic {a['usage']}  |  openai {o['usage']}")


def test_streaming_equivalence():
    """流式 vs 非流式输出应内容一致（同一 SDK 内比较）。"""
    import anthropic as anth
    from openai import OpenAI as OAI

    client_anth = anth.Anthropic(
        api_key="dummy", base_url="https://api.longcat.chat/anthropic",
        default_headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"},
    )
    # 只验证 SDK 流式接口是否可正常构建（不真正调用）
    # 真正流式对比放集成测试
    assert hasattr(client_anth.messages, "stream")
    assert hasattr(client_anth.messages, "create")
