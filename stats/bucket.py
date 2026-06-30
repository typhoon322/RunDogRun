"""
stats/bucket.py — V3 FINAL 分桶模块 (re-export from analytics)
================================================================
统一入口: stats.bucket → analytics.bucket
"""
from analytics.bucket import (
    BUCKETS,
    analyze,
    bucket_report,
)

__all__ = ["BUCKETS", "analyze", "bucket_report"]
