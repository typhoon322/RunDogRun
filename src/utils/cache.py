"""
cache.py — 日内缓存, 避免重复请求同一数据
"""

_cache: dict[str, dict] = {}


def day_cache() -> dict:
    """返回当日缓存字典 (key → value)"""
    return _cache


def get_cache(key: str) -> dict | None:
    return _cache.get(key)


def set_cache(key: str, value: dict) -> None:
    _cache[key] = value
