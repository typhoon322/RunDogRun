"""
scripts/health_check.py — 每日系统健康巡检
==============================================
中午 12:00 检查 GitHub Actions 是否正常运行
"""
import json
import os
import sys
from datetime import datetime

# 确保脚本目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check() -> int:
    """返回 0=正常, 1=警告, 2=错误"""
    errors = []
    warnings = []
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"🔍 系统巡检 — {today}")
    print("─" * 40)

    # 1. Pipeline 日志
    pipeline_path = "data/outputs/pipeline_log.json"
    if not os.path.exists(pipeline_path):
        errors.append("❌ pipeline_log.json 不存在 — Actions 可能未执行")
    else:
        with open(pipeline_path) as f:
            plog = json.load(f)
        total = plog.get("total", 0)
        fails = plog.get("fail_count", 0)
        skips = plog.get("skip_count", 0)
        print(f"  Pipeline: {total}步, OK={plog.get('ok_count',0)}, Fail={fails}, Skip={skips}")
        if fails > 0:
            errors.append(f"❌ {fails} 个步骤失败")
        if total == 0:
            errors.append("❌ Pipeline 步骤数为0")

    # 2. 日报
    report_path = "data/outputs/daily_report.json"
    if not os.path.exists(report_path):
        errors.append("❌ daily_report.json 不存在")
    else:
        with open(report_path) as f:
            report = json.load(f)
        report_date = report.get("date", "")
        print(f"  日报: {report_date}")
        if report_date != today:
            warnings.append(f"⚠️ 日报日期({report_date})不是今天({today})")

    # 3. 数据缓存
    cache_dir = "data/raw/daily"
    if os.path.exists(cache_dir):
        csv_count = len([f for f in os.listdir(cache_dir) if f.endswith(".csv")])
        print(f"  缓存: {csv_count} 个 CSV")
        if csv_count == 0:
            warnings.append("⚠️ 数据缓存为空")
    else:
        warnings.append("⚠️ data/raw/daily 目录不存在")

    # 4. 快照
    snap_dir = "data/snapshots"
    if os.path.exists(snap_dir):
        snaps = [d for d in os.listdir(snap_dir) if os.path.isdir(f"{snap_dir}/{d}")]
        latest = snaps[-1] if snaps else "无"
        print(f"  快照: {len(snaps)} 个, 最新 {latest}")
    else:
        warnings.append("⚠️ 快照目录不存在")

    # ── 通知推送 ──
    title = "📊 系统巡检 " + today
    if errors:
        title = "❌ 系统异常 " + today
    elif warnings:
        title = "⚠️ 系统警告 " + today

    # 保存通知文件
    os.makedirs("data/outputs", exist_ok=True)
    msg = {"title": title, "errors": errors, "warnings": warnings, "time": datetime.now().isoformat()}
    with open("data/outputs/notification.json", "w", encoding="utf-8") as f:
        json.dump(msg, f, ensure_ascii=False, indent=2)

    print(f"\n📡 {title}")

    # ── 结论 ──
    print("─" * 40)
    if errors:
        print(f"\n❌ {len(errors)} 个错误:")
        for e in errors:
            print(f"  {e}")
        return 2
    elif warnings:
        print(f"\n⚠️ {len(warnings)} 个警告:")
        for w in warnings:
            print(f"  {w}")
        return 1
    else:
        print("\n✅ 系统运行正常")
        return 0


if __name__ == "__main__":
    sys.exit(check())
