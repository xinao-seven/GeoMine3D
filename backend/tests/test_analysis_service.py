from app.services.analysis_service import (
    build_overview,
    coal_thickness_by_borehole,
    depth_distribution,
    layer_frequency,
    thickness_distribution,
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
