import math

import trimesh

from app.services.section_service import LayerModelFile, compute_section


def _box_layer(tmp_path, code: str = "L01", color: str = "#123456") -> LayerModelFile:
    """生成 100×100×50 的闭合盒壳 GLB（局部坐标 0..100 / 0..100 / 0..50）。"""
    mesh = trimesh.creation.box(bounds=[[0, 0, 0], [100, 100, 50]])
    path = tmp_path / f"{code}.glb"
    mesh.export(str(path), file_type="glb")
    return LayerModelFile(code=code, name=f"测试层{code}", color=color, path=path)


def test_compute_section_cuts_closed_box(tmp_path) -> None:
    layer = _box_layer(tmp_path)
    # 原点 (1000, 2000, 500)：A 在盒内沿 x 方向，B 在盒外
    origin = {"x": 1000.0, "y": 2000.0, "z": 500.0}
    ax, ay = 1010.0, 2050.0
    bx, by = 1100.0, 2050.0

    result = compute_section([layer], ax, ay, bx, by, origin)

    assert result["length_m"] == 90
    assert result["z_range"] == [500.0, 550.0]
    assert len(result["layers"]) == 1
    data = result["layers"][0]
    assert data["code"] == "L01"
    assert data["loops"], "闭合盒被剖切面切中，应产出闭环"
    # 剖面为无限平面，交线覆盖整个盒子长度（s ∈ [-10, 90]）
    all_points = [pt for loop in data["loops"] for pt in loop]
    s_values = [pt[0] for pt in all_points]
    assert math.isclose(min(s_values), -10.0, abs_tol=0.5)
    assert math.isclose(max(s_values), 90.0, abs_tol=0.5)
    z_values = [pt[1] for pt in all_points]
    assert math.isclose(min(z_values), 500.0, abs_tol=0.5)
    assert math.isclose(max(z_values), 550.0, abs_tol=0.5)


def test_compute_section_skips_missing_files(tmp_path) -> None:
    layer = _box_layer(tmp_path)
    missing = LayerModelFile(code="L99", name="缺失层", color="#000000", path=tmp_path / "L99.glb")

    result = compute_section([layer, missing], 1010.0, 2050.0, 1100.0, 2050.0, {"x": 1000.0, "y": 2000.0, "z": 500.0})

    assert result["skipped"] == ["L99"]
    assert [item["code"] for item in result["layers"]] == ["L01"]


def test_compute_section_rejects_zero_length_line(tmp_path) -> None:
    layer = _box_layer(tmp_path)
    try:
        compute_section([layer], 1010.0, 2050.0, 1010.0, 2050.0, {"x": 1000.0, "y": 2000.0, "z": 500.0})
    except ValueError:
        return
    raise AssertionError("零长度剖面线应抛出 ValueError")
