"""保序投影(移植自论文第4章 chapter4_redesign_experiments)。

pava_increasing: 加权 PAVA(池邻 violators algorithm)单调增拟合;
project_order:   加权欧氏投影到 z[k] - z[k+1] >= min_thickness 约束锥,
                 用于逐节点修正界面高程的上下序。
"""
from __future__ import annotations

import numpy as np


def pava_increasing(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    means: list[float] = []
    masses: list[float] = []
    starts: list[int] = []
    ends: list[int] = []
    for i, (value, weight) in enumerate(zip(values, weights)):
        means.append(float(value))
        masses.append(float(weight))
        starts.append(i)
        ends.append(i + 1)
        while len(means) >= 2 and means[-2] > means[-1]:
            mass = masses[-2] + masses[-1]
            mean = (means[-2] * masses[-2] + means[-1] * masses[-1]) / mass
            end = ends[-1]
            means[-2:] = [mean]
            masses[-2:] = [mass]
            ends[-2:] = [end]
            starts.pop()
    fitted = np.empty(len(values), dtype=float)
    for mean, start, end in zip(means, starts, ends):
        fitted[start:end] = mean
    return fitted


def project_order(z: np.ndarray, weights: np.ndarray, min_thickness: float = 0.08) -> np.ndarray:
    """Weighted Euclidean projection onto z[k]-z[k+1] >= min_thickness."""
    out = z.copy()
    finite = np.flatnonzero(np.isfinite(z))
    if not len(finite):
        return out
    breaks = np.flatnonzero(np.diff(finite) > 1)
    for segment in np.split(finite, breaks + 1):
        if len(segment) < 2:
            continue
        local = z[segment]
        transformed = local + np.arange(len(local)) * min_thickness
        fitted = -pava_increasing(-transformed, np.maximum(weights[segment], 1e-8))
        out[segment] = fitted - np.arange(len(local)) * min_thickness
    return out
