"""
api_client.py — 统一 HTTP 客户端
"""
import requests
import config
from src.utils.helpers import retry_request


def api_get(url: str, params: dict | None = None, label: str = "api") -> requests.Response | None:
    """统一 GET 请求 (含重试+超时)"""
    def _req():
        return requests.get(url, params=params,
                           headers={"User-Agent": "Mozilla/5.0"},
                           timeout=config.HTTP_TIMEOUT)
    resp = retry_request(_req, label=label)
    if resp:
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp


def api_post(url: str, json_data: dict | None = None, label: str = "api") -> requests.Response | None:
    """统一 POST 请求"""
    def _req():
        return requests.post(url, json=json_data or {},
                            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
                            timeout=config.HTTP_TIMEOUT)
    return retry_request(_req, label=label)
