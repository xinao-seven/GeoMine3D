"""模型文件分发:内容指纹 URL、协商缓存(ETag/304)、Range(206)。

背景:``server/static/models/web_package`` 有 244MB,单文件 ``model_combined.glb``
超 20MB。交付包内容会随数据重跑而变,所以不能无脑长缓存(历史上出过“时而空心”
的缓存故障),但每次全量重下同样不可接受。策略是:

- 带内容指纹的静态地址(``?v=<hash8>``)→ ``immutable`` 长缓存;
- 不带指纹 → ``no-cache`` 回源校验 + 强 ETag(内容哈希)→ 304,只花几十字节;
- 大文件支持 Range 断点续传(Starlette FileResponse 自带)。
"""
from __future__ import annotations

import json
from pathlib import Path

import db_utils
import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionFactory
from app.main import app
from app.models.asset import ModelAsset, ModelVersion
from app.services.model_paths import (
    combined_variant_metadata,
    public_url,
    publish_package,
    variant_metadata,
)
from app.services.modeling_service import _register_models  # noqa: PLC2701 - 单测内部实现

CATALOG = {
    "origin_restore": {"display_recommendation": {"z_scale": 20}},
    "layers": [
        {
            "code": "L01",
            "name_cn": "测试煤层",
            "index": 1,
            "color_hex": "#123456",
            "bounds_local": {},
            "stats": {},
            "lods": [],
        }
    ],
}


@pytest.fixture(autouse=True)
def _isolated_model_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "models"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "source_model_dir", root)
    return root


@pytest.fixture
async def client():
    # app 在模块导入时(夹具 monkeypatch 之前)就已创建,/static/models 挂载指向真实模型根,
    # 与生产行为一致;因此这里不要在夹具里 import app。
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def _write_package(root: Path, marker: str = "A") -> tuple[Path, dict]:
    """造一个最小交付包(1 层 + 合并场景 + 壳 + LOD),返回 (目录, catalog)。"""
    package = root / "demo_package"
    (package / "shells").mkdir(parents=True, exist_ok=True)
    (package / "L01.glb").write_bytes(f"render-{marker}".encode() * 50)
    (package / "model_combined.glb").write_bytes(f"combined-{marker}".encode() * 50)
    (package / "model_combined_shell.glb").write_bytes(f"cshell-{marker}".encode())
    (package / "shells" / "L01_shell.glb").write_bytes(f"shell-{marker}".encode())
    (package / "catalog.json").write_text(json.dumps(CATALOG, ensure_ascii=False), encoding="utf-8")
    return package, CATALOG


class TestPublicUrlVersioning:
    def test_url_without_version_is_plain(self) -> None:
        assert public_url("a/b.glb") == "/static/models/a/b.glb"

    def test_url_with_version_carries_content_hash(self) -> None:
        assert public_url("a/b.glb", "deadbeef") == "/static/models/a/b.glb?v=deadbeef"

    def test_variant_metadata_embeds_version(self, _isolated_model_root: Path) -> None:
        package, catalog = _write_package(_isolated_model_root)
        meta = variant_metadata(package, "L01", catalog["layers"][0], version="abc12345")

        assert meta["variant_urls"]["render"].endswith("?v=abc12345")
        assert meta["variant_urls"]["shell"].endswith("?v=abc12345")
        assert "?" not in meta["render_file"], "库里存的路径不能带 query"

    def test_combined_metadata_embeds_version(self, _isolated_model_root: Path) -> None:
        package, _ = _write_package(_isolated_model_root)
        meta = combined_variant_metadata(package, version="abc12345")
        assert meta["variant_urls"]["render"].endswith("?v=abc12345")


class TestRegisteredMetadataHasVersion:
    async def test_register_models_writes_versioned_urls(self, _isolated_model_root: Path) -> None:
        await db_utils.open_or_skip()
        staging = _isolated_model_root / "projects" / "demo-project" / ".tmp-job"
        staging.mkdir(parents=True)
        (staging / "shells").mkdir()
        (staging / "L01.glb").write_bytes(b"render-A" * 100)
        (staging / "shells" / "L01_shell.glb").write_bytes(b"shell-A")
        (staging / "catalog.json").write_text(
            json.dumps(CATALOG, ensure_ascii=False), encoding="utf-8"
        )
        published = publish_package("demo-project", staging)
        url_version = published.content_hash[:8]

        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            try:
                await _register_models(
                    session, None, project, published.directory,
                    published.catalog, 20.0, published=published,
                )
                await session.commit()

                assets = (
                    await session.scalars(
                        select(ModelAsset).where(ModelAsset.project_id == project.id)
                    )
                ).all()
                assert len(assets) == 1
                metadata = assets[0].metadata_json
                assert metadata["variant_urls"]["render"].endswith(f"?v={url_version}")
                assert metadata["variant_urls"]["shell"].endswith(f"?v={url_version}")
                assert metadata["package_hash"] == published.content_hash
                assert metadata["package_dir"].endswith(published.content_hash[:16])
            finally:
                await db_utils.drop_project(project.id)


class TestStaticCacheHeaders:
    def _first_model_file(self) -> str | None:
        """在**真实**模型根下找一个可读的 GLB。

        注意:/static/models 的挂载是在 app import 时按当时的 settings 建立的,而其余
        用例把 settings.source_model_dir 指到了 tmp_path,所以这里要用仓库里的真实路径,
        不能用 settings(否则会误判为“文件不存在”而跳过)。
        """
        root = Path(__file__).resolve().parents[2] / "server" / "static" / "models"
        for candidate in ("web_package/model_combined.glb", "web_package/L01.glb"):
            if (root / candidate).is_file():
                return candidate
        return None

    async def test_versioned_url_is_immutable(self, client) -> None:
        relative = self._first_model_file()
        if relative is None:
            pytest.skip("测试环境缺少锦界交付包,跳过静态缓存头用例")

        response = await client.get(f"/static/models/{relative}?v=abc12345")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"

    async def test_unversioned_url_must_revalidate(self, client) -> None:
        relative = self._first_model_file()
        if relative is None:
            pytest.skip("测试环境缺少锦界交付包,跳过静态缓存头用例")

        response = await client.get(f"/static/models/{relative}")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache, must-revalidate"


class TestModelFileEndpoint:
    async def _create_asset(self) -> tuple[str, str]:
        """建一个指向临时模型根的资产,返回 (asset_id, project_id)。"""
        root = Path(settings.source_model_path)
        package, _ = _write_package(root)
        async with AsyncSessionFactory() as session:
            project = await db_utils.create_project(session)
            asset = ModelAsset(
                project_id=project.id,
                name="完整地层模型",
                model_type="stratum",
                status="ready",
                metadata_json={"catalog_code": "COMBINED"},
            )
            session.add(asset)
            await session.commit()
            version = ModelVersion(
                model_id=asset.id,
                version=1,
                file_path="demo_package/model_combined.glb",
                storage_scope="server_static",
                file_size=(package / "model_combined.glb").stat().st_size,
                content_hash="deadbeefdeadbeefdeadbeefdeadbeef",
                draco_compressed=False,
            )
            session.add(version)
            await session.commit()
            asset.current_version_id = version.id
            await session.commit()
            return asset.id, project.id

    async def test_response_is_revalidatable_not_long_cached(self, client) -> None:
        await db_utils.open_or_skip()
        asset_id, project_id = await self._create_asset()
        try:
            response = await client.get(f"/api/v1/models/{asset_id}/file")

            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-cache, must-revalidate"
            assert response.headers["etag"] == '"deadbeefdeadbeefdeadbeefdeadbeef"', (
                "ETag 用内容哈希,不受 mtime 抖动影响"
            )
            assert response.headers["accept-ranges"] == "bytes"
        finally:
            await db_utils.drop_project(project_id)

    async def test_if_none_match_returns_304(self, client) -> None:
        await db_utils.open_or_skip()
        asset_id, project_id = await self._create_asset()
        try:
            first = await client.get(f"/api/v1/models/{asset_id}/file")
            etag = first.headers["etag"]

            second = await client.get(
                f"/api/v1/models/{asset_id}/file", headers={"If-None-Match": etag}
            )

            assert second.status_code == 304
            assert second.content == b"", "304 不能带响应体,否则协商缓存就白做了"
            assert second.headers["etag"] == etag
        finally:
            await db_utils.drop_project(project_id)

    async def test_range_request_returns_206(self, client) -> None:
        await db_utils.open_or_skip()
        asset_id, project_id = await self._create_asset()
        try:
            response = await client.get(
                f"/api/v1/models/{asset_id}/file", headers={"Range": "bytes=0-99"}
            )

            assert response.status_code == 206
            assert response.headers["content-range"].startswith("bytes 0-99/")
            assert len(response.content) == 100
        finally:
            await db_utils.drop_project(project_id)
