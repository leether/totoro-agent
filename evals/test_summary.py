"""
Eval 6: 汇总报告 — 一次跑完全部维度，整理对比表。
需要在其他 test 文件已经触发 API 调用后运行。
"""
import json, os, time, statistics
from conftest import run_benchmark, API_KEY

MODEL = "LongCat-2.0-Preview"
REPEAT = 10

BENCHMARKS = [
    # (name, messages, max_tokens)
    ("单轮短问",        [{"role": "user", "content": "你好"}], 128),
    ("单轮长问",        [{"role": "user", "content": "请用200字介绍人工智能"}], 512),
    ("多轮对话",        [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮你的？"},
        {"role": "user", "content": "写一个Python冒泡排序函数"},
    ], 512),
    ("纯输出长度测试",  [{"role": "user", "content": "列出1到100的数字，每个一行"}], 2048),
]

RESULTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval_results.json")


def _run_all():
    results = {}
    for name, msgs, max_t in BENCHMARKS:
        results[name] = {}
        for sdk in ("anthropic", "openai"):
            texts, lats, usages = [], [], []
            for _ in range(REPEAT):
                t, lat, uso = run_benchmark(sdk, msgs, max_tokens=max_t)
                texts.append(t)
                lats.append(lat)
                usages.append(uso)
            results[name][sdk] = {
                "text_sample": texts[0][:120],
                "latency_avg": round(statistics.mean(lats), 2),
                "latency_stdev": round(statistics.stdev(lats), 2) if len(lats) > 1 else 0,
                "output_tokens_avg": round(statistics.mean([u["output_tokens"] for u in usages])),
                "input_tokens_avg": round(statistics.mean([u["input_tokens"] for u in usages])),
                "text_len_avg": round(statistics.mean([len(t) for t in texts])),
            }
    return results


def test_generate_report():
    """产生汇总 JSON 并断言基本合理性。"""
    results = _run_all()

    # ---- 写入文件 ----
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已写入 {RESULTS_FILE}")

    # ---- 维度对比 ----
    header = f"{'场景':<14} {'SDK':<12} {'延迟avg':>8} {'延迟stdev':>10} {'input':>7} {'output':>7} {'字数':>6}"
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))

    for name, sdks in results.items():
        for sdk, m in sdks.items():
            print(f"{name:<14} {sdk:<12} {m['latency_avg']:>7.2f}s {m['latency_stdev']:>9.2f}s "
                  f"{m['input_tokens_avg']:>6} {m['output_tokens_avg']:>6} {m['text_len_avg']:>6}")

    print("=" * len(header))

    # ---- 基本断言 ----
    for name, sdks in results.items():
        for sdk, m in sdks.items():
            assert m["latency_avg"] < 30, f"{name}/{sdk}: 延迟过高"
            assert m["output_tokens_avg"] > 0, f"{name}/{sdk}: output_tokens 为 0"
            assert m["text_len_avg"] > 0, f"{name}/{sdk}: 输出空"
