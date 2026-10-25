"""界面趋势与高斯过程插值(移植自论文第3/4章)。

- SharedTrend / shared_trend: 全部界面共享的平面线性趋势
  (src/evaluation/interpolation_breakthrough_poc.SharedTrend +
   experiments/scripts/chapter03/build_chapter03_revision.shared_trend);
- ExtendedConfig / make_gp: 逐界面残差 GP
  (src/evaluation/route_a_extended_validation);
- latent_std: GP 隐函数后验标准差(build_refined_surfaces.latent_std)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.linalg import solve_triangular
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import (
    ConstantKernel,
    Matern,
    RBF,
    WhiteKernel,
)


class ExtendedConfig:
    random_state: int = 42
    initial_length_scale_m: float = 800.0
    initial_noise_level: float = 8.0
    alpha: float = 1e-4


def make_gp(kind: str, cfg: ExtendedConfig) -> GaussianProcessRegressor:
    if kind == "matern_ard":
        spatial = Matern(
            np.array([cfg.initial_length_scale_m, cfg.initial_length_scale_m]),
            (1e-2, 1e5),
            nu=1.5,
        )
    elif kind == "rbf":
        spatial = RBF(cfg.initial_length_scale_m, (1e-2, 1e5))
    elif kind == "matern_iso":
        spatial = Matern(cfg.initial_length_scale_m, (1e-2, 1e5), nu=1.5)
    else:
        raise ValueError(f"Unknown GP kind: {kind}")
    kernel = ConstantKernel(1.0, (1e-3, 1e3)) * spatial + WhiteKernel(
        cfg.initial_noise_level, (1e-8, 1e3)
    )
    return GaussianProcessRegressor(
        kernel=kernel,
        alpha=cfg.alpha,
        normalize_y=True,
        n_restarts_optimizer=0,
        random_state=cfg.random_state,
    )


class SharedTrend:
    """各界面共享一个截距 + 平面线性项的趋势模型。"""

    def __init__(self, interfaces: list[str]):
        self.interfaces = interfaces
        self.interface_to_idx = {name: idx for idx, name in enumerate(interfaces)}
        self.center = np.zeros(2)
        self.coef = np.zeros(len(interfaces) + 2)

    def predict(self, interface: str, xy: np.ndarray) -> np.ndarray:
        xy = np.asarray(xy, dtype=float)
        xy_km = (xy - self.center) / 1000.0
        return self.coef[self.interface_to_idx[interface]] + xy_km @ self.coef[-2:]


def shared_trend(
    points: pd.DataFrame, interfaces: list[str], equal_interface_weight: bool = False
) -> SharedTrend:
    """对全部界面的界面点联合拟合趋势(design: one-hot(界面) + xy_km)。"""
    model = SharedTrend(interfaces)
    model.center = points[["x", "y"]].to_numpy(float).mean(axis=0)
    xy_km = (points[["x", "y"]].to_numpy(float) - model.center) / 1000.0
    design = np.zeros((len(points), len(interfaces) + 2), dtype=float)
    for row_idx, interface in enumerate(points["interface"].astype(str)):
        design[row_idx, model.interface_to_idx[interface]] = 1.0
    design[:, -2:] = xy_km
    if equal_interface_weight:
        counts = points.groupby("interface")["interface"].transform("size").to_numpy(float)
        root_w = np.sqrt(1.0 / counts)
        model.coef = np.linalg.lstsq(
            design * root_w[:, None], points["z"].to_numpy(float) * root_w, rcond=None
        )[0]
    else:
        model.coef = np.linalg.lstsq(design, points["z"].to_numpy(float), rcond=None)[0]
    return model


def latent_std(model: GaussianProcessRegressor, query: np.ndarray) -> np.ndarray:
    """GP 信号分量的后验标准差(不含白噪声),与论文实现逐行一致。"""
    if model is None:
        return np.zeros(len(query), dtype=float)
    signal_kernel = model.kernel_.k1
    k_trans = signal_kernel(query, model.X_train_)
    v = solve_triangular(model.L_, k_trans.T, lower=True, check_finite=False)
    variance = signal_kernel.diag(query) - np.einsum("ij,ji->i", v.T, v)
    y_scale = float(np.asarray(model._y_train_std).reshape(-1)[0])
    return np.sqrt(np.maximum(variance, 0.0)) * y_scale
