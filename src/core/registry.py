"""
registry.py — 模块注册中心
===========================
统一管理 v1-v8 所有模块的入口, 支持按名称查找和延迟加载。
"""
from typing import Any, Callable

_registry: dict[str, Callable] = {}


def register(name: str):
    """装饰器: 将函数注册到中心"""
    def decorator(func):
        _registry[name] = func
        return func
    return decorator


def get_module(name: str) -> Callable | None:
    return _registry.get(name)


def list_modules() -> list[str]:
    return sorted(_registry.keys())


def run_all(data: dict, ctx: Any = None) -> dict[str, Any]:
    """按顺序执行所有注册模块"""
    order = [
        "v1_collect", "v2_sector", "v1_stock", "v3_leader",
        "v4_risk", "v5_regime", "v6_resonance",
    ]
    results = {}
    for name in order:
        if name in _registry:
            results[name] = _registry[name](data, ctx)
    return results
