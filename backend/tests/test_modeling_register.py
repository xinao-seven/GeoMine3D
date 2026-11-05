"""注册阶段一致性:内容寻址发布(暂存区 → 不可变目录 → 原子切指针)与幂等注册。

覆盖三件事:
1. ``publish_package`` 幂等:同一份内容重复发布得到同一个目录名,暂存区被丢弃;
2. ``activate_package`` 用单文件 ``os.replace`` 切指针,``project_package_dir`` 跟随指针,
   指针缺失/损坏时回退历史 ``web_package`` 目录(兼容既有项目);
3. ``_register_models`` 幂等:identity 是 (project_id, catalog_code) 而不是文件路径,
   重复注册(重试)与换内容重建都不会多出资产行。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import delete, select, text

from app.core.config import settings
from app.core.database import AsyncSessionFactory, engine
from app.models.asset import ModelAsset
from app.models.project import Project
from app.services.model_paths import (
    activate_package,
    cleanup_staging,
    project_dir,
    project_package_dir,
    project_package_pointer,
    project_packages_dir,
    project_staging_dir,
    prune_packages,
    publish_package,
)
from app.services.modeling_service import _register_models  # noqa: PLC2701 - 单测验证内部实现

PROJECT_ID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture(autouse=True)
async def _dispose_engine_after_each_test() -> None:
    """pytest-asyncio 每个用例一个事件循环,连接池必须跟着清,否则下个用例拿到
    上一个已关闭 loop 上的连接(报 Event loop is closed)。"""
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
def _isolated_model_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把模型根指到 tmp_path,避免测试往真实 server/static/models 里写东西。"""
    monkeypatch.setattr(settings, "source_model_dir", tmp_path / "models")
    root = tmp_path / "models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _make_staging(project_id: str, job_id: str, *, marker: str = "A") -> Path:
    """造一个最小交付包暂存区(1 层 + 合并场景 + 壳 + LOD)。"""
    staging = project_staging_dir(project_id, job_id)
    (staging / "shells").mkdir(parents=True)
    (staging / "lods").mkdir(parents=True)
    (staging / "L01.glb").write_bytes(f"render-{marker}".encode())
    (staging / "model_combined.glb").write_bytes(f"combined-{marker}".encode())
    (staging / "model_combined_shell.glb").write_bytes(f"combined-shell-{marker}".encode())
    (staging / "shells" / "L01_shell.glb").write_bytes(f"shell-{marker}".encode())
    lod = staging / "lods" / "L01_lod50.glb"
    lod.write_bytes(f"lod-{marker}".encode())
    catalog = {
        "origin_restore": {
            "x_origin_m": 1000.0,
            "y_origin_m": 2000.0,
            "z_origin_m": 900.0,
            "display_recommendation": {"z_scale": 20},
        },
        "layers": [
            {
                "code": "L01",
                "name_cn": "测试煤层",
                "index": 1,
                "color_hex": "#123456",
                "bounds_local": {"min": [0, 0, 0], "max": [1, 1, 1]},
                "stats": {"triangles": 12},
                "lods": [{"name": "lod50", "path": str(lod)}],
            }
        ],
    }
    (staging / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False), encoding="utf-8"
    )
    return staging


def _publish(staging: Path) -> tuple[str, Path, dict]:
    published = publish_package(PROJECT_ID, staging)
    return published.content_hash, published.directory, published.catalog


class TestPublish:
    def test_publish_moves_staging_into_content_addressed_dir(self) -> None:
        staging = _make_staging(PROJECT_ID, "job-1")
        content_hash, directory, catalog = _publish(staging)

        assert not staging.exists(), "暂存区应被搬走,不能留在原地"
        assert directory.parent == project_packages_dir(PROJECT_ID)
        assert directory.name == content_hash[:16]
        assert (directory / "L01.glb").is_file()
        assert catalog["layers"][0]["code"] == "L01"

    def test_publish_is_idempotent_for_same_content(self) -> None:
        first_hash, first_dir, _ = _publish(_make_staging(PROJECT_ID, "job-1"))

        second = _make_staging(PROJECT_ID, "job-2")  # 同内容、不同 job
        second_hash, second_dir, _ = _publish(second)

        assert second_hash == first_hash, "同内容必须得到同一指纹(重试才能幂等)"
        assert second_dir == first_dir
        assert not second.exists(), "重复发布应丢弃暂存区"

    def test_different_content_yields_different_package(self) -> None:
        first_hash, _, _ = _publish(_make_staging(PROJECT_ID, "job-1", marker="A"))
        second_hash, _, _ = _publish(_make_staging(PROJECT_ID, "job-2", marker="B"))
        assert first_hash != second_hash


class TestActivateAndResolve:
    def test_pointer_switch_is_followed_by_project_package_dir(self) -> None:
        first_hash, _, _ = _publish(_make_staging(PROJECT_ID, "job-1", marker="A"))
        activate_package(PROJECT_ID, first_hash)
        assert project_package_dir(PROJECT_ID) == project_packages_dir(PROJECT_ID) / first_hash[:16]

        second_hash, _, _ = _publish(_make_staging(PROJECT_ID, "job-2", marker="B"))
        activate_package(PROJECT_ID, second_hash)
        assert project_package_dir(PROJECT_ID) == project_packages_dir(PROJECT_ID) / second_hash[:16]

        pointer = project_package_pointer(PROJECT_ID)
        payload = json.loads(pointer.read_text(encoding="utf-8"))
        assert payload["active"] == second_hash[:16]
        assert not pointer.with_name(pointer.name + ".tmp").exists(), "临时指针文件必须已被替换掉"

    def test_missing_pointer_falls_back_to_legacy_package_dir(self) -> None:
        legacy = project_dir(PROJECT_ID) / "web_package"
        legacy.mkdir(parents=True)
        assert project_package_dir(PROJECT_ID) == legacy

    def test_corrupted_pointer_falls_back_to_legacy_package_dir(self) -> None:
        legacy = project_dir(PROJECT_ID) / "web_package"
        legacy.mkdir(parents=True)
        project_package_pointer(PROJECT_ID).write_text("{not json", encoding="utf-8")
        assert project_package_dir(PROJECT_ID) == legacy

    def test_prune_keeps_only_active_package(self) -> None:
        keep_hash, keep_dir, _ = _publish(_make_staging(PROJECT_ID, "job-1", marker="A"))
        drop_hash, drop_dir, _ = _publish(_make_staging(PROJECT_ID, "job-2", marker="B"))
        activate_package(PROJECT_ID, keep_hash)

        removed = prune_packages(PROJECT_ID, keep_hash)

        assert removed == [drop_hash[:16]]
        assert keep_dir.is_dir()
        assert not drop_dir.exists()

    def test_cleanup_staging_removes_all_tmp_dirs(self) -> None:
        _make_staging(PROJECT_ID, "job-1")
        _make_staging(PROJECT_ID, "job-2")

        removed = cleanup_staging(PROJECT_ID)

        assert sorted(removed) == [".tmp-job-1", ".tmp-job-2"]
        assert cleanup_staging(PROJECT_ID) == []


# ---------------------------------------------------------------- 数据库幂等注册


async def _open_session_or_skip():
    """MySQL 不可用时跳过(本地没起 docker compose 也能跑纯文件系统用例)。"""
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - 任何连接问题都按"不可用"处理
        pytest.skip(f"MySQL 不可用,跳过数据库用例: {exc}")


async def _new_project(session) -> Project:
    project = Project(name="单测-注册幂等", coordinate_system="Gauss-Kruger")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _drop_project(project_id: str) -> None:
    """清掉测试项目。先解掉 model_assets ↔ model_versions 的循环引用再删。"""
    async with AsyncSessionFactory() as session:
        await session.execute(
            text(
                "UPDATE model_assets SET current_version_id = NULL WHERE project_id = :pid"
            ),
            {"pid": project_id},
        )
        await session.execute(delete(ModelAsset).where(ModelAsset.project_id == project_id))
        await session.execute(text("DELETE FROM projects WHERE id = :pid"), {"pid": project_id})
        await session.commit()


async def _asset_rows(session, project_id: str) -> list[ModelAsset]:
    rows = await session.scalars(
        select(ModelAsset).where(ModelAsset.project_id == project_id).order_by(ModelAsset.name)
    )
    return list(rows)


class TestRegisterIdempotency:
    async def test_registering_same_package_twice_keeps_asset_count(self) -> None:
        await _open_session_or_skip()
        published = publish_package(PROJECT_ID, _make_staging(PROJECT_ID, "job-1"))

        async with AsyncSessionFactory() as session:
            project = await _new_project(session)
            try:
                first = await _register_models(
                    session, None, project, published.directory,
                    published.catalog, 20.0, published=published,
                )
                await session.commit()
                second = await _register_models(
                    session, None, project, published.directory,
                    published.catalog, 20.0, published=published,
                )
                await session.commit()

                rows = await _asset_rows(session, project.id)
                assert first == second == 2, "1 层 + 合并场景 = 2 个资产"
                assert len(rows) == 2, "重复注册不能新增资产行"
                codes = sorted((row.metadata_json or {}).get("catalog_code") for row in rows)
                assert codes == ["COMBINED", "L01"]
                assert all(
                    (row.metadata_json or {}).get("package_hash") == published.content_hash
                    for row in rows
                )
            finally:
                await _drop_project(project.id)

    async def test_rebuild_with_new_content_reuses_asset_rows(self) -> None:
        await _open_session_or_skip()
        first = publish_package(PROJECT_ID, _make_staging(PROJECT_ID, "job-1", marker="A"))
        second = publish_package(PROJECT_ID, _make_staging(PROJECT_ID, "job-2", marker="B"))
        assert first.content_hash != second.content_hash

        async with AsyncSessionFactory() as session:
            project = await _new_project(session)
            try:
                await _register_models(
                    session, None, project, first.directory,
                    first.catalog, 20.0, published=first,
                )
                await session.commit()
                await _register_models(
                    session, None, project, second.directory,
                    second.catalog, 20.0, published=second,
                )
                await session.commit()

                rows = await _asset_rows(session, project.id)
                assert len(rows) == 2, "换内容重建应复用资产行,而不是再插一批"
                for row in rows:
                    metadata = row.metadata_json or {}
                    assert metadata["package_hash"] == second.content_hash
                    assert metadata["package_dir"].endswith(second.content_hash[:16])
                    assert second.content_hash[:16] in metadata["source_file"]
            finally:
                await _drop_project(project.id)
