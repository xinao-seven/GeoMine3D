"""项目统计分析服务。

数值核心抽成纯函数，便于在不依赖数据库的情况下单元测试；
数据库聚合部分只负责取数，再把行记录交给纯函数计算。
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence


def thickness_distribution(
    segments: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """按地层名聚合厚度统计，结果按地层平均顶深排序。

    每条记录需包含 layer_name / top_depth / thickness。
    """
    buckets: dict[str, dict[str, Any]] = {}
    for row in segments:
        name = str(row.get("layer_name") or "").strip()
        if not name:
            continue
        thickness = float(row.get("thickness") or 0)
        top = float(row.get("top_depth") or 0)
        bucket = buckets.setdefault(
            name,
            {"layer_name": name, "count": 0, "total": 0.0, "min": math.inf, "max": -math.inf, "top_sum": 0.0},
        )
        bucket["count"] += 1
        bucket["total"] += thickness
        bucket["min"] = min(bucket["min"], thickness)
        bucket["max"] = max(bucket["max"], thickness)
        bucket["top_sum"] += top

    result = []
    for bucket in buckets.values():
        count = bucket["count"]
        result.append(
            {
                "layer_name": bucket["layer_name"],
                "count": count,
                "avg_thickness": round(bucket["total"] / count, 3) if count else 0.0,
                "min_thickness": round(bucket["min"], 3) if count else 0.0,
                "max_thickness": round(bucket["max"], 3) if count else 0.0,
                "avg_top_depth": round(bucket["top_sum"] / count, 3) if count else 0.0,
            }
        )
    result.sort(key=lambda item: item["avg_top_depth"])
    return result


def layer_frequency(segments: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """统计每个地层名出现在多少个钻孔中，按平均顶深排序。"""
    per_layer: dict[str, dict[str, Any]] = {}
    for row in segments:
        name = str(row.get("layer_name") or "").strip()
        if not name:
            continue
        bucket = per_layer.setdefault(
            name, {"borehole_ids": set(), "top_sum": 0.0, "top_count": 0}
        )
        borehole_id = row.get("borehole_id")
        if borehole_id:
            bucket["borehole_ids"].add(str(borehole_id))
        bucket["top_sum"] += float(row.get("top_depth") or 0)
        bucket["top_count"] += 1

    result = [
        {
            "layer_name": name,
            "borehole_count": len(bucket["borehole_ids"]),
            "avg_top_depth": round(bucket["top_sum"] / bucket["top_count"], 3)
            if bucket["top_count"]
            else 0.0,
        }
        for name, bucket in per_layer.items()
    ]
    result.sort(key=lambda item: item["avg_top_depth"])
    return result


def depth_distribution(
    depths: Sequence[float], target_bins: int = 8
) -> dict[str, Any]:
    """钻孔总深分布：基本统计量 + 自适应等宽直方图。"""
    values = [float(d) for d in depths if d and d > 0]
    if not values:
        return {"count": 0, "min": 0.0, "max": 0.0, "avg": 0.0, "bins": []}

    lo, hi = min(values), max(values)
    avg = sum(values) / len(values)
    bins = _histogram(values, lo, hi, target_bins)
    return {
        "count": len(values),
        "min": round(lo, 2),
        "max": round(hi, 2),
        "avg": round(avg, 2),
        "bins": bins,
    }


def _histogram(
    values: Sequence[float], lo: float, hi: float, target_bins: int
) -> list[dict[str, Any]]:
    if hi <= lo:
        return [
            {
                "start": round(lo, 2),
                "end": round(hi, 2),
                "count": len(values),
            }
        ]
    raw_step = (hi - lo) / max(target_bins, 1)
    magnitude = 10 ** math.floor(math.log10(raw_step)) if raw_step > 0 else 1
    step = 1.0
    for candidate in (1, 2, 2.5, 5, 10):
        step = candidate * magnitude
        if step >= raw_step:
            break
    start = math.floor(lo / step) * step
    end = math.ceil(hi / step) * step
    bin_count = max(int(round((end - start) / step)), 1)
    counts = [0] * bin_count
    for value in values:
        index = min(int((value - start) / step), bin_count - 1)
        counts[index] += 1
    return [
        {
            "start": round(start + i * step, 2),
            "end": round(start + (i + 1) * step, 2),
            "count": counts[i],
        }
        for i in range(bin_count)
    ]


def workingface_status(faces: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """工作面按状态分组计数，并汇总尺寸信息。"""
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "length_sum": 0.0, "width_sum": 0.0, "sized": 0}
    )
    for face in faces:
        status = str(face.get("status") or "未知").strip() or "未知"
        bucket = buckets[status]
        bucket["count"] += 1
        length = face.get("length")
        width = face.get("width")
        if length and width:
            bucket["length_sum"] += float(length)
            bucket["width_sum"] += float(width)
            bucket["sized"] += 1

    return [
        {
            "status": status,
            "count": bucket["count"],
            "avg_length": round(bucket["length_sum"] / bucket["sized"], 1)
            if bucket["sized"]
            else None,
            "avg_width": round(bucket["width_sum"] / bucket["sized"], 1)
            if bucket["sized"]
            else None,
        }
        for status, bucket in sorted(buckets.items(), key=lambda item: -item[1]["count"])
    ]


def coal_thickness_by_borehole(
    segments_by_borehole: Mapping[str, Sequence[Mapping[str, Any]]],
    coal_keywords: Sequence[str] = ("煤",),
) -> dict[str, dict[str, Any]]:
    """按钻孔聚合煤层（名称含关键字的层）合计厚度。"""
    result: dict[str, dict[str, Any]] = {}
    for borehole_id, segments in segments_by_borehole.items():
        total = 0.0
        layers: list[str] = []
        for row in segments:
            name = str(row.get("layer_name") or "")
            if any(keyword in name for keyword in coal_keywords):
                total += float(row.get("thickness") or 0)
                if name not in layers:
                    layers.append(name)
        result[borehole_id] = {"coal_thickness": round(total, 3), "coal_layers": layers}
    return result


def build_overview(
    boreholes: Sequence[Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
    faces: Sequence[Mapping[str, Any]],
    model_count: int,
) -> dict[str, Any]:
    """组合统计概览（不含模型/导入细节）。"""
    depths = [float(b.get("total_depth") or 0) for b in boreholes]
    strata_layers = {str(s.get("layer_name")).strip() for s in segments if s.get("layer_name")}
    return {
        "borehole_count": len(boreholes),
        "segment_count": len(segments),
        "strata_layer_count": len(strata_layers),
        "model_count": model_count,
        "workingface_count": len(faces),
        "total_drilling_depth": round(sum(depths), 1),
        "avg_borehole_depth": round(sum(depths) / len(depths), 1) if depths else 0.0,
        "max_borehole_depth": round(max(depths), 1) if depths else 0.0,
        "thickness_distribution": thickness_distribution(segments),
        "depth_distribution": depth_distribution(depths),
        "layer_frequency": layer_frequency(segments),
        "workingface_status": workingface_status(faces),
    }
