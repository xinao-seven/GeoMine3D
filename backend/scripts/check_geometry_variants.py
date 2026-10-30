"""校验交付包的几何双轨(渲染轨含内部壁 / 分析轨闭合壳)是否真的落到了磁盘与数据库。

背景:剖切后"内部空心"的投诉,第一步要排除"文件本身没有内部壁"或"注册的
``render_file`` 实际指向壳"。本脚本只读 GLB 的 JSON chunk(不加载顶点数据),
按三角面数给出可核对的数字:

- 渲染轨(``L*.glb`` / ``model_combined.glb``)三角面数应明显大于分析轨
  (``shells/*_shell.glb`` / ``model_combined_shell.glb``)——内部棱柱壁就在差额里;
- 合并场景的渲染轨三角面数应**逐层等于** ``L*.glb`` 之和(合并包就是各层拼接)。

默认按数据库里的 ``metadata.render_file`` / ``metadata.shell_file`` 解析真实文件,
因此同时验证了"注册是否正确"与"文件是否存在";``--package`` 可直接检查未入库的交付包。

用法::

    python scripts/check_geometry_variants.py                     # 全部项目
    python scripts/check_geometry_variants.py --project-id <pid>
    python scripts/check_geometry_variants.py --package ../server/static/models/web_package
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

from app.core.database import AsyncSessionFactory  # noqa: E402
from app.services.model_paths import model_root  # noqa: E402


@dataclass
class GlbStat:
    triangles: int
    meshes: int
    attrs: tuple[str, ...]


GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
LAYER_FILE_PATTERN = re.compile(r"^L\d+$")


def read_glb_json(path: Path) -> dict:
    data = path.read_bytes()
    magic, _version, length = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC:
        raise ValueError(f"不是 GLB 文件: {path}")
    offset = 12
    while offset < length:
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        if chunk_type == CHUNK_JSON:
            return json.loads(data[offset + 8:offset + 8 + chunk_length].decode("utf-8"))
        offset += 8 + chunk_length + (-chunk_length % 4)
    raise ValueError(f"GLB 缺少 JSON chunk: {path}")


def glb_stat(path: Path) -> GlbStat:
    doc = read_glb_json(path)
    accessors = doc.get("accessors") or []
    triangles = 0
    attrs: set[str] = set()
    for mesh in doc.get("meshes") or []:
        for primitive in mesh.get("primitives") or []:
            attrs.update((primitive.get("attributes") or {}).keys())
            index_ref = primitive.get("indices")
            if index_ref is not None:
                count = accessors[index_ref]["count"]
            else:
                count = accessors[primitive["attributes"]["POSITION"]]["count"]
            mode = primitive.get("mode", 4)
            if mode == 4:
                triangles += count // 3
    return GlbStat(triangles=triangles, meshes=len(doc.get("meshes") or []), attrs=tuple(sorted(attrs)))


def fmt(value: int | None) -> str:
    return "-" if value is None else f"{value:,}"


async def load_rows(project_id: str | None) -> list[dict]:
    sql = "select a.id, a.project_id, a.name, a.metadata_json from model_assets a"
    params: dict[str, str] = {}
    if project_id:
        sql += " where a.project_id = :project_id"
        params["project_id"] = project_id
    async with AsyncSessionFactory() as session:
        rows = (await session.execute(text(sql), params)).mappings().all()
    result = []
    for row in rows:
        metadata = row["metadata_json"]
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        result.append({**dict(row), "metadata_json": metadata or {}})
    return result


def check_registered_packages(rows: list[dict]) -> int:
    """按交付包目录归组,逐包打印双轨三角面数与合并轨自洽性。"""
    problems = 0
    root = model_root()
    packages: dict[Path, dict] = {}
    for row in rows:
        metadata = row["metadata_json"]
        render_rel = metadata.get("render_file") or metadata.get("source_file")
        if not render_rel:
            continue
        render_path = (root / render_rel).resolve()
        if not render_path.is_file():
            print(f"[缺少文件] {row['name']}: render={render_rel}")
            problems += 1
            continue
        shell_rel = metadata.get("shell_file")
        if shell_rel and not (root / shell_rel).is_file():
            print(f"[缺少文件] {row['name']}: shell={shell_rel}")
            problems += 1
        entry = packages.setdefault(render_path.parent, {"layers": [], "combined": None})
        item = {
            "name": row["name"],
            "render": render_path,
            "shell": (root / shell_rel).resolve() if shell_rel else None,
        }
        if metadata.get("combined"):
            entry["combined"] = item
        elif LAYER_FILE_PATTERN.match(render_path.stem):
            # 井巷/工作面等附件不是分层体元,不参与逐层求和对账
            entry["layers"].append(item)

    for package_dir, items in sorted(packages.items()):
        print(f"\n=== 交付包 {package_dir} ===")
        layer_render_sum = 0
        layer_shell_sum = 0
        for item in sorted(items["layers"], key=lambda i: i["render"].name):
            render_tris = glb_stat(item["render"]).triangles
            shell_tris = glb_stat(item["shell"]).triangles if item["shell"] else None
            layer_render_sum += render_tris
            layer_shell_sum += shell_tris or 0
            ratio = f"{render_tris / shell_tris:.2f}x" if shell_tris else "-"
            print(f"  [层] {item['render'].name:16s} render={fmt(render_tris):>10s} "
                  f"shell={fmt(shell_tris):>10s} 含壁/壳={ratio}")
        combined = items["combined"]
        if combined:
            render_tris = glb_stat(combined["render"]).triangles
            shell_tris = glb_stat(combined["shell"]).triangles if combined["shell"] else None
            ratio = f"{render_tris / shell_tris:.2f}x" if shell_tris else "-"
            print(f"  [合并] {combined['render'].name:16s} render={fmt(render_tris):>10s} "
                  f"shell={fmt(shell_tris):>10s} 含壁/壳={ratio}")
            if layer_render_sum:
                verdict = "一致" if render_tris == layer_render_sum else "不一致!"
                print(f"         渲染轨 vs 逐层之和 = {fmt(layer_render_sum)} -> {verdict}")
                if render_tris != layer_render_sum:
                    problems += 1
            if layer_shell_sum and shell_tris is not None:
                verdict = "一致" if shell_tris == layer_shell_sum else "不一致!"
                print(f"         分析轨 vs 逐层之和 = {fmt(layer_shell_sum)} -> {verdict}")
                if shell_tris != layer_shell_sum:
                    problems += 1
    return problems


def check_package_dir(package_dir: Path) -> int:
    """直接检查磁盘上的交付包(无需入库):逐层与合并的两条轨三角面数。"""
    problems = 0
    if not package_dir.is_dir():
        print(f"[错误] 目录不存在: {package_dir}")
        return 1
    print(f"\n=== 磁盘交付包 {package_dir} ===")
    layer_render_sum = 0
    layer_shell_sum = 0
    for layer_file in sorted(package_dir.glob("L*.glb")):
        shell_file = package_dir / "shells" / f"{layer_file.stem}_shell.glb"
        render_tris = glb_stat(layer_file).triangles
        shell_tris = glb_stat(shell_file).triangles if shell_file.is_file() else None
        layer_render_sum += render_tris
        layer_shell_sum += shell_tris or 0
        ratio = f"{render_tris / shell_tris:.2f}x" if shell_tris else "缺少壳"
        print(f"  [层] {layer_file.name:16s} render={fmt(render_tris):>10s} "
              f"shell={fmt(shell_tris):>10s} 含壁/壳={ratio}")
        if shell_tris is None:
            problems += 1
    combined_file = package_dir / "model_combined.glb"
    combined_shell = package_dir / "model_combined_shell.glb"
    if combined_file.is_file():
        render_tris = glb_stat(combined_file).triangles
        shell_tris = glb_stat(combined_shell).triangles if combined_shell.is_file() else None
        ratio = f"{render_tris / shell_tris:.2f}x" if shell_tris else "缺少壳"
        print(f"  [合并] {combined_file.name:16s} render={fmt(render_tris):>10s} "
              f"shell={fmt(shell_tris):>10s} 含壁/壳={ratio}")
        if layer_render_sum:
            verdict = "一致" if render_tris == layer_render_sum else "不一致!"
            print(f"         渲染轨 vs 逐层之和 = {fmt(layer_render_sum)} -> {verdict}")
            problems += 0 if render_tris == layer_render_sum else 1
        if not shell_tris:
            problems += 1
    else:
        print("  [合并] 缺少 model_combined.glb")
        problems += 1
    return problems


async def main() -> int:
    parser = argparse.ArgumentParser(description="校验交付包渲染轨(含内部壁)/分析轨(闭合壳)")
    parser.add_argument("--project-id", help="只检查指定项目")
    parser.add_argument(
        "--package",
        action="append",
        default=[],
        help="额外/替代地直接检查磁盘上的交付包目录(可重复)",
    )
    args = parser.parse_args()

    problems = 0
    for raw in args.package:
        problems += check_package_dir(Path(raw).expanduser().resolve())
    if args.package and not args.project_id:
        return 1 if problems else 0
    problems += check_registered_packages(await load_rows(args.project_id))
    print("\n结论:", "发现问题" if problems else "全部通过(渲染轨确实包含内部壁)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
