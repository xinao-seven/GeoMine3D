"""交付包重建脚本:按既有曲面 npz 重新生成双轨产物并可同步数据库注册。

用途
----
建模引擎的侧表面网格算法变更后(例如 2026-10 引入“渲染轨含内部棱柱壁 +
分析轨闭合壳”),既有交付包里的同名 GLB 会与代码不一致,需要在不重跑
GP 插值的前提下原地重建。本脚本:

1. 读取曲面 npz(``x``/``y``/``corrected``/``latent_std``/``pinchout_masks``),
   调用 ``modeling_engine.package_builder.build_web_package`` 生成:
   - 渲染轨 ``L*.glb`` / ``model_combined.glb`` / ``z20/`` / ``lods/``(含内部壁);
   - 分析轨 ``shells/L*_shell.glb``(闭合壳);
   - 新 ``catalog.json`` / ``README.md``。
2. 从旧 catalog 保留不可再生的元数据(来源链、ACT 参数、井巷文件清单等)。
3. ``--project-id`` 时同步数据库:重写模型资产的 ``metadata.shell_file`` /
   ``lod_urls`` 与 ``model_versions`` 的 file_size / content_hash
   (``storage_scope`` 由交付包位置自动判定)。

示例
----
::

    # 锦界 server_static 交付包:保持 z_origin 不变,重建后同步到项目
    python scripts/rebuild_web_package.py \\
        --package ../server/static/models/web_package \\
        --npz E:/code/model-thesis-private/experiments/data/chapters/\\
chapter04_uncertainty_order_projection/model_visualization_refined/\\
square_direct_ard_pinchout_surfaces_refined.npz \\
        --project-id d8fafee7-3d51-47cd-b586-c632c1069c36

    # 上传建模项目交付包(曲面 npz 由建模任务留在 uploads/modeling-jobs/<id>/)
    python scripts/rebuild_web_package.py \\
        --package uploads/projects/<pid>/web_package \\
        --npz uploads/modeling-jobs/<job>/surfaces.npz \\
        --project-id <pid>

不加 ``--project-id`` 时只重建文件,不动数据库。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import numpy as np  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionFactory  # noqa: E402
from app.models.modeling import ModelingJob  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.services.modeling_service import register_models_from_catalog  # noqa: E402
from app.services.server_import_service import ServerDataImportService  # noqa: E402
from modeling_engine import package_builder  # noqa: E402

# 重建时从旧 catalog 原样保留的键:来源链与锦界专属井巷清单无法由曲面 npz 复原。
PRESERVED_KEYS = ("act_params", "source", "workings", "workings_glb", "consumer")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_surfaces(npz_path: Path) -> dict[str, Any]:
    data = np.load(npz_path, allow_pickle=True)
    missing = [k for k in ("x", "y", "corrected", "latent_std", "pinchout_masks") if k not in data]
    if missing:
        raise SystemExit(f"曲面 npz 缺少字段: {missing} (实际: {list(data.files)})")
    return {
        "xy_global": np.column_stack([data["x"], data["y"]]).astype(float),
        "surfaces": data["corrected"].astype(float),
        "latent_std": data["latent_std"].astype(float),
        "pinchout_masks": data["pinchout_masks"].astype(bool),
        "pinchout_threshold_m": float(data["pinchout_threshold_m"])
        if "pinchout_threshold_m" in data
        else 0.5,
    }


def _layer_names_from_catalog(catalog: dict[str, Any]) -> list[str]:
    names = [str(layer.get("name_cn") or layer.get("code")) for layer in catalog.get("layers") or []]
    if not names:
        raise SystemExit("旧 catalog 没有 layers,无法确定层名;请提供 --layer-names")
    return names


async def _refresh_database(
    package_dir: Path, catalog: dict[str, Any], project_id: str, vertical_scale: float
) -> str:
    """按交付包位置判定存储范围,复用导入/建模服务的注册逻辑刷新资产行。"""
    source_root = settings.source_model_path.resolve()
    upload_root = settings.upload_path.resolve()
    resolved = package_dir.resolve()

    async with AsyncSessionFactory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise SystemExit(f"项目不存在: {project_id}")

        if resolved.is_relative_to(source_root):
            expected = settings.source_model_catalog_path.parent.resolve()
            if resolved != expected:
                raise SystemExit(
                    f"server_static 交付包必须位于 {expected} (与 SOURCE_MODEL_CATALOG 一致),"
                    f"当前为 {resolved}"
                )
            service = ServerDataImportService(session)
            count = await service.upsert_models_from_catalog(project, catalog)
            scope = "server_static"
        elif resolved.is_relative_to(upload_root):
            job_row = await session.scalar(
                select(ModelingJob)
                .where(ModelingJob.project_id == project_id)
                .order_by(ModelingJob.created_at.desc())
                .limit(1)
            )
            count = await register_models_from_catalog(
                session, project, package_dir, catalog, vertical_scale, job_row
            )
            scope = "upload"
        else:
            raise SystemExit(
                f"交付包需位于 {source_root} 或 {upload_root} 之下,当前为 {resolved}"
            )

        await session.commit()
    return f"{scope}:{count}"


def rebuild(
    package_dir: Path,
    npz_path: Path,
    layer_names: list[str] | None,
    z_origin_m: float | None,
    z_scale: float | None,
) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    catalog_path = package_dir / "catalog.json"
    old_catalog = _read_json(catalog_path)
    names = layer_names or _layer_names_from_catalog(old_catalog)

    old_origin = (old_catalog.get("origin_restore") or {}).get("z_origin_m")
    origin = float(z_origin_m) if z_origin_m is not None else (
        float(old_origin) if old_origin is not None else None
    )
    if origin is None:
        raise SystemExit("旧 catalog 无 origin_restore.z_origin_m,请用 --z-origin 指定高程基准")
    scale = float(z_scale) if z_scale is not None else float(
        (old_catalog.get("z20_models") or {}).get("scale_z") or
        ((old_catalog.get("origin_restore") or {}).get("display_recommendation") or {}).get("z_scale") or
        20.0
    )

    loaded = _load_surfaces(npz_path)
    if loaded["surfaces"].shape[0] != len(names) + 1:
        raise SystemExit(
            f"层数不匹配: npz 界面 {loaded['surfaces'].shape[0]} vs catalog 层 {len(names)}"
        )

    print(f"[rebuild] {package_dir}")
    print(f"[rebuild] {len(names)} 层, z_origin={origin:.3f}, z_scale={scale:g}")
    result = package_builder.build_web_package(
        xy_global=loaded["xy_global"],
        surfaces=loaded["surfaces"],
        pinchout_masks=loaded["pinchout_masks"],
        latent_std_arr=loaded["latent_std"],
        pinchout_threshold_m=loaded["pinchout_threshold_m"],
        layer_names=names,
        package_dir=package_dir,
        z_scale=scale,
        z_origin_m=origin,
        source_meta=old_catalog.get("source") or {},
        progress=lambda msg: print(f"[rebuild] {msg}"),
    )

    # 保留不可再生元数据(井巷清单、来源链、ACT 参数…)
    catalog = result["catalog"]
    preserved = {k: old_catalog[k] for k in PRESERVED_KEYS if k in old_catalog}
    catalog.update(preserved)
    catalog["schema_version"] = "1.0-refined"
    catalog["rebuild"] = {
        "script": "backend/scripts/rebuild_web_package.py",
        "npz": str(npz_path),
        "z_origin_m": origin,
        "z_scale": scale,
        "preserved_keys": sorted(preserved),
    }
    (package_dir / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"catalog": catalog, "summary": result["summary"], "z_origin_m": origin, "z_scale": scale}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按曲面 npz 重建交付包(双轨产物)并同步注册")
    parser.add_argument("--package", required=True, help="交付包目录(含 catalog.json)")
    parser.add_argument("--npz", required=True, help="曲面 npz(x/y/corrected/latent_std/pinchout_masks)")
    parser.add_argument("--layer-names", default=None, help="逗号分隔层名;缺省取旧 catalog")
    parser.add_argument("--z-origin", type=float, default=None, help="高程基准;缺省取旧 catalog")
    parser.add_argument("--z-scale", type=float, default=None, help="竖向夸张倍数;缺省取旧 catalog")
    parser.add_argument("--project-id", default=None, help="同步该项目的模型资产与版本行")
    args = parser.parse_args(argv)

    names = (
        [item.strip() for item in args.layer_names.split(",") if item.strip()]
        if args.layer_names
        else None
    )
    rebuilt = rebuild(
        Path(args.package), Path(args.npz), names, args.z_origin, args.z_scale
    )
    summary = rebuilt["summary"]
    print(
        f"[rebuild] 完成: 渲染单元 {summary['render_cells']} / 壳单元 {summary['shell_cells']}, "
        f"体积 {summary['total_volume_m3'] / 1e6:,.1f} 百万立方米, "
        f"{summary['elapsed_seconds']:.1f}s"
    )
    if args.project_id:
        scope = asyncio.run(
            _refresh_database(
                Path(args.package),
                rebuilt["catalog"],
                args.project_id,
                float(rebuilt["z_scale"]),
            )
        )
        print(f"[rebuild] 数据库已同步 ({scope})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
