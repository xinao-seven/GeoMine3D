"""交付包双轨产物(渲染轨 / 分析轨)的路径与公开 URL 解析。

建模引擎(modeling_engine)对同一个分层体元集合同时导出两套几何:

- 渲染轨 ``render``:``<pkg>/{code}.glb``(以及 ``model_combined.glb``、``z20/``、
  ``lods/``)。含内部棱柱壁(相邻体元共享侧面按无向键单份保留),剖切后内部
  呈柱状实体、无需补面;非水密,渲染端必须 ``DoubleSide``。
- 分析轨 ``shell``:``<pkg>/shells/{code}_shell.glb``。闭合水密壳,供剖面求交、
  体积、等值线等数值分析使用。

**所有模型文件都放在同一个根目录**(``settings.source_model_path``,默认
``server/static/models``),对外统一挂在 ``/static/models`` 上::

    <model_root>/
    ├── web_package/                     # 锦界交付包(含 shells/ lods/ z20/ vtu/)
    ├── projects/<project_id>/web_package/  # 上传钻孔 Excel 生成的项目交付包
    ├── user_uploads/<asset_id>/v<n>.glb    # 手动上传的模型版本
    └── settlement/ 、basemap/            # 固定数据集(沉陷位移场、底图)

``metadata.source_file`` / ``shell_file`` 等一律是相对该根目录的 POSIX 路径,
``model_versions.file_path`` 亦然;数据库的 ``storage_scope`` 只保留历史兼容
(迁移后统一为 ``server_static``,解析时不再按 scope 分叉)。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.core.config import settings
from app.core.exceptions import AppError

# 模型根目录对外统一挂载点(与 app/main.py 的 mount 一致)
PUBLIC_PREFIX = "/static/models"
# 上传建模交付包的子目录
PROJECTS_DIR = "projects"
# 手动上传模型版本的子目录
USER_UPLOADS_DIR = "user_uploads"

VARIANTS = ("render", "shell")


def model_root() -> Path:
    """模型文件唯一根目录(绝对路径)。"""
    return settings.source_model_path


def relative_to_root(path: Path) -> str:
    """文件相对模型根的 POSIX 路径;越界时按 500 处理(与导入服务一致)。"""
    try:
        return path.resolve().relative_to(model_root().resolve()).as_posix()
    except ValueError as exc:
        raise AppError(
            "MODEL_PATH_OUTSIDE_ROOT",
            f"模型文件不在模型根目录 {model_root()} 之下: {path}",
            status_code=500,
        ) from exc


def public_url(relative_path: str) -> str:
    """相对模型根的路径 → 浏览器可访问的静态地址。"""
    return f"{PUBLIC_PREFIX}/{relative_path.lstrip('/')}"


def resolve_model_file(relative_path: str | None) -> Path | None:
    """相对模型根的路径 → 绝对路径;越界或文件不存在返回 None。"""
    if not relative_path:
        return None
    root = model_root().resolve()
    path = (root / relative_path).resolve()
    if path != root and root not in path.parents:
        return None
    return path if path.is_file() else None


def project_package_dir(project_id: str) -> Path:
    """上传建模项目的交付包目录(与锦界 ``web_package/`` 同构)。"""
    return model_root() / PROJECTS_DIR / project_id / "web_package"


def user_upload_dir(asset_id: str) -> Path:
    """单个模型资产的手动上传版本目录。"""
    return model_root() / USER_UPLOADS_DIR / asset_id


def ensure_model_dirs() -> None:
    """启动时补齐模型根下的固定子目录。"""
    for path in (model_root(), model_root() / PROJECTS_DIR, model_root() / USER_UPLOADS_DIR):
        path.mkdir(parents=True, exist_ok=True)


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


def _variant_urls(files: dict[str, Path]) -> tuple[dict[str, str | None], str | None]:
    """渲染轨必然存在(已在上游校验);分析轨存在时才写 shell_file。"""
    render_rel = relative_to_root(files["render"])
    shell_path = files.get("shell")
    shell_rel = (
        relative_to_root(shell_path)
        if shell_path is not None and shell_path.is_file()
        else None
    )
    variant_urls: dict[str, str | None] = {
        "render": public_url(render_rel),
        "shell": public_url(shell_rel) if shell_rel else None,
    }
    return variant_urls, shell_rel


def combined_variant_metadata(package_dir: Path) -> dict[str, Any]:
    """合并场景的双轨 metadata(前端“含内部壁 / 空心壳”两个加载按钮都靠它)。"""
    files = package_combined_variant_files(package_dir)
    variant_urls, shell_rel = _variant_urls(files)
    return {
        "render_file": relative_to_root(files["render"]),
        "shell_file": shell_rel,
        "variant_urls": variant_urls,
    }


def variant_metadata(
    package_dir: Path,
    code: str,
    layer: Mapping[str, Any],
) -> dict[str, Any]:
    """生成模型资产的双轨 metadata 片段(路径为相对模型根,URL 为静态地址)。

    只写入实际存在的文件:``shell_file`` 为 ``None`` 表示该包没有分析轨
    (旧包),前端/接口据此判断 ``variant=shell`` 不可用。
    """
    files = package_variant_files(package_dir, code)
    variant_urls, shell_rel = _variant_urls(files)

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
        rel = relative_to_root(lod_path)
        lod_files[name] = rel
        lod_urls[name] = public_url(rel)

    return {
        "render_file": relative_to_root(files["render"]),
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
    """把 variant 解析成相对模型根的文件路径;均为空返回 None。

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
