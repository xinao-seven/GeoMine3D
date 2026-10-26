"""钻孔 Excel 异步建模服务:上传 → 子进程建模引擎 → 数据注册。

链路:
1. create_job(): 保存上传 Excel 到 uploads/modeling-jobs/<job_id>/inputs/,
   创建独立 Project 与 pending 状态的 ModelingJob;
2. run_modeling_job(): 以子进程运行 backend/modeling_engine(与后端同一
   Python 环境,避免阻塞事件循环),stdout 逐行写入 engine.log 并节流刷新
   job.message 供前端轮询;
3. _register_results(): 按 engine 产出的 catalog.json 注册分层模型资产
   (storage_scope="upload", metadata source="modeling"),按层名映射注册
   钻孔与分层,origin_restore 写回 project。

建模任务串行执行(asyncio.Semaphore),失败时回滚注册事务并记录 error_message。
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_DIR, settings
from app.core.database import AsyncSessionFactory
from app.core.exceptions import AppError
from app.models.asset import ModelAsset, ModelVersion
from app.models.borehole import Borehole, BoreholeSegment
from app.models.modeling import ModelingJob
from app.models.project import Project
from app.models.workspace import ImportRun
from app.services.model_paths import combined_variant_metadata, variant_metadata
from app.services.server_import_service import file_sha256

# 建模引擎是 backend 顶层包;uvicorn 不一定以 backend 为工作目录启动,兜底注入 sys.path。
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

MODELING_SOURCE_TAG = "modeling"

_background_tasks: set[asyncio.Task] = set()
_job_semaphore: asyncio.Semaphore | None = None


def _semaphore() -> asyncio.Semaphore:
    global _job_semaphore
    if _job_semaphore is None:
        _job_semaphore = asyncio.Semaphore(max(1, settings.modeling_max_concurrent))
    return _job_semaphore


def job_input_dir(job_id: str) -> Path:
    return settings.upload_path / "modeling-jobs" / job_id


def project_output_dir(project_id: str) -> Path:
    return settings.upload_path / "projects" / project_id


def relative_to_upload(path: Path) -> str:
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
            output_dir=relative_to_upload(project_output_dir(project.id) / "web_package"),
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
    """在当前事件循环中启动后台建模任务,持有强引用防止被垃圾回收。"""
    task = asyncio.create_task(run_modeling_job(job_id), name=f"modeling-job-{job_id}")
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def run_modeling_job(job_id: str) -> None:
    async with _semaphore():
        async with AsyncSessionFactory() as session:
            job = await session.get(ModelingJob, job_id)
            if job is None or job.status != "pending":
                return
            project = await session.get(Project, job.project_id)
            if project is None:
                job.status = "failed"
                job.error_message = "任务所属项目不存在"
                await session.commit()
                return
            job.status = "running"
            job.stage = "解析输入"
            job.message = "解析钻孔数据"
            await session.commit()
            try:
                result = await _execute_engine(job, session)
                job.stage = "注册数据"
                job.message = "模型生成完成,写入数据库"
                await session.commit()
                summary = await _register_results(session, job, project, result)
                job.status = "completed"
                job.stage = "完成"
                job.message = "建模完成"
                job.result_json = {**result, "registered": summary}
                session.add(
                    ImportRun(
                        project_id=project.id,
                        source=f"modeling-engine job {job.id}",
                        status="completed",
                        summary_json=summary,
                    )
                )
                await session.commit()
            except Exception as exc:
                # 注册阶段可能已写入部分数据,回滚后只保留任务失败状态。
                await session.rollback()
                failed = await session.get(ModelingJob, job_id)
                if failed is not None:
                    failed.status = "failed"
                    failed.stage = "失败"
                    failed.error_message = _error_tail(exc, job_id)
                    await session.commit()


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


async def _execute_engine(job: ModelingJob, session: AsyncSession) -> dict[str, Any]:
    strata = settings.upload_path / job.input_strata_path
    location = settings.upload_path / job.input_location_path
    out_dir = settings.upload_path / job.output_dir
    job_dir = job_input_dir(job.id)
    log_path = job_dir / "engine.log"
    result_json = job_dir / "result.json"
    surfaces_npz = job_dir / "surfaces.npz"

    command = _engine_command(
        job, strata=strata, location=location, out_dir=out_dir,
        result_json=result_json, surfaces_npz=surfaces_npz,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as log_handle:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=BACKEND_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        last_commit = datetime.now(timezone.utc)

        async def _pump_stdout() -> None:
            nonlocal last_commit
            assert process.stdout is not None
            async for raw in process.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                log_handle.write(raw)
                log_handle.flush()
                if line.startswith("[modeling] "):
                    job.message = line[len("[modeling] "):]
                    job.stage = "建模中"
                    now = datetime.now(timezone.utc)
                    if (now - last_commit).total_seconds() >= 3.0:
                        last_commit = now
                        await session.commit()

        pump = asyncio.create_task(_pump_stdout())
        try:
            await asyncio.wait_for(process.wait(), timeout=settings.modeling_timeout_seconds)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise EngineFailure(
                f"建模引擎超时(>{settings.modeling_timeout_seconds}s),已终止"
            )
        finally:
            await pump

    if process.returncode != 0:
        tail = _log_tail(log_path)
        raise EngineFailure(f"建模引擎失败(退出码 {process.returncode}):\n{tail}")
    if not result_json.is_file():
        raise EngineFailure("建模引擎未产出结果文件 result.json")
    return json.loads(result_json.read_text(encoding="utf-8"))


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
    session: AsyncSession, job: ModelingJob, project: Project, result: dict[str, Any]
) -> dict[str, Any]:
    """按引擎产出注册:project 原点/比例、钻孔+分层(层名配色)、分层模型资产。"""
    package_dir = settings.upload_path / job.output_dir
    catalog = json.loads((package_dir / "catalog.json").read_text(encoding="utf-8"))
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

    strata = data_io.parse_strata(settings.upload_path / job.input_strata_path)
    locations = data_io.parse_locations(settings.upload_path / job.input_location_path)
    colors = _layer_colors(result)
    fallback = "#8d7358"
    layer_index = {
        str(layer["name_cn"]): int(layer_i)
        for layer_i, layer in enumerate(result.get("layers", []))
    }

    # 建模用的孔集合 = 分层表 ∩ 位置表(与引擎 build_model_inputs 的口径一致)。
    used_keys = set(strata.holes) & set(locations)
    colors = _layer_colors(result)
    fallback = "#8d7358"
    layer_index = {
        str(layer["name_cn"]): int(layer_i)
        for layer_i, layer in enumerate(result.get("layers", []))
    }

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

    asset_count = await _register_models(session, job, project, package_dir, catalog, vertical_scale)
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
) -> int:
    """公开入口:按建模交付包 catalog 注册模型资产(任务流程与重建脚本共用)。"""
    return await _register_models(session, job, project, package_dir, catalog, vertical_scale)


async def _register_models(
    session: AsyncSession,
    job: ModelingJob | None,
    project: Project,
    package_dir: Path,
    catalog: dict[str, Any],
    vertical_scale: float,
) -> int:
    """按 catalog 注册分层 GLB 与合并 GLB(与锦界导入 service 的元数据契约一致)。

    双轨产物:``source_file``=渲染轨(含内部棱柱壁),``shell_file``=分析轨(闭合壳)。
    ``job`` 可为 None(交付包重建脚本无任务上下文,仅在 metadata 中省略 job_id)。
    """
    existing_rows = await session.scalars(
        select(ModelAsset).where(
            ModelAsset.project_id == project.id,
        )
    )
    existing = {
        item.metadata_json.get("source_file"): item
        for item in existing_rows
        if (item.metadata_json or {}).get("source_file")
    }
    layers = catalog.get("layers") or []

    async def _assign_version(asset: ModelAsset, glb_path: Path, relative_path: str) -> None:
        version = await session.scalar(
            select(ModelVersion).where(
                ModelVersion.model_id == asset.id, ModelVersion.version == 1
            )
        )
        if version is None:
            version = ModelVersion(model_id=asset.id, version=1)
            session.add(version)
        version.file_path = relative_path
        version.storage_scope = "upload"
        version.file_size = glb_path.stat().st_size
        version.content_hash = file_sha256(glb_path)
        version.draco_compressed = False
        await session.flush()
        asset.current_version_id = version.id

    def _base_metadata(relative_path: str) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "source": MODELING_SOURCE_TAG,
            "source_file": relative_path,
            "format": "glb",
            "local_coordinates": True,
            "vertical_scale": vertical_scale,
        }
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
        relative_path = relative_to_upload(glb_path)
        asset = existing.get(relative_path)
        if asset is None:
            asset = ModelAsset(project_id=project.id)
            session.add(asset)
        asset.name = layer.get("name_cn") or code
        asset.model_type = "stratum"
        asset.status = "ready"
        # 双轨产物:渲染轨(含内部棱柱壁)+ 分析轨(闭合壳)。见 model_paths。
        variants = variant_metadata(settings.upload_path, "upload", package_dir, code, layer)
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
        relative_path = relative_to_upload(combined_path)
        asset = existing.get(relative_path)
        if asset is None:
            asset = ModelAsset(project_id=project.id)
            session.add(asset)
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
            **combined_variant_metadata(settings.upload_path, "upload", package_dir),
        }
        await session.flush()
        await _assign_version(asset, combined_path, relative_path)

    return len(layers) + 1


async def fail_stale_modeling_jobs() -> int:
    """服务启动时把中断的 pending/running 任务标记为失败。"""
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


def collect_project_files(project_id: str, job_ids: list[str]) -> list[Path]:
    """项目删除时需要一并清理的文件目录。"""
    dirs = [project_output_dir(project_id)]
    dirs.extend(job_input_dir(job_id) for job_id in job_ids)
    return dirs
