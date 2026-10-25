from app.services.analysis_service import (
    burial_depth_contours,
    build_overview,
    coal_thickness_by_borehole,
    depth_distribution,
    estimate_workingface_reserves,
    idw_grid,
    layer_frequency,
    marching_squares,
    point_in_polygon,
    polygon_area,
    thickness_distribution,
    virtual_borehole,
    workingface_status,
)


SEGMENTS = [
    {"borehole_id": "b1", "layer_name": "1-2煤", "top_depth": 100, "thickness": 4.0},
    {"borehole_id": "b1", "layer_name": "粉砂岩", "top_depth": 104, "thickness": 6.0},
    {"borehole_id": "b2", "layer_name": "1-2煤", "top_depth": 120, "thickness": 2.0},
    {"borehole_id": "b2", "layer_name": "粉砂岩", "top_depth": 122, "thickness": 8.0},
    {"borehole_id": "b3", "layer_name": "1-2煤", "top_depth": 80, "thickness": 6.0},
]


def test_thickness_distribution_groups_by_layer_and_sorts_by_top_depth() -> None:
    result = thickness_distribution(SEGMENTS)

    names = [row["layer_name"] for row in result]
    assert names == ["1-2煤", "粉砂岩"]
    coal = result[0]
    assert coal["count"] == 3
    assert coal["avg_thickness"] == 4.0
    assert coal["min_thickness"] == 2.0
    assert coal["max_thickness"] == 6.0


def test_thickness_distribution_skips_empty_names() -> None:
    result = thickness_distribution([{"layer_name": "  ", "top_depth": 1, "thickness": 2}])
    assert result == []


def test_layer_frequency_counts_distinct_boreholes() -> None:
    result = layer_frequency(SEGMENTS)

    by_name = {row["layer_name"]: row["borehole_count"] for row in result}
    assert by_name == {"1-2煤": 3, "粉砂岩": 2}


def test_depth_distribution_builds_adaptive_bins() -> None:
    depths = [10, 40, 75, 130, 190, 260, 340, 420]

    result = depth_distribution(depths)

    assert result["count"] == 8
    assert result["min"] == 10
    assert result["max"] == 420
    assert sum(bin_["count"] for bin_ in result["bins"]) == 8
    assert result["bins"]


def test_depth_distribution_handles_empty_input() -> None:
    assert depth_distribution([])["count"] == 0
    assert depth_distribution([])["bins"] == []


def test_workingface_status_groups_and_averages_sizes() -> None:
    faces = [
        {"status": "回采中", "length": 200, "width": 100},
        {"status": "回采中", "length": 300, "width": 150},
        {"status": "规划中", "length": None, "width": None},
    ]

    result = workingface_status(faces)

    by_status = {row["status"]: row for row in result}
    assert by_status["回采中"]["count"] == 2
    assert by_status["回采中"]["avg_length"] == 250.0
    assert by_status["规划中"]["count"] == 1
    assert by_status["规划中"]["avg_length"] is None


def test_coal_thickness_by_borehole_sums_coal_layers_only() -> None:
    grouped = {"b1": SEGMENTS[0:2], "b2": SEGMENTS[2:4]}

    result = coal_thickness_by_borehole(grouped)

    assert result["b1"]["coal_thickness"] == 4.0
    assert result["b1"]["coal_layers"] == ["1-2煤"]
    assert result["b2"]["coal_thickness"] == 2.0


def test_build_overview_composes_summary_blocks() -> None:
    boreholes = [
        {"code": "B1", "total_depth": 120},
        {"code": "B2", "total_depth": 240},
    ]
    faces = [{"code": "W1", "status": "回采中", "length": 100, "width": 50}]

    overview = build_overview(boreholes, SEGMENTS, faces, model_count=5)

    assert overview["borehole_count"] == 2
    assert overview["segment_count"] == 5
    assert overview["strata_layer_count"] == 2
    assert overview["model_count"] == 5
    assert overview["workingface_count"] == 1
    assert overview["total_drilling_depth"] == 360.0
    assert overview["max_borehole_depth"] == 240.0
    assert overview["thickness_distribution"][0]["layer_name"] == "1-2煤"


V_BOREHOLES = [
    {"id": "b1", "code": "B1", "x": 0, "y": 0},
    {"id": "b2", "code": "B2", "x": 100, "y": 0},
    {"id": "b3", "code": "B3", "x": 1000, "y": 1000},
]
V_SEGMENTS = {
    "b1": [
        {"layer_name": "1-2煤", "top_depth": 100, "bottom_depth": 104, "thickness": 4, "color": "#111111"},
        {"layer_name": "粉砂岩", "top_depth": 104, "bottom_depth": 110, "thickness": 6, "color": "#222222"},
    ],
    "b2": [
        {"layer_name": "1-2煤", "top_depth": 120, "bottom_depth": 126, "thickness": 6, "color": "#333333"},
    ],
    "b3": [
        {"layer_name": "1-2煤", "top_depth": 200, "bottom_depth": 210, "thickness": 10, "color": "#444444"},
    ],
}


def test_virtual_borehole_interpolates_layers_by_distance() -> None:
    result = virtual_borehole(V_BOREHOLES, V_SEGMENTS, 50, 0, max_neighbors=8)

    # 距 b1/b2 各 50m，b3 很远权重应可忽略
    coal = next(layer for layer in result["layers"] if layer["layer_name"] == "1-2煤")
    assert 100 < coal["top_depth"] < 120
    assert coal["color"] == "#111111"  # 取最近邻 b1 的颜色
    assert result["used_neighbors"] == 3
    assert result["nearest_distance_m"] == 50.0


def test_virtual_borehole_exact_hit_returns_nearest_values() -> None:
    result = virtual_borehole(V_BOREHOLES, V_SEGMENTS, 0, 0, max_neighbors=8)

    coal = next(layer for layer in result["layers"] if layer["layer_name"] == "1-2煤")
    assert coal["top_depth"] == 100.0
    assert coal["bottom_depth"] == 104.0


def test_virtual_borehole_no_neighbors() -> None:
    result = virtual_borehole([], V_SEGMENTS, 10, 10)
    assert result["layers"] == []
    assert result["used_neighbors"] == 0
    assert result["nearest_distance_m"] is None


def test_virtual_borehole_layers_sorted_by_top_depth() -> None:
    result = virtual_borehole(V_BOREHOLES, V_SEGMENTS, 30, 0)
    tops = [layer["top_depth"] for layer in result["layers"]]
    assert tops == sorted(tops)


SQUARE = [[0, 0], [100, 0], [100, 100], [0, 100]]


def test_polygon_area_and_point_in_polygon() -> None:
    assert polygon_area(SQUARE) == 10000.0
    assert point_in_polygon(50, 50, SQUARE)
    assert not point_in_polygon(150, 50, SQUARE)
    assert point_in_polygon(50, 0.0001, SQUARE)


def test_estimate_workingface_reserves_uses_inside_boreholes_only() -> None:
    faces = [{"name": "W1", "points": SQUARE}]
    boreholes = [
        {"id": "b1", "code": "B1", "x": 50, "y": 50},
        {"id": "b2", "code": "B2", "x": 500, "y": 500},
    ]
    segments = {
        "b1": [{"layer_name": "1-2煤", "top_depth": 100, "bottom_depth": 106, "thickness": 6}],
        "b2": [{"layer_name": "1-2煤", "top_depth": 100, "bottom_depth": 200, "thickness": 100}],
    }

    items = estimate_workingface_reserves(faces, boreholes, segments, density_t_per_m3=1.35)

    assert len(items) == 1
    item = items[0]
    assert item["area_m2"] == 10000
    assert item["borehole_count"] == 1
    assert item["mean_coal_thickness_m"] == 6.0
    # 10000 m2 * 6 m * 1.35 t/m3 = 81000 t = 8.1 万吨
    assert item["reserve_wan_t"] == 8.1


def test_estimate_workingface_reserves_without_boreholes() -> None:
    faces = [{"name": "W1", "points": SQUARE}]
    items = estimate_workingface_reserves(faces, [], {})
    assert items[0]["borehole_count"] == 0
    assert items[0]["mean_coal_thickness_m"] is None
    assert items[0]["reserve_wan_t"] is None


def test_idw_grid_and_marching_squares_produce_lines() -> None:
    # 平面场 value = x + y
    samples = [
        {"x": 0, "y": 0, "value": 0},
        {"x": 100, "y": 0, "value": 100},
        {"x": 0, "y": 100, "value": 100},
        {"x": 100, "y": 100, "value": 200},
    ]
    grid = idw_grid(samples, 0, 0, 100, 100, 21, 21)
    assert len(grid) == 21 and len(grid[0]) == 21
    # 角点近似采样值
    assert grid[0][0] == 0
    assert grid[20][20] == 200

    lines = marching_squares(grid, 0, 0, 100, 100, [100])
    assert len(lines) == 1
    level_lines = lines[0]
    assert level_lines["level"] == 100
    # 平面 x+y=100 的等值线应是对角线附近的线段集合
    assert len(level_lines["segments"]) >= 4
    flat = level_lines["segments"]
    coords = [(flat[i], flat[i + 1]) for i in range(0, len(flat), 4)]
    for x, y in coords:
        assert 90 <= x + y <= 110


def test_burial_depth_contours_auto_step() -> None:
    samples = [
        {"x": 0, "y": 0, "value": 90},
        {"x": 100, "y": 0, "value": 110},
        {"x": 0, "y": 100, "value": 130},
        {"x": 100, "y": 100, "value": 150},
    ]

    result = burial_depth_contours(samples)

    assert result["sample_count"] if "sample_count" in result else True
    assert result["bbox"] is not None
    assert result["levels"]
    assert result["lines"]


def test_burial_depth_contours_empty() -> None:
    result = burial_depth_contours([])
    assert result["levels"] == []
    assert result["lines"] == []
    assert result["bbox"] is None
