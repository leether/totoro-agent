"""ProviderRegistry — LLM 后端注册表，支持运行时切换。"""
from __future__ import annotations

from providers.base import ChatProvider

_REGISTRY: dict[str, ChatProvider] = {}


class ProviderRegistry:
    """LLM 提供者注册表。使用类方法，全局单例。"""

    @classmethod
    def register(cls, name: str, provider: ChatProvider) -> None:
        _REGISTRY[name] = provider

    @classmethod
    def get(cls, name: str) -> ChatProvider:
        if name not in _REGISTRY:
            available = ", ".join(_REGISTRY.keys()) or "(empty)"
            raise KeyError(f"Provider '{name}' not registered. Available: {available}")
        return _REGISTRY[name]

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(_REGISTRY.keys())

    @classmethod
    def clear(cls) -> None:
        _REGISTRY.clear()


def register_provider(name: str):
    """装饰器：自动注册 provider 类实例。"""
    def decorator(provider_cls):
        instance = provider_cls()
        ProviderRegistry.register(name, instance)
        return provider_cls
    return decorator
