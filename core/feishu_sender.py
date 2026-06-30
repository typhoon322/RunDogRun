"""
core/feishu_sender.py — V3 FINAL 飞书决策卡推送
===================================================
每天自动推送决策卡到飞书群。
Webhook 做了混淆处理: base64(反转(ID)), 不是明文。
"""
import base64
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CN_TZ = timezone(timedelta(hours=8))
logger = logging.getLogger("v3.feishu")

# ── Webhook 混淆解码 ──
# 原理: prefix + base64(reversed(hook_id))
# 破解需要: 知道 prefix + 知道是反转 + base64 解码
# GitHub 上即使看到这两个常量, 也不知道解码方式
_FS_PREFIX = "https://open.feishu.cn/open-apis/bot/v2/hook/"
_FS_ENCODED = "YmFjMTc2ZTdlOGUxLTZmZGItZmZmNC0wMDI4LTkyNTA5ZWIw"


def _decode_webhook() -> str:
    """解码 webhook URL — 不暴露明文"""
    decoded = base64.b64decode(_FS_ENCODED).decode()
    hook_id = decoded[::-1]  # 反转恢复
    return _FS_PREFIX + hook_id


# ── 安全关键词 (飞书机器人要求至少一个命中) ──
_KEYWORDS = ["DOG", "score", "市场", "决策"]


def _ensure_keyword(text: str) -> str:
    """确保消息包含安全关键词"""
    for kw in _KEYWORDS:
        if kw in text:
            return text
    # 兜底: 在末尾加关键词
    return text + "\n\n> 市场"


def send_decision_card(
    system_score: float,
    trend: float,
    flow: float,
    value: float,
    decision: dict,
    position: dict,
    market_state: str = "—",
    state: str = "ACTIVE",
    ic_5d: float | None = None,
) -> bool:
    """
    发送飞书决策卡 (V3 FINAL 格式)。

    Args:
        system_score, trend, flow, value: 因子值
        decision: decision_engine.decide() 的返回值
        position: calc_position_size() 的返回值
        market_state: 市场状态
        state: 生命周期状态 (COLLECT_ONLY/WARM_UP/ACTIVE/MONITORING)
        ic_5d: 5日 IC 值

    Returns:
        True 如果发送成功
    """
    url = _decode_webhook()

    # 决策文本
    action_map = {
        "EXIT": "🔴 清仓退出",
        "REDUCE": "🟠 减仓50%",
        "NO_TRADE": "🟡 观望不动",
        "BUY_SMALL": "🟢 小仓试单",
        "BUY_FULL": "🟢 满仓买入",
    }
    action_text = action_map.get(decision["action"], decision["action"])

    # Risk 级别
    risk_level = "NORMAL"
    if decision["action"] in ("EXIT", "REDUCE"):
        risk_level = "HIGH"
    elif position.get("compressed"):
        risk_level = "COMPRESSED"
    elif decision["action"] == "NO_TRADE":
        risk_level = "CAUTION"

    # Action 建议
    action_suggestions = {
        "EXIT": "建议清仓, 等待信号恢复",
        "REDUCE": "减仓50%, 控制风险",
        "NO_TRADE": "观望, 不操作",
        "BUY_SMALL": "可小仓试单",
        "BUY_FULL": "可满仓买入",
    }

    now = datetime.now(CN_TZ)
    date_str = now.strftime("%Y-%m-%d")

    # IC 显示
    ic_str = ""
    if ic_5d is not None:
        ic_quality = "🟢" if ic_5d > 0.03 else ("🟡" if ic_5d >= 0 else "🔴")
        ic_str = f"\nIC: {ic_5d:+.3f} {ic_quality}"

    # 状态映射
    state_emoji = {"COLLECT_ONLY": "❄️", "WARM_UP": "🔥", "ACTIVE": "🚀", "MONITORING": "🧠"}
    se = state_emoji.get(state, "❓")

    # 构建飞书卡片消息 (V3 FINAL 格式)
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "content": f"📊 RunDogRun {date_str}",
                    "tag": "plain_text",
                },
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": (
                            f"**STATE: {se} {state}**\n"
                            f"**System Score: {system_score:.0f}**\n"
                            f"Trend: {trend:.0f}  |  Flow: {flow:.0f}{ic_str}"
                        ),
                        "tag": "lark_md",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "content": (
                            f"**Decision: {action_text}**\n"
                            f"Position: {position.get('target_pct', 0):.0%}\n"
                            f"Risk: {risk_level}"
                        ),
                        "tag": "lark_md",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "content": f"**Action:** {action_suggestions.get(decision['action'], decision['reason'])}\n\n"
                                   f"⚠️ 自动生成 · 仅供参考 · {now.strftime('%H:%M')}",
                        "tag": "lark_md",
                    },
                },
            ],
        },
    }

    # 安全关键词检查
    body_str = json.dumps(card, ensure_ascii=False)
    body_str = _ensure_keyword(body_str)

    try:
        resp = requests.post(url, data=body_str.encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            if result.get("code") == 0:
                logger.info("飞书推送成功")
                return True
            else:
                logger.warning(f"飞书返回错误: {result}")
                return False
        else:
            logger.warning(f"飞书推送失败: HTTP {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"飞书推送异常: {e}")
        return False


def send_text_summary(text: str) -> bool:
    """发送纯文本消息 (备用)"""
    url = _decode_webhook()
    text = _ensure_keyword(text)
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False
