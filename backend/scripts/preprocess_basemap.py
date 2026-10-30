"""把交付包里的 GeoTIFF DEM 预处理成三维场景可用的平面底图。

源数据：server/data/tif/20260211.tif —— float32 高程栅格，EPSG:32649
（WGS84 / UTM 49N，20m 分辨率）。钻孔/边界使用 CGCS2000 3° 带 Gauss-Kruger
37 带（带号前缀，东向 ~3742xxxx），因此脚本在目标网格上重采样重投影，
输出北向上的灰度地形底图 + 地理范围元数据：

    server/static/models/basemap/basemap.jpg
    server/static/models/basemap/basemap.json   # {xmin,xmax,ymin,ymax,width_px,height_px,...}

前端 /static/models 已挂载，直接按元数据铺放平面纹理即可；元数据不存在
（未运行本脚本）时底图功能自动隐藏。

用法：
    python scripts/preprocess_basemap.py
可选参数：--source / --output / --max-px / --zmin / --zmax
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import numpy as np

DEFAULT_SOURCE = Path("../server/data/tif/20260211.tif")
DEFAULT_OUTPUT_DIR = Path("../server/static/models/basemap")
MAX_SIDE_DEFAULT = 2048

# 交付 DEM 的源坐标系（WGS84 / UTM 49N）与目标（CGCS2000 3° 带 GK 37 带，
# 带号前缀 false easting=37500000，中央子午线 111°E）
SOURCE_CRS = "EPSG:32649"
TARGET_PROJ4 = (
    "+proj=tmerc +lat_0=0 +lon_0=111 +k=1 +x_0=37500000 +y_0=0 "
    "+ellps=GRS80 +units=m +no_defs"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(BACKEND_DIR / DEFAULT_SOURCE))
    parser.add_argument("--output-dir", default=str(BACKEND_DIR / DEFAULT_OUTPUT_DIR))
    parser.add_argument("--max-px", type=int, default=MAX_SIDE_DEFAULT)
    parser.add_argument("--zmin", type=float, default=None, help="灰度下限(米)，默认取 2%% 分位")
    parser.add_argument("--zmax", type=float, default=None, help="灰度上限(米)，默认取 98%% 分位")
    return parser.parse_args()


def read_dem(path: Path) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """读取 float32 DEM 与其 UTM 坐标范围 (xmin, ymin, xmax, ymax)。"""
    import tifffile

    with tifffile.TiffFile(str(path)) as tif:
        page = tif.pages[0]
        data = page.asarray()
        scale = page.tags.get("ModelPixelScaleTag")
        tiepoint = page.tags.get("ModelTiepointTag")
        if scale is None or tiepoint is None:
            raise SystemExit("源 TIFF 缺少地理参考标签(ModelPixelScale/ModelTiepoint)")
        px, py = float(scale.value[0]), float(scale.value[1])
        ox, oy = float(tiepoint.value[3]), float(tiepoint.value[4])
    if data.ndim == 3:
        data = data[0]
    height, width = data.shape
    # 像元中心 → 外边界范围
    return data, (ox - px / 2, oy - py * height - py / 2, ox + px * width - px / 2, oy - py / 2)


def resample_to_target(
    dem: np.ndarray,
    utm_bounds: tuple[float, float, float, float],
    target_bounds: tuple[float, float, float, float],
    out_size: tuple[int, int],
) -> np.ndarray:
    """把 UTM 网格的 DEM 重采样到目标投影的规则网格（双线性）。"""
    from pyproj import CRS, Transformer

    tx_min, ty_min, tx_max, ty_max = target_bounds
    out_w, out_h = out_size
    xs = np.linspace(tx_min, tx_max, out_w)
    ys = np.linspace(ty_max, ty_min, out_h)  # 图像自上而下 = 北到南
    grid_x, grid_y = np.meshgrid(xs, ys)

    transformer = Transformer.from_crs(CRS.from_proj4(TARGET_PROJ4), CRS(SOURCE_CRS), always_xy=True)
    utm_x, utm_y = transformer.transform(grid_x, grid_y)

    # UTM 源网格上的双线性采样
    sx_min, sy_min, sx_max, sy_max = utm_bounds
    height, width = dem.shape
    px = (sx_max - sx_min) / width
    py = (sy_max - sy_min) / height
    fx = (utm_x - sx_min) / px - 0.5
    fy = (sy_max - utm_y) / py - 0.5

    fx = np.clip(fx, 0, width - 2)
    fy = np.clip(fy, 0, height - 2)
    x0 = np.floor(fx).astype(np.int64)
    y0 = np.floor(fy).astype(np.int64)
    wx = fx - x0
    wy = fy - y0

    top = dem[y0, x0] * (1 - wx) + dem[y0, x0 + 1] * wx
    bottom = dem[y0 + 1, x0] * (1 - wx) + dem[y0 + 1, x0 + 1] * wx
    return top * (1 - wy) + bottom * wy


def to_grayscale(surface: np.ndarray, zmin: float | None, zmax: float | None) -> tuple[np.ndarray, float, float]:
    valid = np.isfinite(surface) & (surface > -1e30)
    if not valid.any():
        raise SystemExit("DEM 无有效值（全部为 nodata）")
    values = surface[valid]
    lo = float(np.percentile(values, 2)) if zmin is None else zmin
    hi = float(np.percentile(values, 98)) if zmax is None else zmax
    if hi <= lo:
        hi = lo + 1.0
    stretched = np.clip((surface - lo) / (hi - lo), 0, 1)
    stretched[~valid] = 1.0  # 无值区渲染为白
    return (stretched * 255).astype(np.uint8), lo, hi


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    if not source.exists():
        raise SystemExit(f"源 DEM 不存在: {source}")

    dem, utm_bounds = read_dem(source)
    scale = (utm_bounds[2] - utm_bounds[0]) / dem.shape[1]

    from pyproj import CRS, Transformer

    to_target = Transformer.from_crs(CRS(SOURCE_CRS), CRS.from_proj4(TARGET_PROJ4), always_xy=True)
    corners_src = [
        (utm_bounds[0], utm_bounds[1]),
        (utm_bounds[2], utm_bounds[1]),
        (utm_bounds[2], utm_bounds[3]),
        (utm_bounds[0], utm_bounds[3]),
    ]
    corner_x, corner_y = to_target.transform(
        [c[0] for c in corners_src], [c[1] for c in corners_src]
    )
    target_bounds = (min(corner_x), min(corner_y), max(corner_x), max(corner_y))

    aspect = (target_bounds[2] - target_bounds[0]) / (target_bounds[3] - target_bounds[1])
    if aspect >= 1:
        out_w = args.max_px
        out_h = max(1, round(args.max_px / aspect))
    else:
        out_h = args.max_px
        out_w = max(1, round(args.max_px * aspect))

    print(f"[basemap] DEM {dem.shape[1]}x{dem.shape[0]} @ {scale:.0f}m → 重采样 {out_w}x{out_h}")
    valid_ratio = float(np.mean(dem > -1e30))
    if valid_ratio < 0.5:
        print(f"[basemap] 警告: DEM 有效像元占比仅 {valid_ratio:.1%}")
    surface = resample_to_target(dem, utm_bounds, target_bounds, (out_w, out_h))
    gray, lo, hi = to_grayscale(surface, args.zmin, args.zmax)

    # 目标范围与有效数据范围都换算到目标坐标系后检查是否可能有重叠数据
    from pyproj import CRS, Transformer as _T
    _t = _T.from_crs(CRS(SOURCE_CRS), CRS.from_proj4(TARGET_PROJ4), always_xy=True)
    src_valid = dem > -1e30
    if src_valid.any():
        rows = np.where(src_valid.any(axis=1))[0]
        cols = np.where(src_valid.any(axis=0))[0]
        sx_min, sy_min, sx_max, sy_max = utm_bounds
        px = (sx_max - sx_min) / dem.shape[1]
        py = (sy_max - sy_min) / dem.shape[0]
        vx = [sx_min + cols.min() * px, sx_min + cols.max() * px]
        vy = [sy_max - rows.max() * py, sy_max - rows.min() * py]
        gx, gy = _t.transform(vx, vy)
        print(
            "[basemap] DEM 有效数据范围(目标坐标系): "
            f"x {min(gx):.0f}~{max(gx):.0f}, y {min(gy):.0f}~{max(gy):.0f}"
        )
        mine_hint = "（请确认该范围与项目矿区一致，否则底图不会出现在场景中）"
        print(f"[basemap] {mine_hint}")

    from PIL import Image

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / "basemap.jpg"
    Image.fromarray(gray, mode="L").convert("RGB").save(str(image_path), quality=85)

    meta = {
        "image": "basemap.jpg",
        "width_px": out_w,
        "height_px": out_h,
        "bounds": {
            "xmin": round(target_bounds[0], 3),
            "ymin": round(target_bounds[1], 3),
            "xmax": round(target_bounds[2], 3),
            "ymax": round(target_bounds[3], 3),
        },
        "crs": "CGCS2000 3-degree Gauss-Kruger zone 37 (带号前缀)",
        "source_crs": SOURCE_CRS,
        "source_file": str(source.name),
        "elevation_range_m": [round(lo, 1), round(hi, 1)],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = output_dir / "basemap.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[basemap] 已生成 {image_path}")
    print(f"[basemap] 范围(GK37带): {meta['bounds']} 高程 {meta['elevation_range_m']} m")


if __name__ == "__main__":
    main()
