"""界面曲面重建(移植自论文 chapter04 build_refined_surfaces.py)。

共享趋势 + 逐界面 Matérn-ARD 残差 GP 插值 → 逐节点加权保序投影 →
0.5m 尖灭折叠,产出 (界面数, 共享节点数) 的高程曲面、隐函数标准差与
尖灭掩膜。与论文实现的差异:网格参数(间距/外扩/尖灭阈值)由调用方传入,
不再依赖论文仓库路径,不产出论文图件。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from modeling_engine.gp import ExtendedConfig, latent_std, make_gp, shared_trend
from modeling_engine.isotonic import project_order


def expanded_support_grid(
    boreholes: pd.DataFrame,
    grid_spacing_m: float = 100.0,
    boundary_padding_m: float = 200.0,
) -> pd.DataFrame:
    """以钻孔 bbox 中心为中心的正方形规则网格,按间距向上取整保证边界外扩。"""
    xy = boreholes[["x", "y"]].dropna().drop_duplicates().to_numpy(float)
    lower = xy.min(axis=0)
    upper = xy.max(axis=0)
    center = (lower + upper) / 2.0
    requested_half_side = np.ptp(xy, axis=0).max() / 2.0 + boundary_padding_m
    half_steps = int(np.ceil(requested_half_side / grid_spacing_m))
    offsets = np.arange(-half_steps, half_steps + 1, dtype=float) * grid_spacing_m
    xs = center[0] + offsets
    ys = center[1] + offsets
    gx, gy = np.meshgrid(xs, ys)
    return pd.DataFrame(np.column_stack([gx.ravel(), gy.ravel()]), columns=["x", "y"])


def interface_names(layers: list[str]) -> list[str]:
    """层序 → 界面名(IF_0 为第 1 层顶,IF_i 为第 i 层底)。"""
    return [f"IF_0_top_{layers[0]}"] + [
        f"IF_{i + 1}_bottom_{layer}" for i, layer in enumerate(layers)
    ]


def build_interface_points(
    boreholes: pd.DataFrame, intervals: pd.DataFrame, layers: list[str]
) -> tuple[list[str], dict[str, pd.DataFrame], pd.DataFrame]:
    """分层记录 → 逐界面控制点(移植自 chapter34_full_experiments.build_interface_points)。"""
    merged = intervals.merge(
        boreholes[["borehole_id", "x", "y", "z"]],
        on="borehole_id",
        how="left",
        validate="many_to_one",
    )
    merged["top_z"] = merged["z"] - merged["top_depth"]
    merged["bottom_z"] = merged["z"] - merged["bottom_depth"]
    names = interface_names(layers)
    records: list[dict] = []
    layer_to_idx = {layer: i for i, layer in enumerate(layers)}
    for row in merged.itertuples(index=False):
        idx = layer_to_idx[row.layer_name]
        records.append(
            {
                "interface": names[idx],
                "borehole_id": row.borehole_id,
                "x": row.x,
                "y": row.y,
                "z": row.top_z,
            }
        )
        records.append(
            {
                "interface": names[idx + 1],
                "borehole_id": row.borehole_id,
                "x": row.x,
                "y": row.y,
                "z": row.bottom_z,
            }
        )
    all_points = pd.DataFrame(records).dropna()
    all_points = (
        all_points.groupby(["interface", "borehole_id"], as_index=False)
        .agg(x=("x", "mean"), y=("y", "mean"), z=("z", "mean"))
        .sort_values(["interface", "borehole_id"])
        .reset_index(drop=True)
    )
    points = {
        name: all_points[all_points["interface"].eq(name)].copy().reset_index(drop=True)
        for name in names
    }
    return names, points, all_points


def direct_elevation_surfaces(
    all_points: pd.DataFrame,
    points: dict[str, pd.DataFrame],
    interfaces: list[str],
    support: pd.DataFrame,
    progress: callable | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """共享趋势 + 逐界面 ARD 残差 GP → 各界面高程与隐函数标准差。"""
    trend_model = shared_trend(all_points, interfaces, equal_interface_weight=False)
    cfg = ExtendedConfig()
    query = support[["x", "y"]].to_numpy(float)
    means, stds = [], []
    for i, interface in enumerate(interfaces, start=1):
        train = points[interface]
        train_xy = train[["x", "y"]].to_numpy(float)
        trend_train = trend_model.predict(interface, train_xy)
        trend_query = trend_model.predict(interface, query)
        residual = train["z"].to_numpy(float) - trend_train
        gp = make_gp("matern_ard", cfg)
        gp.fit(train_xy, residual)
        means.append(trend_query + gp.predict(query))
        stds.append(latent_std(gp, query))
        if progress is not None:
            progress(f"界面插值 {i}/{len(interfaces)} {interface} 控制点 {len(train)}")
    return np.asarray(means), np.asarray(stds)


def zero_thickness_projection(
    raw: np.ndarray, std: np.ndarray, pinchout_threshold_m: float = 0.5
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """逐节点保序投影修正上下序,再按阈值折叠尖灭层。

    返回 (order_projected, corrected, pinchout_masks)。
    """
    projected = raw.copy()
    for node in range(raw.shape[1]):
        weights = 1.0 / np.maximum(std[:, node], 1.0) ** 2
        projected[:, node] = project_order(raw[:, node], weights, min_thickness=0.0)

    corrected = projected.copy()
    masks = np.zeros((raw.shape[0] - 1, raw.shape[1]), dtype=bool)
    for layer in range(raw.shape[0] - 1):
        thickness = corrected[layer] - corrected[layer + 1]
        masks[layer] = thickness <= pinchout_threshold_m
        corrected[layer + 1, masks[layer]] = corrected[layer, masks[layer]]
    return projected, corrected, masks
