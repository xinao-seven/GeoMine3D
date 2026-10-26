"""交付包双轨产物(渲染轨 / 分析轨)的路径与公开 URL 解析。

建模引擎(modeling_engine)对同一个分层体元集合同时导出两套几何:

- 渲染轨 ``render``:``<pkg>/{code}.glb``(以及 ``model_combined.glb``、``z20/``、
  ``lods/``)。含内部棱柱壁(相邻体元共享侧面按无向键单份保留),剖切后内部
  呈柱状实体、无需补面;非水密,渲染端必须 ``DoubleSide``。
- 分析轨 ``shell``:``<pkg>/shells/{code}_shell.glb``。闭合水密壳,供剖面求交、
  体积、等值线等数值分析使用。

两套产物都参与注册:``metadata.source_file`` 指向渲染轨,``metadata.shell_file``
指向分析轨;下载走 ``GET /api/v1/models/{id}/file?variant=render|shell``。
旧交付包没有 ``shells/`` 目录时 ``shell_file`` 为 ``None``,``variant=shell``
会明确报 404 而不是悄悄回退到渲染网格(否则剖面求交会与内部壁相交)。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.core.exceptions import AppError

# storage_scope → 静态公开前缀(与 app/main.py 的挂载点一致)
PUBLIC_PREFIX_BY_SCOPE: dict[str, str] = {
    "server_static": "/static/models",
    "upload": "/uploads",
}

VARIANTS = ("render", "shell")


def relative_to_root(path: Path, root: Path) -> str:
    """文件相对存储根的 POSIX 路径;越界时按 500 处理(与导入服务一致)。"""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise AppError(
            "MODEL_PATH_OUTSIDE_ROOT",
            f"模型文件不在存储根目录 {root} 之下: {path}",
            status_code=500,
        ) from exc


def public_url(scope: str, relative_path: str) -> str:
    prefix = PUBLIC_PREFIX_BY_SCOPE.get(scope)
    if prefix is None:
        raise AppError("MODEL_STORAGE_INVALID", f"未知存储范围: {scope}", status_code=500)
    return f"{prefix}/{relative_path.lstrip('/')}"


def package_variant_files(package_dir: Path, code: str) -> dict[str, Path | None]:
    """按约定解析一层的渲染轨/分析轨文件(不判断是否存在)。"""
    return {
        "render": package_dir / f"{code}.glb",
        "shell": package_dir / "shells" / f"{code}_shell.glb",
    }


def package_combined_variant_files(package_dir: Path) -> dict[str, Path]:
    """合并场景的两轨文件(LOD 不适用)。"""
    return {
        "render": package_dir / "model_combined.glb",
        "shell": package_dir / "model_combined_shell.glb",
    }


def _variant_urls(
    root: Path, scope: str, files: dict[str, Path]
) -> tuple[dict[str, str], str | None]:
    """渲染轨必然存在(已在上游校验);分析轨存在时才写 shell_file。"""
    render_rel = relative_to_root(files["render"], root)
    shell_path = files.get("shell")
    shell_rel = (
        relative_to_root(shell_path, root)
        if shell_path is not None and shell_path.is_file()
        else None
    )
    variant_urls = {
        "render": public_url(scope, render_rel),
        "shell": public_url(scope, shell_rel) if shell_rel else None,
    }
    return variant_urls, shell_rel


def combined_variant_metadata(
    root: Path, scope: str, package_dir: Path
) -> dict[str, Any]:
    """合并场景的双轨 metadata(前端“含内部壁 / 空心壳”两个加载按钮都靠它)。"""
    files = package_combined_variant_files(package_dir)
    variant_urls, shell_rel = _variant_urls(root, scope, files)
    return {
        "render_file": relative_to_root(files["render"], root),
        "shell_file": shell_rel,
        "variant_urls": variant_urls,
    }


def variant_metadata(
    root: Path,
    scope: str,
    package_dir: Path,
    code: str,
    layer: Mapping[str, Any],
) -> dict[str, Any]:
    """生成模型资产的双轨 metadata 片段(路径为相对存储根,URL 为静态地址)。

    只写入实际存在的文件:``shell_file`` 为 ``None`` 表示该包没有分析轨
    (旧包),前端/接口据此判断 ``variant=shell`` 不可用。
    """
    files = package_variant_files(package_dir, code)
    variant_urls, shell_rel = _variant_urls(
        root, scope, {"render": files["render"], "shell": files["shell"]}
    )

    lod_urls: dict[str, str] = {}
    lod_files: dict[str, str] = {}
    for lod in layer.get("lods") or []:
        name = str(lod.get("name") or "").strip()
        raw = str(lod.get("path") or "").strip()
        if not name or not raw:
            continue
        lod_path = Path(raw)
        if not lod_path.is_file():
            # 旧 catalog 里可能是生成机的绝对路径,按同目录约定回退定位
            lod_path = package_dir / "lods" / lod_path.name
        if not lod_path.is_file():
            continue
        rel = relative_to_root(lod_path, root)
        lod_files[name] = rel
        lod_urls[name] = public_url(scope, rel)

    return {
        "render_file": relative_to_root(files["render"], root),
        "shell_file": shell_rel,
        "variant_urls": variant_urls,
        "lod_files": lod_files,
        "lod_urls": lod_urls,
    }


def resolve_variant_path(
    metadata: Mapping[str, Any] | None,
    variant: str,
    fallback_file_path: str | None,
) -> str | None:
    """把 variant 解析成相对存储根的文件路径;均为空返回 None。

    ``variant=render`` 优先 ``metadata.render_file``,其次 ``source_file``,
    最后回退到 model_versions.file_path(兼容历史数据)。
    """
    meta = metadata or {}
    if variant == "shell":
        return meta.get("shell_file") or None
    return (
        meta.get("render_file")
        or meta.get("source_file")
        or fallback_file_path
        or None
    )
