"""把历史遗留的多处模型目录迁移到单一模型根目录,并重写数据库路径。

背景
----
模型文件曾在两个目录下:锦界交付包在 ``server/static/models/``,而上传钻孔
Excel 生成的交付包在 ``backend/uploads/projects/<project_id>/web_package/``,
手动上传的模型版本在 ``backend/uploads/models/<asset_id>/``。两套目录 + 两套
公开前缀(/static/models 与 /uploads)+ ``model_versions.storage_scope`` 分支,
排查"到底加载了哪个文件"非常费劲。

现在所有模型文件都在 ``settings.source_model_path``(默认
``server/static/models``),对外统一挂在 ``/static/models``:

    <model_root>/web_package/                     锦界交付包
    <model_root>/projects/<project_id>/web_package/  上传建模交付包
    <model_root>/user_uploads/<asset_id>/v<n>.glb    手动上传版本

本脚本做三件事(默认只打印计划,``--apply`` 才执行):
1. 把 ``uploads/projects/<pid>/web_package`` 移到 ``<model_root>/projects/<pid>/web_package``;
2. 把 ``uploads/models/<asset_id>`` 移到 ``<model_root>/user_uploads/<asset_id>``;
3. 重写 ``model_assets.metadata_json`` 的路径/URL 字段与
   ``model_versions.file_path`` / ``storage_scope``,并按实际文件复核。

可重复执行(已迁移的部分会被跳过)。

用法::

    python scripts/migrate_models_single_root.py            # 只看计划
    python scripts/migrate_models_single_root.py --apply    # 执行
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionFactory  # noqa: E402
from app.models.asset import ModelAsset, ModelVersion  # noqa: E402
from app.services.model_paths import (  # noqa: E402
    PROJECTS_DIR,
    USER_UPLOADS_DIR,
    combined_variant_metadata,
    model_root,
    variant_metadata,
)

# metadata 中保存"相对模型根的路径"的字段
PATH_FIELDS = ("source_file", "render_file", "shell_file")

# 旧相对路径(相对 upload_path) → 新相对路径(相对模型根) 的映射
OLD_PREFIX_MAP = (("models/", f"{USER_UPLOADS_DIR}/"),)


def remap_relative(path: str) -> str:
    for old, new in OLD_PREFIX_MAP:
        if path.startswith(old):
            return new + path[len(old):]
    return path


def plan_moves() -> list[tuple[Path, Path]]:
    """列出待移动的目录(源目录存在、目标目录尚未占用)。"""
    upload_root = settings.upload_path
    root = model_root()
    moves: list[tuple[Path, Path]] = []

    projects_src = upload_root / PROJECTS_DIR
    for package in sorted(projects_src.glob("*/web_package")):
        target = root / PROJECTS_DIR / package.parent.name / "web_package"
        moves.append((package.parent, target.parent))

    uploads_src = upload_root / "models"
    for asset_dir in sorted(p for p in uploads_src.glob("*") if p.is_dir()):
        moves.append((asset_dir, root / USER_UPLOADS_DIR / asset_dir.name))
    return moves


def apply_moves(moves: list[tuple[Path, Path]], dry_run: bool) -> int:
    moved = 0
    for source, target in moves:
        if not source.exists():
            continue
        if target.exists():
            print(f"[跳过] 目标已存在(需人工处理): {target}")
            continue
        print(f"[移动] {source} -> {target}")
        moved += 1
        if dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
    return moved


def _package_dir(metadata: dict, file_path: str | None) -> Path | None:
    """由 metadata/版本路径反推交付包目录(含 L*.glb 的目录)。"""
    for value in (metadata.get("render_file"), metadata.get("source_file"), file_path):
        if isinstance(value, str) and value:
            return (model_root() / remap_relative(value)).resolve().parent
    return None


def rewrite_metadata(metadata: dict, file_path: str | None) -> dict:
    """重写 metadata 的路径/URL 字段;无法确定交付包目录时只做前缀重映射。"""
    updated = dict(metadata or {})
    for field in PATH_FIELDS:
        value = updated.get(field)
        if isinstance(value, str) and value:
            updated[field] = remap_relative(value)

    package_dir = _package_dir(metadata, file_path)
    if package_dir is not None and package_dir.is_dir():
        if metadata.get("combined"):
            updated.update(combined_variant_metadata(package_dir))
        else:
            code = str(metadata.get("catalog_code") or "").strip()
            if code:
                updated.update(variant_metadata(package_dir, code, metadata))
    return updated


async def migrate_db(dry_run: bool) -> tuple[int, int, list[str]]:
    """重写 model_versions 与 model_assets;返回 (版本数, 资产数, 缺失文件列表)。"""
    versions_changed = assets_changed = 0
    missing: list[str] = []
    async with AsyncSessionFactory() as session:
        versions = (await session.scalars(select(ModelVersion))).all()
        for version in versions:
            new_path = remap_relative(version.file_path)
            new_scope = "server_static"
            if new_path != version.file_path or version.storage_scope != new_scope:
                versions_changed += 1
                if not dry_run:
                    version.file_path = new_path
                    version.storage_scope = new_scope
            resolved = model_root() / new_path
            if not resolved.is_file():
                missing.append(f"version {version.id}: {new_path}")

        assets = (await session.scalars(select(ModelAsset))).all()
        version_paths = {
            version.model_id: version.file_path
            for version in versions
            if version.id
        }
        for asset in assets:
            metadata = asset.metadata_json or {}
            fallback = version_paths.get(asset.id)
            updated = rewrite_metadata(metadata, fallback)
            if updated != metadata:
                assets_changed += 1
                if not dry_run:
                    asset.metadata_json = updated

        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    return versions_changed, assets_changed, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="模型文件迁移到单一根目录")
    parser.add_argument("--apply", action="store_true", help="实际执行(默认只打印计划)")
    args = parser.parse_args()
    dry_run = not args.apply

    root = model_root()
    print(f"模型根目录: {root}")
    print(f"上传目录  : {settings.upload_path}")
    print("模式      :", "DRY-RUN(加 --apply 执行)" if dry_run else "APPLY")

    moves = plan_moves()
    if not moves:
        print("没有需要移动的模型目录。")
    moved = apply_moves(moves, dry_run)

    import asyncio

    versions_changed, assets_changed, missing = asyncio.run(migrate_db(dry_run))
    print(
        f"\n数据库: 版本行待改 {versions_changed} / 资产 metadata 待改 {assets_changed}"
        + ("(未提交)" if dry_run else "(已提交)")
    )
    if missing:
        print("⚠ 以下文件在模型根目录下找不到(迁移前就缺失):")
        for item in missing[:20]:
            print("   ", item)
        if len(missing) > 20:
            print(f"    ... 另有 {len(missing) - 20} 条")
    print(f"\n移动目录 {moved} 个。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
