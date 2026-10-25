"""矿区边界/工作面范围 Shapefile 解析服务。

交付数据里的 shp 是 CAD 折线导出（非面要素）：井田边界一条折线、
开采工作面为一批闭合矩形折线。这里按折线读取并做进程内缓存（按 mtime 失效），
前端负责把投影坐标换算为场景坐标后绘制贴地线框；闭合的工作面折线同时
供储量估算做面积计算。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import shapefile

from app.core.config import settings

_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_lock = threading.Lock()


def _resolve(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    return settings.source_data_path / path


def read_polylines(relative_path: str) -> list[dict[str, Any]]:
    """读取折线 shp，返回 [{name, points, bbox}]；文件缺失时返回空列表。"""
    path = _resolve(relative_path)
    if not path.exists():
        return []

    mtime = path.stat().st_mtime
    cache_key = str(path)
    with _lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] == mtime:
            return cached[1]

    reader = shapefile.Reader(str(path))
    records: list[dict[str, Any]] = []
    for index, shape_record in enumerate(reader.shapeRecords()):
        raw = shape_record.record
        fields = raw.as_dict() if hasattr(raw, "as_dict") else dict(raw)
        name = str(fields.get("Layer") or fields.get("RefName") or f"shape_{index + 1}")
        points = [
            [round(float(x), 3), round(float(y), 3)]
            for x, y in shape_record.shape.points
        ]
        if len(points) < 2:
            continue
        records.append(
            {
                "name": name,
                "points": points,
                "bbox": [round(float(v), 2) for v in shape_record.shape.bbox],
            }
        )

    with _lock:
        _cache[cache_key] = (mtime, records)
    return records


def load_boundaries() -> dict[str, Any]:
    """汇总矿区边界与工作面范围折线。"""
    return {
        "mine": read_polylines(settings.mine_boundary_shp),
        "workingfaces": read_polylines(settings.workingface_boundary_shp),
    }
