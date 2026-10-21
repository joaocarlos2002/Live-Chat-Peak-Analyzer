from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def _timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None


def read_messages(path: Path) -> list[dict[str, Any]]:
    messages = []
    if not path.exists():
        return messages
    with path.open(encoding="utf-8") as source:
        for line in source:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            timestamp = _timestamp(item.get("timestamp", item.get("ts")))
            if timestamp is not None:
                item["_timestamp"] = timestamp
                messages.append(item)
    return sorted(messages, key=lambda item: item["_timestamp"])


def analyze(messages: list[dict[str, Any]], window: int = 10) -> dict[str, Any]:
    if window <= 0:
        raise ValueError("A janela deve ser maior que zero.")
    if not messages:
        return {
            "window_seconds": window,
            "total_messages": 0,
            "unique_users": 0,
            "average": 0,
            "median": 0,
            "stddev": 0,
            "p90": 0,
            "duration_seconds": 0,
            "total_windows": 0,
            "active_windows": 0,
            "coverage_percent": 0,
            "above_average_windows": 0,
            "max_rate_per_second": 0,
            "peak_share_percent": 0,
            "user_message_ratio": 0,
            "max_count": 0,
            "timeline": [],
            "peaks": [],
        }

    start = messages[0]["_timestamp"]
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for message in messages:
        bucket = math.floor((message["_timestamp"] - start) / window)
        buckets[bucket].append(message)

    last_bucket = max(buckets)
    counts = [len(buckets.get(index, [])) for index in range(last_bucket + 1)]
    timeline = []
    for index in range(last_bucket + 1):
        items = buckets.get(index, [])
        if not items:
            timeline.append({
                "offset_seconds": index * window,
                "start_timestamp": None,
                "end_timestamp": None,
                "count": 0,
                "rate_per_second": 0,
                "unique_users": 0,
            })
            continue
        relative_start = index * window
        timeline.append({
            "offset_seconds": relative_start,
            "start_timestamp": items[0].get("timestamp"),
            "end_timestamp": items[-1].get("timestamp"),
            "count": len(items),
            "rate_per_second": round(len(items) / window, 3),
            "unique_users": len({str(item.get("user_id") or item.get("username")) for item in items if item.get("user_id") or item.get("username")}),
        })

    average = statistics.mean(counts)
    median = statistics.median(counts)
    stddev = statistics.pstdev(counts)
    sorted_counts = sorted(counts)
    p90 = sorted_counts[min(len(sorted_counts) - 1, math.ceil(len(sorted_counts) * 0.9) - 1)]
    duration_seconds = (messages[-1]["_timestamp"] - start) + window
    all_users = {str(item.get("user_id") or item.get("username")) for item in messages if item.get("user_id") or item.get("username")}
    ranked = sorted(timeline, key=lambda item: item["count"], reverse=True)
    peaks = []
    for rank, item in enumerate(ranked[:10], start=1):
        peaks.append({
            **item,
            "rank": rank,
            "relative_intensity": round(item["count"] / average, 3) if average else 0,
            "z_score": round((item["count"] - average) / stddev, 3) if stddev else 0,
        })
    return {
        "window_seconds": window,
        "total_messages": len(messages),
        "unique_users": len(all_users),
        "average": round(average, 3),
        "median": median,
        "stddev": round(stddev, 3),
        "p90": p90,
        "duration_seconds": round(duration_seconds, 3),
        "total_windows": len(counts),
        "active_windows": sum(1 for count in counts if count > 0),
        "coverage_percent": round(sum(1 for count in counts if count > 0) / len(counts) * 100, 2),
        "above_average_windows": sum(1 for count in counts if count > average),
        "max_rate_per_second": round(max(counts) / window, 3),
        "peak_share_percent": round(max(counts) / len(messages) * 100, 2),
        "user_message_ratio": round(len(messages) / len(all_users), 3) if all_users else 0,
        "max_count": max(counts),
        "timeline": timeline,
        "peaks": peaks,
    }
