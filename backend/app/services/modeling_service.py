"""钻孔 Excel 异步建模服务:上传 → 子进程建模引擎 → 数据注册。

链路:
1. create_job(): 保存上传 Excel 到 uploads/modeling-jobs/<job_id>/inputs/(相对
   upload_path),创建独立 Project 与 pending 状态的 ModelingJob;
2. run_modeling_job(): 以子进程运行 backend/modeling_engine(与后端同一
   Python 环境,避免阻塞事件循环),stdout 逐行写入 engine.log 并节流刷新
   job.message 供前端轮询;
3. 交付包发布(原子生效):引擎先写 ``projects/<pid>/.tmp-<job_id>/`` 暂存区,
   校验 catalog 后算内容指纹并搬进不可变的 ``projects/<pid>/packages/<hash>/``;
   **数据库注册事务 commit 成功之后**才原子切换 ``projects/<pid>/active.json``
   指针。这样“数据一致”与“产物可见”不会出现半成品中间态,重试与重建也幂等;
4. _register_results(): 按 catalog.json 注册分层模型资产(identity 为
   project_id + catalog_code,重复注册只更新版本指向),按层名映射注册钻孔与
   分层,origin_restore 写回 project。

建模任务串行执行(asyncio.Semaphore),失败时回滚注册事务、清理暂存区并记录
error_message。
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_DIR, settings
from app.core.database import AsyncSessionFactory
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.asset import ModelAsset, ModelVersion
from app.models.borehole import Borehole, BoreholeSegment
from app.models.modeling import ModelingJob
from app.models.project import Project
from app.models.workspace import ImportRun
from app.services.model_paths import (
    PublishedPackage,
    activate_package,
    cleanup_staging,
    combined_variant_metadata,
    project_dir,
    project_staging_dir,
    prune_packages,
    publish_package,
    relative_to_root,
    variant_metadata,
)
from app.services.modeling_progress import record_progress
from app.services.server_import_service import file_sha256

# 建模引擎是 backend 顶层包;uvicorn 不一定以 backend 为工作目录启动,兜底注入 sys.path。
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

MODELING_SOURCE_TAG = "modeling"

logger = get_logger("app.modeling")

_background_tasks: set[asyncio.Task] = set()
_job_semaphore: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _job_semaphore
    if _job_semaphore is None:
        _job_semaphore = asyncio.Semaphore(max(1, settings.modeling_max_concurrent))
    return _job_semaphore


def job_input_dir(job_id: str) -> Path:
    """任务输入/日志目录(Excel、engine.log),仍在 uploads 下,不属于模型资产。"""
    return settings.upload_path / "modeling-jobs" / job_id


def project_output_dir(project_id: str) -> Path:
    """项目产物根目录:projects/<project_id>/(含 packages/、active.json、暂存区)。"""
    return project_dir(project_id)


def relative_to_upload(path: Path) -> str:
    """任务输入文件的相对路径(相对 upload_path)。"""
    return path.resolve().relative_to(settings.upload_path.resolve()).as_posix()


async def save_upload(upload: UploadFile, target: Path) -> int:
    """流式落盘上传文件,限制扩展名与大小,返回字节数。"""
    name = (upload.filename or "").lower()
    if not name.endswith(".xlsx"):
        raise AppError(
            "MODELING_FILE_TYPE_INVALID",
            f"只支持 .xlsx 文件: {upload.filename}",
            status_code=415,
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    size = 0
    with target.open("wb") as handle:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                handle.close()
                target.unlink(missing_ok=True)
                raise AppError(
                    "MODELING_FILE_TOO_LARGE",
                    f"文件超过大小限制 {settings.max_upload_size_mb}MB: {upload.filename}",
                    status_code=413,
                )
            handle.write(chunk)
    if size == 0:
        target.unlink(missing_ok=True)
        raise AppError("MODELING_FILE_EMPTY", f"上传文件为空: {upload.filename}")
    return size


class ModelingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(
        self,
        *,
        name: str,
        description: str | None,
        strata_file: UploadFile,
        location_file: UploadFile,
        params: dict[str, Any],
    ) -> ModelingJob:
        project = Project(name=name.strip(), description=description, coordinate_system="Gauss-Kruger")
        self.session.add(project)
        await self.session.flush()

        job = ModelingJob(
            project_id=project.id,
            status="pending",
            stage="排队中",
            message="等待建模",
            params_json=params,
            input_strata_path="",
            input_location_path="",
            # output_dir 相对**模型根目录**(与 metadata.file_path 同一基准)
            output_dir=relative_to_root(project_output_dir(project.id)),
        )
        self.session.add(job)
        await self.session.flush()

        input_dir = job_input_dir(job.id) / "inputs"
        await save_upload(strata_file, input_dir / "strata.xlsx")
        await save_upload(location_file, input_dir / "location.xlsx")
        job.input_strata_path = relative_to_upload(input_dir / "strata.xlsx")
        job.input_location_path = relative_to_upload(input_dir / "location.xlsx")

        await self.session.commit()
        await self.session.refresh(job)
        return job


def spawn_modeling_job(job_id: str) -> None:
    """在**当前进程**里启动后台建模任务(Redis 不可用时的降级路径)。

    持有强引用防止任务被 GC。并发的串行化靠进程内 ``asyncio.Semaphore``;
    多 worker / 多机部署需要 Redis 队列(见 app/services/modeling_queue.py)。
    """
    task = asyncio.create_task(_run_with_semaphore(job_id), name=f"modeling-job-{job_id}")
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _run_with_semaphore(job_id: str) -> None:
    from app.core.metrics import record_job_result

    started = time.monotonic()
    async with _semaphore():
        outcome = await run_modeling_job(job_id)
    record_job_result(outcome.status, time.monotonic() - started)


async def dispatch_modeling_job(job_id: str) -> str:
    """投递建模任务,返回投递方式(``redis`` / ``inline``)。

    Redis 可用就丢进 Stream 交给 worker(可重试/可恢复/跨进程);不可用就退回
    进程内后台任务,保证“没起 Redis 也能用”。
    """
    from app.services.modeling_queue import enqueue_modeling_job

    if await enqueue_modeling_job(job_id):
        return "redis"
    spawn_modeling_job(job_id)
    return "inline"


@dataclass(slots=True)
class JobOutcome:
    """一次执行的结果。队列据此决定 ACK / 退避重试 / 进死信。"""

    status: str  # completed | failed | skipped
    error: str | None = None


async def run_modeling_job(job_id: str) -> JobOutcome:
    """执行一个已投递的建模任务(只碰数据库与磁盘,不负责重试策略)。"""
    async with AsyncSessionFactory() as session:
        job = await session.get(ModelingJob, job_id)
        if job is None:
            return JobOutcome("skipped", "任务不存在")
        if job.status not in ("pending", "running"):
            # 已完成 / 已判死的任务被重复投递时直接丢弃(幂等,不重复建模)
            return JobOutcome("skipped", f"任务已是 {job.status} 状态")
        project = await session.get(Project, job.project_id)
        if project is None:
            job.status = "failed"
            job.error_message = "任务所属项目不存在"
            await session.commit()
            return JobOutcome("failed", job.error_message)
        job.status = "running"
        job.stage = "解析输入"
        job.message = "解析钻孔数据"
        job.attempts = (job.attempts or 0) + 1
        job.last_heartbeat_at = datetime.now(UTC)
        await session.commit()
        try:
            result, published = await _execute_engine(job, session)
            job.stage = "注册数据"
            job.message = "模型生成完成,写入数据库"
            job.output_dir = relative_to_root(published.directory)
            job.result_json = {**result, "package_hash": published.content_hash}
            await session.commit()
            await record_progress(job.id, "注册数据", 95, "模型生成完成,写入数据库")
            # 注册全部写进一个事务(只 flush 不 commit),与“完成”状态一起落库。
            summary = await _register_results(session, job, project, result, published)
            job.status = "completed"
            job.stage = "完成"
            job.message = "建模完成"
            job.next_retry_at = None
            job.result_json = {
                **result,
                "package_hash": published.content_hash,
                "registered": summary,
            }
            session.add(
                ImportRun(
                    project_id=project.id,
                    source=f"modeling-engine job {job.id}",
                    status="completed",
                    summary_json=summary,
                )
            )
            await session.commit()
            await record_progress(job.id, "完成", 100, "建模完成")
            await asyncio.to_thread(activate_package, project.id, published.content_hash)
            removed = await asyncio.to_thread(
                prune_packages, project.id, published.content_hash
            )
            if removed:
                logger.info(
                    "建模任务 %s 生效 %s,回收旧交付包 %s",
                    job.id,
                    published.content_hash[:16],
                    ", ".join(removed),
                )
            return JobOutcome("completed")
        except Exception as exc:
            # 注册阶段可能已写入部分数据,回滚后只保留任务失败状态。
            await session.rollback()
            # 交付包若还停在暂存区就删掉,不留半成品(已发布的内容目录不可变,留着
            # 供同内容重试直接复用,由指针失效与 prune 控制回收)。
            await asyncio.to_thread(cleanup_staging, job.project_id, job.id)
            message = _error_tail(exc, job_id)
            failed = await session.get(ModelingJob, job_id)
            if failed is not None:
                failed.status = "failed"
                failed.stage = "失败"
                failed.error_message = message
                await session.commit()
            # 失败也要推一帧,否则前端进度条会停在半路。
            await record_progress(job_id, "失败", 100, message[:500])
            return JobOutcome("failed", message)


def _error_tail(exc: Exception, job_id: str) -> str:
    if isinstance(exc, EngineFailure):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"


class EngineFailure(RuntimeError):
    pass


def _engine_command(job: ModelingJob, *, strata: Path, location: Path, out_dir: Path,
                    result_json: Path, surfaces_npz: Path) -> list[str]:
    params = job.params_json or {}
    command = [
        sys.executable, "-m", "modeling_engine.generate",
        "--strata", str(strata),
        "--location", str(location),
        "--out", str(out_dir),
        "--result-json", str(result_json),
        "--save-surfaces", str(surfaces_npz),
        "--grid-spacing", str(float(params.get("grid_spacing_m", 100.0))),
        "--boundary-padding", str(float(params.get("boundary_padding_m", 200.0))),
        "--pinchout-threshold", str(float(params.get("pinchout_threshold_m", 0.5))),
        "--z-scale", str(float(params.get("z_scale", 20.0))),
    ]
    return command


async def _execute_engine(
    job: ModelingJob, session: AsyncSession
) -> tuple[dict[str, Any], PublishedPackage]:
    """跑建模子进程 → 发布不可变交付包。返回(引擎结果, 已发布的包)。

    引擎只往暂存区 ``projects/<pid>/.tmp-<job_id>/`` 写;校验 catalog/产物完整性后
    再算内容指纹并搬进 ``packages/<hash>/``。整个过程不切生效指针,因此“写了一半
    的包”永远不会被前端或分析接口看到。
    """
    strata = settings.upload_path / job.input_strata_path
    location = settings.upload_path / job.input_location_path
    if not job.project_id:
        raise EngineFailure("建模任务缺少所属项目")
    out_dir = project_staging_dir(job.project_id, job.id)
    job_dir = job_input_dir(job.id)
    log_path = job_dir / "engine.log"
    result_json = job_dir / "result.json"
    surfaces_npz = job_dir / "surfaces.npz"

    command = _engine_command(
        job, strata=strata, location=location, out_dir=out_dir,
        result_json=result_json, surfaces_npz=surfaces_npz,
    )
    # 上一次同任务失败可能留下同名暂存区,先清掉再让引擎重新写。
    await asyncio.to_thread(cleanup_staging, job.project_id, job.id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as log_handle:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=BACKEND_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        last_commit = datetime.now(UTC)

        async def _pump_stdout() -> None:
            nonlocal last_commit
            assert process.stdout is not None
            async for raw in process.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                log_handle.write(raw)
                log_handle.flush()
                if line.startswith("[progress] "):
                    # 引擎吐的结构化进度:写 Redis 快照 + 事件流,SSE 立即推给前端。
                    try:
                        payload = json.loads(line[len("[progress] "):])
                    except ValueError:
                        continue
                    await record_progress(
                        job.id,
                        str(payload.get("stage") or "建模中"),
                        float(payload.get("percent") or 0),
                        str(payload.get("message") or ""),
                    )
                    continue
                if line.startswith("[modeling] "):
                    job.message = line[len("[modeling] "):]
                    job.stage = "建模中"
                    now = datetime.now(UTC)
                    if (now - last_commit).total_seconds() >= 3.0:
                        last_commit = now
                        await session.commit()

        pump = asyncio.create_task(_pump_stdout())
        try:
            await asyncio.wait_for(process.wait(), timeout=settings.modeling_timeout_seconds)
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise EngineFailure(
                f"建模引擎超时(>{settings.modeling_timeout_seconds}s),已终止"
            ) from exc
        finally:
            await pump

    if process.returncode != 0:
        tail = _log_tail(log_path)
        raise EngineFailure(f"建模引擎失败(退出码 {process.returncode}):\n{tail}")
    if not result_json.is_file():
        raise EngineFailure("建模引擎未产出结果文件 result.json")
    result = json.loads(result_json.read_text(encoding="utf-8"))
    # 哈希/搬运是阻塞 IO(几十 MB),必须离开事件循环线程。
    published = await asyncio.to_thread(publish_package, job.project_id, out_dir)
    logger.info(
        "建模任务 %s 交付包已发布 %s(%d 个产物, %d 字节)",
        job.id,
        published.content_hash[:16],
        len(published.file_hashes),
        sum(published.file_sizes.values()),
    )
    return result, published


def _log_tail(log_path: Path, max_chars: int = 4000) -> str:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(无引擎日志)"
    return text[-max_chars:]


def _layer_colors(result: dict[str, Any]) -> dict[str, str]:
    return {
        str(layer["name_cn"]): str(layer["color_hex"])
        for layer in result.get("layers", [])
    }


async def _register_results(
    session: AsyncSession,
    job: ModelingJob,
    project: Project,
    result: dict[str, Any],
    published: PublishedPackage,
) -> dict[str, Any]:
    """按引擎产出注册:project 原点/比例、钻孔+分层(层名配色)、分层模型资产。"""
    package_dir = published.directory
    catalog = published.catalog
    restore = catalog.get("origin_restore") or {}
    vertical_scale = float(
        restore.get("display_recommendation", {}).get("z_scale") or 20
    )

    project.coordinate_system = "Gauss-Kruger"
    project.origin_x = float(restore.get("x_origin_m", 0))
    project.origin_y = float(restore.get("y_origin_m", 0))
    project.origin_z = float(restore.get("z_origin_m", 0))
    project.vertical_scale = vertical_scale
    await session.flush()

    from modeling_engine import data_io

    # 同步解析 Excel 与落盘哈希都是阻塞调用,不能在事件循环线程里跑
    # (否则 SSE 长连接/其他请求都会被卡住)。
    strata = await asyncio.to_thread(
        data_io.parse_strata, settings.upload_path / job.input_strata_path
    )
    locations = await asyncio.to_thread(
        data_io.parse_locations, settings.upload_path / job.input_location_path
    )
    colors = _layer_colors(result)
    fallback = "#8d7358"
    layer_index = {
        str(layer["name_cn"]): int(layer_i)
        for layer_i, layer in enumerate(result.get("layers", []))
    }

    # 建模用的孔集合 = 分层表 ∩ 位置表(与引擎 build_model_inputs 的口径一致)。
    used_keys = set(strata.holes) & set(locations)

    borehole_count = 0
    segment_count = 0
    for key in sorted(used_keys):
        hole = strata.holes[key]
        location = locations[key]
        borehole = (
            await session.scalars(
                select(Borehole).where(
                    Borehole.project_id == project.id, Borehole.code == hole.code
                )
            )
        ).first()
        if borehole is None:
            borehole = Borehole(project_id=project.id)
            session.add(borehole)
        borehole.code = hole.code
        borehole.name = hole.code
        borehole.x = location["x"]
        borehole.y = location["y"]
        borehole.z = location["z"]
        borehole.total_depth = max(
            (segment["bottom_depth"] for segment in hole.segments), default=0
        )
        borehole.status = "active"
        borehole.metadata_json = {
            "source": MODELING_SOURCE_TAG,
            "job_id": job.id,
            "has_location": True,
            "has_strata": True,
        }
        await session.flush()
        await session.execute(
            delete(BoreholeSegment).where(BoreholeSegment.borehole_id == borehole.id)
        )
        for sequence, segment in enumerate(hole.segments):
            session.add(
                BoreholeSegment(
                    borehole_id=borehole.id,
                    layer_name=segment["layer_name"],
                    lithology=segment["layer_name"],
                    top_depth=segment["top_depth"],
                    bottom_depth=segment["bottom_depth"],
                    thickness=segment["bottom_depth"] - segment["top_depth"],
                    color=colors.get(segment["layer_name"], fallback),
                    sequence=sequence,
                )
            )
        borehole_count += 1
        segment_count += len(hole.segments)
    await session.flush()

    asset_count = await _register_models(
        session, job, project, package_dir, catalog, vertical_scale, published=published
    )
    return {
        "boreholes": borehole_count,
        "borehole_segments": segment_count,
        "model_assets": asset_count,
        "skipped_boreholes": result.get("skipped_boreholes", []),
        "layers": len(result.get("layers", [])),
        "layer_order_source": "derived from uploaded strata table",
        "layer_index_reference": layer_index,
    }


async def register_models_from_catalog(
    session: AsyncSession,
    project: Project,
    package_dir: Path,
    catalog: dict[str, Any],
    vertical_scale: float,
    job: ModelingJob | None = None,
    published: PublishedPackage | None = None,
) -> int:
    """公开入口:按建模交付包 catalog 注册模型资产(任务流程与重建脚本共用)。"""
    return await _register_models(
        session, job, project, package_dir, catalog, vertical_scale, published=published
    )


async def _register_models(
    session: AsyncSession,
    job: ModelingJob | None,
    project: Project,
    package_dir: Path,
    catalog: dict[str, Any],
    vertical_scale: float,
    published: PublishedPackage | None = None,
) -> int:
    """按 catalog 注册分层 GLB 与合并 GLB(与锦界导入 service 的元数据契约一致)。

    双轨产物:``source_file``=渲染轨(含内部棱柱壁),``shell_file``=分析轨(闭合壳)。
    ``job`` 可为 None(交付包重建脚本无任务上下文,仅在 metadata 中省略 job_id)。

    **幂等**:资产 identity 是 ``(project_id, catalog_code)``,不是文件路径——内容寻址
    后每次重建的路径都会变,按路径匹配会越建越多。同一份输入重复注册(重试/重建)
    只会把版本指向同一份不可变产物,资产数量不变。
    """
    existing_rows = await session.scalars(
        select(ModelAsset).where(
            ModelAsset.project_id == project.id,
        )
    )
    existing: dict[str, ModelAsset] = {}
    for item in existing_rows:
        metadata = item.metadata_json or {}
        key = metadata.get("catalog_code") or metadata.get("source_file")
        if key:
            existing[str(key)] = item
    layers = catalog.get("layers") or []

    def _package_relative(path: Path) -> str | None:
        if published is None:
            return None
        try:
            return published.relative(path)
        except ValueError:
            return None

    async def _assign_version(asset: ModelAsset, glb_path: Path, relative_path: str) -> None:
        version = await session.scalar(
            select(ModelVersion).where(
                ModelVersion.model_id == asset.id, ModelVersion.version == 1
            )
        )
        if version is None:
            version = ModelVersion(model_id=asset.id, version=1)
            session.add(version)
        # 发布阶段已经算过逐文件哈希,直接复用;没有发布上下文时(重建脚本)回退现算。
        key = _package_relative(glb_path)
        if published is not None and key is not None and key in published.file_hashes:
            size = published.file_sizes[key]
            digest = published.file_hashes[key]
        else:
            size = await asyncio.to_thread(lambda: glb_path.stat().st_size)
            digest = await asyncio.to_thread(file_sha256, glb_path)
        version.file_path = relative_path
        version.storage_scope = "server_static"
        version.file_size = size
        version.content_hash = digest
        version.draco_compressed = False
        await session.flush()
        asset.current_version_id = version.id

    # 内容指纹前 8 位作为静态资源版本号:前端据此拿到 immutable 缓存,内容一变 URL 就变。
    url_version = published.content_hash[:8] if published is not None else None

    def _base_metadata(relative_path: str) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "source": MODELING_SOURCE_TAG,
            "source_file": relative_path,
            "format": "glb",
            "local_coordinates": True,
            "vertical_scale": vertical_scale,
        }
        if published is not None:
            # 分析结果缓存/前端加载都以包指纹为准:内容一变指纹就变,缓存自然失效。
            meta["package_hash"] = published.content_hash
            meta["package_dir"] = relative_to_root(published.directory)
        if job is not None:
            meta["job_id"] = job.id
        return meta

    for layer in layers:
        code = str(layer.get("code") or "").strip()
        if not code:
            continue
        glb_path = package_dir / f"{code}.glb"
        if not glb_path.is_file():
            raise EngineFailure(f"catalog 中的模型文件不存在: {glb_path}")
        relative_path = relative_to_root(glb_path)
        asset = existing.get(code)
        if asset is None:
            asset = ModelAsset(project_id=project.id)
            session.add(asset)
            existing[code] = asset
        asset.name = layer.get("name_cn") or code
        asset.model_type = "stratum"
        asset.status = "ready"
        # 双轨产物:渲染轨(含内部棱柱壁)+ 分析轨(闭合壳)。见 model_paths。
        variants = variant_metadata(package_dir, code, layer, version=url_version)
        asset.metadata_json = {
            **_base_metadata(relative_path),
            "catalog_code": code,
            "layer_index": layer.get("index"),
            "color_hex": layer.get("color_hex"),
            "bbox": layer.get("bounds_local"),
            "stats": layer.get("stats"),
            "lods": layer.get("lods") or [],
            **variants,
        }
        await session.flush()
        await _assign_version(asset, glb_path, relative_path)

    combined_path = package_dir / "model_combined.glb"
    if combined_path.is_file():
        relative_path = relative_to_root(combined_path)
        asset = existing.get("COMBINED")
        if asset is None:
            asset = ModelAsset(project_id=project.id)
            session.add(asset)
            existing["COMBINED"] = asset
        asset.name = "完整地层模型"
        asset.model_type = "stratum"
        asset.status = "ready"
        asset.metadata_json = {
            **_base_metadata(relative_path),
            "catalog_code": "COMBINED",
            "combined": True,
            "layer_colors": {
                str(layer.get("code")): layer.get("color_hex")
                for layer in layers
                if layer.get("code")
            },
            "layer_names": {
                str(layer.get("code")): layer.get("name_cn")
                for layer in layers
                if layer.get("code")
            },
            # 合并场景也有双轨:model_combined.glb(含壁) / model_combined_shell.glb(壳)
            **combined_variant_metadata(package_dir, version=url_version),
        }
        await session.flush()
        await _assign_version(asset, combined_path, relative_path)

    return len(layers) + 1


async def fail_stale_modeling_jobs() -> int:
    """降级路径:没有 Redis 时,启动阶段只能把中断的任务标记为失败。

    Redis 可用时改用 ``recoverable_modeling_jobs()`` + 队列重投(见 main.py),
    那样重启不会丢掉任何已提交的任务。
    """
    async with AsyncSessionFactory() as session:
        jobs = await session.scalars(
            select(ModelingJob).where(ModelingJob.status.in_(("pending", "running")))
        )
        count = 0
        for job in jobs:
            job.status = "failed"
            job.stage = "失败"
            job.error_message = "服务重启导致任务中断,请重新上传"
            count += 1
        if count:
            await session.commit()
        return count


def _as_utc(value: datetime | None) -> datetime | None:
    """MySQL 的 DATETIME 不存时区,读回来是 naive 值;统一按 UTC 对齐后再比较。"""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def recoverable_modeling_jobs(
    heartbeat_ttl_seconds: int,
) -> list[tuple[str, int]]:
    """列出“应恢复”的任务:idle 在 pending/running 且心跳未刷新的。

    心跳 TTL 是判定“有人真在跑”的唯一依据:worker 活着就会定期刷新
    ``last_heartbeat_at``;进程崩了/机器重启后,超过 TTL 未刷新的 running 任务
    就是僵死任务,应当重新入队而不是直接判死。

    返回 ``(job_id, attempts)``,调用方据此决定重投还是进死信。
    """
    deadline = datetime.now(UTC) - timedelta(seconds=heartbeat_ttl_seconds)
    async with AsyncSessionFactory() as session:
        jobs = await session.scalars(
            select(ModelingJob).where(ModelingJob.status.in_(("pending", "running")))
        )
        rows: list[tuple[str, int]] = []
        for job in jobs:
            heartbeat = _as_utc(job.last_heartbeat_at)
            if heartbeat is not None and heartbeat > deadline:
                continue  # 心跳还新,说明有 worker 在跑,别抢
            rows.append((job.id, int(job.attempts or 0)))
        return rows


async def set_job_heartbeat(job_id: str, when: datetime | None = None) -> None:
    """刷新任务的 DB 心跳(存活凭证;Redis 里的租约见 modeling_queue)。"""
    async with AsyncSessionFactory() as session:
        job = await session.get(ModelingJob, job_id)
        if job is None:
            return
        job.last_heartbeat_at = when or datetime.now(UTC)
        await session.commit()


async def prepare_retry(job_id: str, error: str | None, delay_seconds: float) -> int | None:
    """把失败任务重新置为 pending 并记录下次可见时间;返回 attempts。

    返回 ``None`` 表示任务已不存在,无需重试。
    """
    async with AsyncSessionFactory() as session:
        job = await session.get(ModelingJob, job_id)
        if job is None:
            return None
        job.status = "pending"
        job.stage = "排队中"
        job.message = f"第 {job.attempts} 次尝试失败,{delay_seconds:.0f}s 后重试"
        job.error_message = error
        job.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        await session.commit()
        return int(job.attempts or 0)


async def mark_job_dead(job_id: str, error: str | None) -> None:
    """超过最大重试次数:任务保持 failed,并写明已放弃的原因。"""
    async with AsyncSessionFactory() as session:
        job = await session.get(ModelingJob, job_id)
        if job is None:
            return
        job.status = "failed"
        job.stage = "失败"
        job.error_message = f"已重试 {job.attempts} 次仍失败,任务放弃:{error or '未知错误'}"
        job.next_retry_at = None
        await session.commit()


def collect_project_files(project_id: str, job_ids: list[str]) -> list[Path]:
    """项目删除时需要一并清理的目录(交付包 + 指针 + 暂存区 + 任务输入/日志)。

    交付包现在按内容分目录(``packages/<hash>/``),删项目要连整个 ``projects/<pid>``
    一起清,否则旧内容目录会泄漏在模型根下。
    """
    dirs = [project_dir(project_id)]
    dirs.extend(job_input_dir(job_id) for job_id in job_ids)
    return dirs
