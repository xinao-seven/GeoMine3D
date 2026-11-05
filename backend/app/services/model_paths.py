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

import hashlib
import json
import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.exceptions import AppError

# 模型根目录对外统一挂载点(与 app/main.py 的 mount 一致)
PUBLIC_PREFIX = "/static/models"
# 上传建模交付包的子目录
PROJECTS_DIR = "projects"
# 手动上传模型版本的子目录
USER_UPLOADS_DIR = "user_uploads"
# 交付包内容区(不可变,按内容指纹分子目录)与生效指针
PACKAGES_DIR = "packages"
ACTIVE_POINTER = "active.json"
# 历史交付包目录名:引入内容寻址之前引擎直接写到这里
LEGACY_PACKAGE_DIR = "web_package"
# 引擎输出先写到 projects/<pid>/.tmp-<job_id>/,校验后再搬进 packages/<hash>/
STAGING_PREFIX = ".tmp-"
# 参与内容指纹的产物(与注册进库、前端加载的集合一致)。
# z20/ 与 vtu/ 是锦界专属额外交付物、不注册进库,故不计入指纹。
HASHED_PATTERNS = ("*.glb", "shells/*.glb", "lods/*.glb")

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


def public_url(relative_path: str, version: str | None = None) -> str:
    """相对模型根的路径 → 浏览器可访问的静态地址。

    带 ``version`` 时追加 ``?v=<内容指纹前 8 位>``:内容一变 URL 就变,于是可以放心
    下发 ``Cache-Control: immutable``(见 app/main.py::NoCacheStaticFiles)——既根治了
    “交付包重建后浏览器还在用旧 GLB”这类历史故障,又不用每次全量重下 20MB+ 的合并模型。
    """
    url = f"{PUBLIC_PREFIX}/{relative_path.lstrip('/')}"
    return f"{url}?v={version}" if version else url


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
    """上传建模项目的**当前生效**交付包目录(与锦界 ``web_package/`` 同构)。

    引入内容寻址后目录结构变为::

        projects/<pid>/packages/<content_hash>/   # 不可变产物(每次建模一份)
        projects/<pid>/active.json                # 生效指针(单文件原子替换)
        projects/<pid>/web_package/               # 历史包(只读回退,新项目不再写)

    为什么用指针文件而不是 rename 目录:Windows/NTFS 下把非空目录 rename 成已存在的
    目录不是原子操作,而单个小于 1KB 文件的 ``os.replace`` 是原子的。产物目录本身
    不可变(换内容就换名字),所以“生效”只需原子地改一个指针。
    """
    pointer = project_package_pointer(project_id)
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    active = str(payload.get("active") or "").strip()
    if active:
        candidate = project_packages_dir(project_id) / active
        if candidate.is_dir():
            return candidate
    return project_legacy_package_dir(project_id)


def project_dir(project_id: str) -> Path:
    """单个建模项目的产物根目录(交付包 + 指针 + 临时区都在它下面)。"""
    return model_root() / PROJECTS_DIR / project_id


def project_packages_dir(project_id: str) -> Path:
    """不可变交付包的父目录。"""
    return project_dir(project_id) / PACKAGES_DIR


def project_package_pointer(project_id: str) -> Path:
    """生效指针文件(内容形如 ``{"active": "<content_hash>"}``)。"""
    return project_dir(project_id) / ACTIVE_POINTER


def project_legacy_package_dir(project_id: str) -> Path:
    """引入内容寻址之前的历史交付包目录(只读回退)。"""
    return project_dir(project_id) / LEGACY_PACKAGE_DIR


def project_staging_dir(project_id: str, job_id: str) -> Path:
    """建模引擎的输出暂存目录;校验通过后才会被搬进 ``packages/<hash>/``。"""
    return project_dir(project_id) / f"{STAGING_PREFIX}{job_id}"


@dataclass(slots=True)
class PublishedPackage:
    """一次发布的结果:内容指纹、不可变目录与逐文件哈希(注册时复用,不再重算)。"""

    content_hash: str
    directory: Path
    catalog: dict[str, Any]
    file_hashes: dict[str, str] = field(default_factory=dict)
    file_sizes: dict[str, int] = field(default_factory=dict)

    def relative(self, path: Path) -> str:
        """包内文件 → 相对包目录的 POSIX 路径(即 file_hashes 的键)。"""
        return path.resolve().relative_to(self.directory.resolve()).as_posix()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_package_hash(
    package_dir: Path,
) -> tuple[str, dict[str, str], dict[str, int]]:
    """算交付包内容指纹:逐文件 sha256 → 按相对路径排序后聚合。

    用**内容**而不是时间戳/大小做指纹,保证同一份输入重复建模得到同一个目录名,
    重试与重建才能幂等;参与指纹的产物集合见 ``HASHED_PATTERNS``。
    """
    entries: dict[str, tuple[str, int]] = {}
    for pattern in HASHED_PATTERNS:
        for path in sorted(package_dir.glob(pattern)):
            if not path.is_file():
                continue
            entries[path.relative_to(package_dir).as_posix()] = (
                _hash_file(path),
                path.stat().st_size,
            )
    if not entries:
        raise AppError(
            "MODEL_PACKAGE_EMPTY",
            f"交付包没有可识别的模型产物: {package_dir}",
            status_code=500,
        )
    digest = hashlib.sha256()
    for relative_path in sorted(entries):
        file_hash, size = entries[relative_path]
        digest.update(f"{relative_path}:{size}:{file_hash}\n".encode())
    return (
        digest.hexdigest(),
        {name: value[0] for name, value in entries.items()},
        {name: value[1] for name, value in entries.items()},
    )


def publish_package(project_id: str, staging_dir: Path) -> PublishedPackage:
    """把暂存区搬成不可变内容目录(幂等),**不**切换生效指针。

    调用方应在数据库注册那笔事务 commit 成功后再调 ``activate_package()``:
    “先让数据一致,再让产物可见”。同内容重复发布时目录已存在,直接丢弃暂存区。
    """
    if not staging_dir.is_dir():
        raise AppError(
            "MODEL_PACKAGE_MISSING",
            f"交付包暂存目录不存在: {staging_dir}",
            status_code=500,
        )
    content_hash, file_hashes, file_sizes = compute_package_hash(staging_dir)
    target = project_packages_dir(project_id) / content_hash[:16]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        # 同内容已发布过(重试/重建同一份数据):丢弃暂存区即可,目录保持不可变。
        shutil.rmtree(staging_dir, ignore_errors=True)
    else:
        # 目标是全新名字:rename 到不存在的路径是安全的;用 shutil.move 兼容跨卷
        # (upload 暂存区与模型根可能不在同一个盘)。
        shutil.move(str(staging_dir), str(target))
    catalog = json.loads((target / "catalog.json").read_text(encoding="utf-8"))
    return PublishedPackage(
        content_hash=content_hash,
        directory=target,
        catalog=catalog,
        file_hashes=file_hashes,
        file_sizes=file_sizes,
    )


def activate_package(project_id: str, content_hash: str) -> Path:
    """原子切换生效指针(单文件 ``os.replace``)。返回指针文件路径。"""
    pointer = project_package_pointer(project_id)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"active": content_hash[:16], "content_hash": content_hash},
        ensure_ascii=False,
        indent=2,
    )
    tmp = pointer.with_name(pointer.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, pointer)
    return pointer


def prune_packages(project_id: str, keep_hash: str) -> list[str]:
    """删除除生效包之外的旧内容目录(DB 提交后才调,避免删掉仍在被引用的包)。"""
    keep = keep_hash[:16]
    removed: list[str] = []
    root = project_packages_dir(project_id)
    if not root.is_dir():
        return removed
    for entry in root.iterdir():
        if not entry.is_dir() or entry.name == keep:
            continue
        shutil.rmtree(entry, ignore_errors=True)
        removed.append(entry.name)
    return removed


def cleanup_staging(project_id: str, job_id: str | None = None) -> list[str]:
    """清理暂存区:给定 job_id 只清那一个,否则清掉所有残留的 ``.tmp-*``。"""
    root = project_dir(project_id)
    if not root.is_dir():
        return []
    targets = (
        [project_staging_dir(project_id, job_id)]
        if job_id
        else [path for path in root.iterdir() if path.name.startswith(STAGING_PREFIX)]
    )
    removed: list[str] = []
    for path in targets:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            removed.append(path.name)
    return removed


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


def _variant_urls(
    files: dict[str, Path], version: str | None = None
) -> tuple[dict[str, str | None], str | None]:
    """渲染轨必然存在(已在上游校验);分析轨存在时才写 shell_file。"""
    render_rel = relative_to_root(files["render"])
    shell_path = files.get("shell")
    shell_rel = (
        relative_to_root(shell_path)
        if shell_path is not None and shell_path.is_file()
        else None
    )
    variant_urls: dict[str, str | None] = {
        "render": public_url(render_rel, version),
        "shell": public_url(shell_rel, version) if shell_rel else None,
    }
    return variant_urls, shell_rel


def combined_variant_metadata(
    package_dir: Path, version: str | None = None
) -> dict[str, Any]:
    """合并场景的双轨 metadata(前端“含内部壁 / 空心壳”两个加载按钮都靠它)。"""
    files = package_combined_variant_files(package_dir)
    variant_urls, shell_rel = _variant_urls(files, version)
    return {
        "render_file": relative_to_root(files["render"]),
        "shell_file": shell_rel,
        "variant_urls": variant_urls,
    }


def variant_metadata(
    package_dir: Path,
    code: str,
    layer: Mapping[str, Any],
    version: str | None = None,
) -> dict[str, Any]:
    """生成模型资产的双轨 metadata 片段(路径为相对模型根,URL 为静态地址)。

    只写入实际存在的文件:``shell_file`` 为 ``None`` 表示该包没有分析轨
    (旧包),前端/接口据此判断 ``variant=shell`` 不可用。
    """
    files = package_variant_files(package_dir, code)
    variant_urls, shell_rel = _variant_urls(files, version)

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
        lod_urls[name] = public_url(rel, version)

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
