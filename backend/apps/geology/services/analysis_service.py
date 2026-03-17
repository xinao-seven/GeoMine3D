from .borehole_excel_service import get_thickness_stats, get_depth_stats, get_layer_frequency
from .workingface_service import get_status_stats, get_workingface_list
from .model_service import get_model_list
import math  # noqa: F401  (reserved for future geometric calculations)


def get_thickness_distribution():
    stats = get_thickness_stats()
    return {
        'labels': [s['layerName'] for s in stats],
        'values': [s['avgThickness'] for s in stats],
        'counts': [s['count'] for s in stats],
    }


def get_borehole_depth_distribution():
    data = get_depth_stats()
    if not data:
        return {'labels': [], 'values': [], 'items': []}
    # 返回原始每个钻孔深度，前端可自行决定展示方式
    return {
        'items': data,
        'labels': [d['name'] for d in data],
        'values': [d['totalDepth'] for d in data],
    }


def get_workingface_status():
    stats = get_status_stats()
    return {
        'items': stats,
        'labels': [s['status'] for s in stats],
        'values': [s['count'] for s in stats],
    }


def get_borehole_count():
    from .borehole_excel_service import get_borehole_list
    boreholes = get_borehole_list()
    return {
        'total': len(boreholes),
        'items': boreholes,
    }


def get_layer_frequency_stats():
    freq = get_layer_frequency()
    return {
        'labels': [f['layerName'] for f in freq],
        'values': [f['count'] for f in freq],
    }


def get_borehole_xy_positions_raw():
    from .borehole_excel_service import get_borehole_raw_locations
    items = get_borehole_raw_locations()
    return {
        'items': items,
        'labels': [i['name'] for i in items],
        'xValues': [i['x'] for i in items],
        'yValues': [i['y'] for i in items],
    }


def get_dashboard_summary():
    from .borehole_excel_service import get_borehole_list
    models = get_model_list()
    boreholes = get_borehole_list()
    workingfaces = get_workingface_list()
    return {
        'modelCount': len(models),
        'boreholeCount': len(boreholes),
        'workingFaceCount': len(workingfaces),
        'stratumModelCount': len([m for m in models if m.get('type') == 'stratum']),
        'activeWorkingFaceCount': len([w for w in workingfaces if w.get('status') == '开采中']),
    }
