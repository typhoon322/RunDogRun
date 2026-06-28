"""
scripts/notify.py — 系统通知推送
===================================
支持: PushPlus / Server酱 / 企业微信 Webhook
配置: 设置环境变量 NOTIFY_TOKEN + NOTIFY_TYPE

PushPlus (推荐免费): https://www.pushplus.plus
  · 注册 → 获取 token
  · 设置 NOTIFY_TOKEN=你的token
  · 设置 NOTIFY_TYPE=pushplus
"""
import json
import os
import urllib.request
from datetime import datetime


def send_wechat(title: str, content: str) -> bool:
    """推送到微信"""
    token = os.environ.get("NOTIFY_TOKEN", "")
    ntype = os.environ.get("NOTIFY_TYPE", "")

    if not token:
        print("  ⚠️ 未配置 NOTIFY_TOKEN, 跳过推送")
        print("  注册: https://www.pushplus.plus → 获取token → 设置到 GitHub Secrets")
        _save_notification(title, content)
        return False

    if ntype == "pushplus" or not ntype:
        return _pushplus(token, title, content)
    elif ntype == "serverchan":
        return _serverchan(token, title, content)
    else:
        print(f"  未知通知类型: {ntype}")
        return False


def _pushplus(token: str, title: str, content: str) -> bool:
    """PushPlus 推送"""
    url = "http://www.pushplus.plus/send"
    data = json.dumps({
        "token": token,
        "title": title,
        "content": content,
        "template": "markdown",
    }).encode()
    req = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get("code") == 200:
            print("  ✅ 微信推送成功")
            return True
        else:
            print(f"  ❌ 推送失败: {result.get('msg', '')}")
            return False
    except Exception as e:
        print(f"  ❌ 推送异常: {e}")
        return False


def _serverchan(token: str, title: str, content: str) -> bool:
    """Server酱 推送"""
    url = f"https://sctapi.ftqq.com/{token}.send"
    import urllib.parse
    payload = urllib.parse.urlencode({"title": title, "desp": content}).encode()
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, data=payload), timeout=10)
        return resp.status == 200
    except Exception as e:
        print(f"  ❌ 推送异常: {e}")
        return False


def _save_notification(title: str, content: str) -> None:
    """保存到本地供外部读取"""
    os.makedirs("data/outputs", exist_ok=True)
    with open("data/outputs/notification.json", "w", encoding="utf-8") as f:
        json.dump({
            "title": title,
            "content": content,
            "time": datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)


def build_report(errors: list[str], warnings: list[str]) -> tuple[str, str]:
    """构建推送文案"""
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"📊 系统巡检 {today}"

    if errors:
        title = f"❌ 系统异常 {today}"
        body = "## 错误\n\n"
        for e in errors:
            body += f"- {e}\n"
        if warnings:
            body += "\n## 警告\n\n"
            for w in warnings:
                body += f"- {w}\n"
    elif warnings:
        title = f"⚠️ 系统警告 {today}"
        body = "\n".join(f"- {w}" for w in warnings)
    else:
        body = "✅ 所有检查项正常\n\n- Pipeline 正常\n- 日报已生成\n- 数据缓存正常"

    body += f"\n\n---\n[查看仪表盘](https://typhoon322-rundogrun.streamlit.app)"
    return title, body
