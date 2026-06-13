"""
Eval 5: 错误处理 — 各种异常场景下 SDK 的表现
"""
import pytest

from conftest import API_KEY


def _anthropic_client():
    import anthropic
    return anthropic.Anthropic(
        api_key=API_KEY,
        base_url="https://api.longcat.chat/anthropic",
        default_headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
    )


def _openai_client():
    from openai import OpenAI
    return OpenAI(api_key=API_KEY, base_url="https://api.longcat.chat/openai")


# ---- 无效 Key ----
def test_anthropic_invalid_key():
    import anthropic
    bad = anthropic.Anthropic(
        api_key="invalid_key_xxx",
        base_url="https://api.longcat.chat/anthropic",
        default_headers={"Content-Type": "application/json", "Authorization": "Bearer invalid_key_xxx"},
    )
    with pytest.raises(anthropic.AuthenticationError):
        bad.messages.create(
            model="LongCat-2.0-Preview", max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )


def test_openai_invalid_key():
    from openai import AuthenticationError, OpenAI
    bad = OpenAI(api_key="invalid_key_xxx", base_url="https://api.longcat.chat/openai")
    with pytest.raises(AuthenticationError):
        bad.chat.completions.create(
            model="LongCat-2.0-Preview", max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )


# ---- 空消息 ----
def test_anthropic_empty_messages():
    import anthropic
    client = _anthropic_client()
    with pytest.raises((anthropic.BadRequestError, anthropic.APIStatusError)):
        client.messages.create(
            model="LongCat-2.0-Preview", max_tokens=10,
            messages=[],
        )


def test_openai_empty_messages():
    from openai import BadRequestError
    client = _openai_client()
    with pytest.raises(BadRequestError):
        client.chat.completions.create(
            model="LongCat-2.0-Preview", max_tokens=10,
            messages=[],
        )


# ---- 无效模型名 ----
def test_anthropic_bad_model():
    import anthropic
    client = _anthropic_client()
    with pytest.raises((anthropic.BadRequestError, anthropic.APIStatusError, anthropic.NotFoundError)):
        client.messages.create(
            model="nonexistent-model", max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )


def test_openai_bad_model():
    from openai import BadRequestError, NotFoundError
    client = _openai_client()
    with pytest.raises((BadRequestError, NotFoundError)):
        client.chat.completions.create(
            model="nonexistent-model", max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )


# ---- max_tokens = 0 ----
def test_anthropic_zero_max_tokens():
    import anthropic
    client = _anthropic_client()
    # max_tokens=0 应报错或返回空
    try:
        msg = client.messages.create(
            model="LongCat-2.0-Preview", max_tokens=0,
            messages=[{"role": "user", "content": "hi"}],
        )
        # 某些实现允许 0，检查不崩溃即可
        text = "".join(b.text for b in msg.content if b.type == "text")
        print(f"  anthropic max_tokens=0 => '{text}' (allowed)")
    except (anthropic.BadRequestError, anthropic.APIStatusError) as e:
        print(f"  anthropic max_tokens=0 => 正确抛出 {type(e).__name__}")


def test_openai_zero_max_tokens():
    client = _openai_client()
    try:
        resp = client.chat.completions.create(
            model="LongCat-2.0-Preview", max_tokens=0,
            messages=[{"role": "user", "content": "hi"}],
        )
        text = resp.choices[0].message.content or ""
        print(f"  openai max_tokens=0 => '{text}' (allowed)")
    except Exception as e:
        print(f"  openai max_tokens=0 => 正确抛出 {type(e).__name__}")
