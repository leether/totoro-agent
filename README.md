# LongCat Agent — 最小实现

使用 Anthropic Python SDK 调用 LongCat API 的最小 Agent。

## 快速开始

### 1. 安装依赖

```bash
pip install anthropic
```

### 2. 配置 API Key

编辑 `longcat_agent.py`，将 `YOUR_API_KEY` 替换为你的 LongCat API Key：

```python
API_KEY = "你的API Key"
```

或通过环境变量注入（推荐）：

```bash
export LONGCAT_API_KEY="你的API Key"
```

### 3. 运行

```bash
# 单轮对话
python longcat_agent.py "你好，请介绍一下你自己"

# 流式输出
python longcat_agent.py "写一首关于春天的诗" --stream
```

## 三种使用方式

| 函数 | 说明 |
|------|------|
| `chat(user_text)` | 单轮对话，返回文本 |
| `multi_turn(messages)` | 多轮对话，传入消息历史 |
| `stream_chat(user_text)` | 流式单轮对话，逐块打印 |

## 作为库使用

```python
from longcat_agent import chat, multi_turn, stream_chat

# 单轮
reply = chat("你好")
print(reply)

# 多轮
messages = [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮你的？"},
    {"role": "user", "content": "帮我写代码"},
]
reply = multi_turn(messages)
print(reply)

# 流式
stream_chat("写一首诗")
```

## API 参考

- 端点：`https://api.longcat.chat`
- Anthropic 接口：`POST /anthropic/v1/messages`
- 认证：`Authorization: Bearer YOUR_API_KEY`
- 模型：`LongCat-2.0-Preview`
