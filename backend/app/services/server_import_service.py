from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.asset import ModelAsset, ModelVersion
from app.models.borehole import Borehole, BoreholeSegment
from app.models.project import Project
from app.models.workspace import ImportRun, WorkingFace


# 分层配色:与当前分层表(地层汇总14层.xlsx)的 14 个层位一一对应。
# 选取标准:相邻与任意两层在色相/明度上可区分(最小 RGB 距离 33、色相差 ≥ 25°),
# 且都亮于深色面板背景(亮度 ≥ 0.15),按层顶→层底顺序排列。
# 层序:风积砂层/土层/4-1旋回(泥岩·砂岩)/煤顶泥岩层/煤3-1/直接底层/下伏岩层
LAYER_COLORS = (
    "#e8d7a4",  # 风积砂层
    "#8f7a63",  # 土层
    "#9ab98f",  # 第4旋回泥岩层
    "#e6c878",  # 第4旋回砂岩层
    "#58a086",  # 第3旋回泥岩层
    "#cf8b4f",  # 第3旋回砂岩层
    "#8fb0d4",  # 第2旋回泥岩层
    "#a8ab63",  # 第2旋回砂岩层
    "#5484a8",  # 第1旋回泥岩层
    "#b4738a",  # 第1旋回砂岩层
    "#b0a08c",  # 煤顶泥岩层
    "#6a6a72",  # 煤3-1
    "#b7bcc2",  # 直接底层
    "#85878f",  # 下伏岩层
)
# 层数超过配色表时的中性兑底色
LAYER_COLOR_FALLBACK = "#8d7358"

# 钻孔分层表两列数值存在两种写法（表头都写作 深度/厚度，语义却不同）：
# - BOTTOM_THICKNESS：深度 = 层底深度，厚度 = 层厚（旧表 地层汇总.xlsx）
# - TOP_BOTTOM：      深度 = 层顶深度，厚度列实际存的是层底深度（地层汇总14层.xlsx）
STRATA_BOTTOM_THICKNESS = "bottom_thickness"
STRATA_TOP_BOTTOM = "top_bottom"


def normalize_match_key(value: Any) -> str:
    return "".join(char for char in str(value or "").strip().upper() if char.isalnum())


def canonical_code(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def as_float(value: Any, default: float = 0) -> float:
    if value in (None, ""):
        return default
    return float(value)


def rows_as_dicts(path: Path) -> list[dict[str, Any]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        headers = [str(value).strip() for value in next(rows)]
        return [dict(zip(headers, row, strict=False)) for row in rows if any(row)]
    finally:
        workbook.close()


def detect_strata_convention(rows: list[dict[str, Any]]) -> str:
    """推断分层表 (深度, 厚度) 两列的真实语义。

    判据：若每一行都满足 第二列 ≥ 第一列，则只有“顶深/底深”写法成立
    （层底不可能浅于层顶）；旧表把层厚放在第二列，普遍小于层底深度，会立即被排除。
    """
    pairs: list[tuple[float, float]] = []
    for row in rows:
        if not normalize_match_key(row.get("钻孔名称")):
            continue
        first, second = row.get("深度"), row.get("厚度")
        if first in (None, "") or second in (None, ""):
            continue
        pairs.append((as_float(first), as_float(second)))
    if pairs and all(second >= first for first, second in pairs):
        return STRATA_TOP_BOTTOM
    return STRATA_BOTTOM_THICKNESS


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ServerDataImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.data_root = settings.source_data_path
        self.model_root = settings.source_model_path
        self.location_path = self.data_root / settings.borehole_location_file
        self.strata_path = self.data_root / settings.borehole_strata_file
        self.model_catalog_path = settings.source_model_catalog_path

    async def run(self, project_name: str) -> dict[str, Any]:
        self._validate_sources()
        locations = self._read_locations()
        strata = self._read_strata()
        catalog = self._read_model_catalog()
        project = await self._upsert_project(project_name, locations, catalog)
        borehole_summary = await self._upsert_boreholes(project, locations, strata)
        model_count = await self._upsert_models(project, catalog)
        working_face_count = await self._upsert_working_faces(project)

        summary = {
            "project_id": project.id,
            **borehole_summary,
            "model_assets": model_count,
            "working_faces": working_face_count,
        }
        self.session.add(
            ImportRun(
                project_id=project.id,
                source=f"server/data + {self.strata_path.name} + web_package/catalog.json",
                status="completed",
                summary_json=summary,
            )
        )
        await self.session.commit()
        return summary

    def _validate_sources(self) -> None:
        required = (
            self.location_path,
            self.strata_path,
            self.data_root / "workingfaces.json",
            self.model_catalog_path,
        )
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise AppError("IMPORT_SOURCE_MISSING", f"数据源不存在: {', '.join(missing)}")

    def _read_locations(self) -> dict[str, dict[str, Any]]:
        path = self.location_path
        result: dict[str, dict[str, Any]] = {}
        for row in rows_as_dicts(path):
            key = normalize_match_key(row.get("name"))
            if not key:
                continue
            result[key] = {
                "code": canonical_code(row["name"]),
                "x": as_float(row.get("x")),
                "y": as_float(row.get("y")),
                "z": as_float(row.get("z")),
            }
        return result

    def _read_strata(self) -> dict[str, list[dict[str, Any]]]:
        """读取钻孔分层表，统一归一化成 层顶深度 / 层底深度 / 层厚。

        两种列语义都会按行首列是否满足“底深 ≥ 顶深”自动判别（见 detect_strata_convention），
        并按层顶深度排序、校验层厚非负，避免把两种写法的表混着算成负厚度。
        """
        path = self.strata_path
        rows = rows_as_dicts(path)
        convention = detect_strata_convention(rows)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            key = normalize_match_key(row.get("钻孔名称"))
            if not key:
                continue
            first = as_float(row.get("深度"))
            second = as_float(row.get("厚度"))
            if convention == STRATA_TOP_BOTTOM:
                top_depth, bottom_depth = first, second
            else:
                bottom_depth, top_depth = first, first - second
            grouped[key].append(
                {
                    "source_code": canonical_code(row.get("钻孔名称")),
                    "layer_name": str(row.get("地层名称") or "未命名地层").strip(),
                    "top_depth": top_depth,
                    "bottom_depth": bottom_depth,
                    "thickness": bottom_depth - top_depth,
                }
            )

        invalid = [
            (key, item)
            for key, segments in grouped.items()
            for item in segments
            if item["thickness"] < -1e-6
        ]
        if invalid:
            key, item = invalid[0]
            raise AppError(
                "IMPORT_SOURCE_INVALID",
                f"分层表存在负厚度行({path.name}, 钻孔 {key}, 地层 {item['layer_name']}): "
                "请确认列语义是 深度=层底+厚度=层厚, 还是 深度=层顶+厚度=层底",
            )

        for segments in grouped.values():
            # 按层顶深度稳定排序,保证 0 厚度夹层仍保持原始层序
            segments.sort(key=lambda item: item["top_depth"])
        return grouped

    def _read_model_catalog(self) -> dict[str, Any]:
        return json.loads(self.model_catalog_path.read_text(encoding="utf-8"))

    async def _upsert_project(
        self,
        project_name: str,
        locations: dict[str, dict[str, Any]],
        catalog: dict[str, Any],
    ) -> Project:
        project = await self.session.scalar(select(Project).where(Project.name == project_name))
        # 场景基准优先采用模型交付包的 origin_restore,保证钻孔与模型在同一坐标系原点上。
        restore = catalog.get("origin_restore") or {}
        if restore.get("x_origin_m") is not None:
            origin_x = float(restore["x_origin_m"])
            origin_y = float(restore["y_origin_m"])
            origin_z = float(restore["z_origin_m"])
        else:
            coordinates = list(locations.values())
            origin_x = sum(item["x"] for item in coordinates) / len(coordinates)
            origin_y = sum(item["y"] for item in coordinates) / len(coordinates)
            origin_z = sum(item["z"] for item in coordinates) / len(coordinates)
        z_scale = (
            restore.get("display_recommendation", {}).get("z_scale")
        )
        if project is None:
            project = Project(name=project_name)
            self.session.add(project)
        project.description = "由 server 目录地质模型与钻孔资料构建的三维地质工作区"
        project.coordinate_system = "Gauss-Kruger"
        project.origin_x = origin_x
        project.origin_y = origin_y
        project.origin_z = origin_z
        # 模型与钻孔统一按交付包建议比例做竖向夸张。
        project.vertical_scale = float(z_scale) if z_scale else 20
        await self.session.flush()
        return project

    async def _upsert_boreholes(
        self,
        project: Project,
        locations: dict[str, dict[str, Any]],
        strata: dict[str, list[dict[str, Any]]],
    ) -> dict[str, int]:
        existing_rows = await self.session.scalars(
            select(Borehole).where(Borehole.project_id == project.id)
        )
        existing = {normalize_match_key(item.code): item for item in existing_rows}
        segment_count = 0
        zero_thickness = 0

        # 只导入分层表里有的钻孔：只有坐标、没有分层的孔不进库也不显示。
        for key in sorted(strata):
            location = locations.get(key)
            segments = strata[key]
            code = location["code"] if location else segments[0]["source_code"]
            borehole = existing.get(key)
            if borehole is None:
                borehole = Borehole(project_id=project.id, code=code, name=code, x=0, y=0, z=0)
                self.session.add(borehole)
                await self.session.flush()
            borehole.code = code
            borehole.name = code
            borehole.x = location["x"] if location else 0
            borehole.y = location["y"] if location else 0
            borehole.z = location["z"] if location else 0
            borehole.total_depth = max((item["bottom_depth"] for item in segments), default=0)
            borehole.status = "active" if location else "missing_location"
            borehole.metadata_json = {
                "source": "server/data",
                "has_location": location is not None,
                "has_strata": bool(segments),
            }

            await self.session.execute(
                delete(BoreholeSegment).where(BoreholeSegment.borehole_id == borehole.id)
            )
            for sequence, item in enumerate(segments):
                zero_thickness += int(item["thickness"] == 0)
                self.session.add(
                    BoreholeSegment(
                        borehole_id=borehole.id,
                        layer_name=item["layer_name"],
                        lithology=item["layer_name"],
                        top_depth=item["top_depth"],
                        bottom_depth=item["bottom_depth"],
                        thickness=item["thickness"],
                        color=LAYER_COLORS[sequence] if sequence < len(LAYER_COLORS) else LAYER_COLOR_FALLBACK,
                        sequence=sequence,
                    )
                )
            segment_count += len(segments)

        # 清理历史上导进来、但已不在分层表中的钻孔(只动导入来源的数据,手工创建的孔保留)
        removed = 0
        for key, borehole in existing.items():
            if key in strata or (borehole.metadata_json or {}).get("source") != "server/data":
                continue
            await self.session.delete(borehole)
            removed += 1

        return {
            "boreholes": len(strata),
            "borehole_segments": segment_count,
            "zero_thickness_segments": zero_thickness,
            "skipped_location_only": len(set(locations) - set(strata)),
            "removed_stale_boreholes": removed,
        }

    async def _upsert_models(self, project: Project, catalog: dict[str, Any]) -> int:
        """按交付包 catalog.json 逐层注册模型资产,不在 catalog 中的旧资产一并清除。"""
        package_dir = self.model_catalog_path.parent
        package_name = package_dir.name
        restore = catalog.get("origin_restore") or {}
        vertical_scale = restore.get("display_recommendation", {}).get("z_scale")
        layers = catalog.get("layers") or []
        catalog_rel_paths: set[str] = set()

        existing_rows = await self.session.scalars(
            select(ModelAsset).where(ModelAsset.project_id == project.id)
        )
        existing = {
            item.metadata_json.get("source_file"): item
            for item in existing_rows
            if item.metadata_json.get("source_file")
        }

        for layer in layers:
            code = str(layer.get("code") or "").strip()
            if not code:
                continue
            glb_path = package_dir / f"{code}.glb"
            if not glb_path.is_file():
                raise AppError(
                    "IMPORT_SOURCE_MISSING",
                    f"catalog 中的模型文件不存在: {glb_path}",
                )
            relative_path = self._package_relative_path(glb_path)
            catalog_rel_paths.add(relative_path)

            asset = existing.get(relative_path)
            if asset is None:
                asset = ModelAsset(project_id=project.id, name=layer.get("name_cn") or code)
                self.session.add(asset)
            asset.name = layer.get("name_cn") or code
            asset.model_type = "stratum"
            asset.status = "ready"
            asset.metadata_json = {
                "source": package_name,
                "source_file": relative_path,
                "catalog_code": code,
                "layer_index": layer.get("index"),
                "color_hex": layer.get("color_hex"),
                "format": "glb",
                "bbox": layer.get("bounds_local"),
                "stats": layer.get("stats"),
                "lods": layer.get("lods") or [],
                "local_coordinates": True,
                "vertical_scale": vertical_scale,
            }
            await self.session.flush()
            await self._assign_asset_version(asset, glb_path, relative_path)

        combined_path = package_dir / "model_combined.glb"
        if combined_path.is_file():
            relative_path = self._package_relative_path(combined_path)
            catalog_rel_paths.add(relative_path)
            layer_colors = {
                str(layer.get("code")): layer.get("color_hex")
                for layer in layers
                if layer.get("code")
            }
            layer_names = {
                str(layer.get("code")): layer.get("name_cn")
                for layer in layers
                if layer.get("code")
            }
            asset = existing.get(relative_path)
            if asset is None:
                asset = ModelAsset(project_id=project.id, name="完整地层模型")
                self.session.add(asset)
            asset.name = "完整地层模型"
            asset.model_type = "stratum"
            asset.status = "ready"
            asset.metadata_json = {
                "source": package_name,
                "source_file": relative_path,
                "catalog_code": "COMBINED",
                "combined": True,
                "layer_colors": layer_colors,
                "layer_names": layer_names,
                "format": "glb",
                "local_coordinates": True,
                "vertical_scale": vertical_scale,
            }
            await self.session.flush()
            await self._assign_asset_version(asset, combined_path, relative_path)

        # 井巷工程模型(巷道 + 工作面),与地层同一局部坐标系,注册为独立可加载资源。
        workings = catalog.get("workings") or {}
        workings_specs = (
            ("roadways", "巷道模型", "roadway"),
            ("working_faces", "工作面模型", "working_face"),
        )
        for section, asset_name, model_type in workings_specs:
            info = workings.get(section) or {}
            file_name = str(info.get("file") or f"{section}.glb")
            glb_path = package_dir / file_name
            if not glb_path.is_file():
                raise AppError(
                    "IMPORT_SOURCE_MISSING",
                    f"catalog 中的模型文件不存在: {glb_path}",
                )
            relative_path = self._package_relative_path(glb_path)
            catalog_rel_paths.add(relative_path)

            asset = existing.get(relative_path)
            if asset is None:
                asset = ModelAsset(project_id=project.id, name=asset_name)
                self.session.add(asset)
            asset.name = asset_name
            asset.model_type = model_type
            asset.status = "ready"
            asset.metadata_json = {
                "source": package_name,
                "source_file": relative_path,
                "catalog_code": section.upper(),
                "format": "glb",
                "color_hex": info.get("default_color"),
                "local_coordinates": True,
                "vertical_scale": vertical_scale,
                "stats": info,
            }
            await self.session.flush()
            await self._assign_asset_version(asset, glb_path, relative_path)

        for source_file, asset in existing.items():
            if source_file not in catalog_rel_paths:
                await self.session.delete(asset)

        return len(catalog_rel_paths)

    def _package_relative_path(self, glb_path: Path) -> str:
        try:
            return glb_path.relative_to(self.model_root).as_posix()
        except ValueError as exc:
            raise AppError(
                "IMPORT_CATALOG_OUTSIDE_MODEL_ROOT",
                f"catalog 目录必须位于模型根目录 {self.model_root} 之下: {glb_path.parent}",
                status_code=500,
            ) from exc

    async def _assign_asset_version(
        self, asset: ModelAsset, glb_path: Path, relative_path: str
    ) -> None:
        version = await self.session.scalar(
            select(ModelVersion).where(
                ModelVersion.model_id == asset.id,
                ModelVersion.version == 1,
            )
        )
        if version is None:
            version = ModelVersion(model_id=asset.id, version=1)
            self.session.add(version)
        version.file_path = relative_path
        version.storage_scope = "server_static"
        version.file_size = glb_path.stat().st_size
        version.content_hash = file_sha256(glb_path)
        version.draco_compressed = False
        await self.session.flush()
        asset.current_version_id = version.id

    async def _upsert_working_faces(self, project: Project) -> int:
        rows = json.loads((self.data_root / "workingfaces.json").read_text(encoding="utf-8"))
        existing_rows = await self.session.scalars(
            select(WorkingFace).where(WorkingFace.project_id == project.id)
        )
        existing = {item.code: item for item in existing_rows}
        for row in rows:
            code = str(row["code"])
            item = existing.get(code)
            if item is None:
                item = WorkingFace(project_id=project.id, code=code, name=row["name"])
                self.session.add(item)
            item.name = row["name"]
            item.status = row.get("status") or "规划中"
            item.description = row.get("description")
            item.length = row.get("length")
            item.width = row.get("width")
            item.coal_seam = row.get("coalSeam")
            item.metadata_json = {"legacy_id": row.get("id"), "legacy_model_id": row.get("modelId")}
        return len(rows)
