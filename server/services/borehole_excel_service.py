import pandas as pd
from pathlib import Path
from pyproj import CRS, Transformer

from config import DATA_DIR

_BOREHOLES_DIR = DATA_DIR / 'boreholes'
_LOCATION_FILE = DATA_DIR / 'location' / '钻孔位置.xlsx'
_MINE_AREA_PRJ = DATA_DIR / 'shp' / '锦界矿边界.prj'
_DEFAULT_SOURCE_CRS = 'EPSG:2421'
_TARGET_CRS = 'EPSG:4326'

_FIELD_MAP = {
    'borehole_name': '钻孔名称',
    'layer_name':    '地层名称',
    'depth':         '深度',
    'thickness':     '厚度',
}


def _build_borehole_transformer():
    source_crs = CRS.from_string(_DEFAULT_SOURCE_CRS)
    if _MINE_AREA_PRJ.exists():
        try:
            prj_text = _MINE_AREA_PRJ.read_text(encoding='utf-8', errors='ignore').strip()
            if prj_text:
                source_crs = CRS.from_wkt(prj_text)
        except Exception:
            pass
    return Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)


_WGS84_TRANSFORMER = _build_borehole_transformer()


def _is_lonlat(lon, lat):
    return -180 <= lon <= 180 and -90 <= lat <= 90


def _convert_point_to_wgs84(x, y):
    if _is_lonlat(x, y):
        return x, y
    lon, lat = _WGS84_TRANSFORMER.transform(x, y)
    if _is_lonlat(lon, lat):
        return lon, lat
    lon2, lat2 = _WGS84_TRANSFORMER.transform(y, x)
    if _is_lonlat(lon2, lat2):
        return lon2, lat2
    return None


def _normalize_name(name):
    if not name:
        return ''
    return ''.join(ch for ch in str(name).strip().upper() if ch.isalnum())


# ---------------------------------------------------------------------------
# Location data
# ---------------------------------------------------------------------------

def _load_location_index():
    if not _LOCATION_FILE.exists():
        print(f'[borehole] 位置文件不存在: {_LOCATION_FILE}')
        return {}
    try:
        df = pd.read_excel(_LOCATION_FILE, engine='openpyxl')
    except Exception as e:
        print(f'[borehole] 位置文件读取失败: {e}')
        return {}

    required = {'name', 'x', 'y', 'z'}
    missing = required - set(df.columns)
    if missing:
        print(f'[borehole] 位置文件缺少列: {missing}，实际: {list(df.columns)}')
        return {}

    index = {}
    for _, row in df.iterrows():
        name = str(row['name']).strip()
        if not name or name == 'nan':
            continue
        try:
            index[name] = {'x': float(row['x']), 'y': float(row['y']), 'z': float(row['z'])}
        except (ValueError, TypeError):
            continue
    return index


def _build_location_match_index(loc_index):
    normalized = {}
    for name, geo in loc_index.items():
        n = _normalize_name(name)
        if n and n not in normalized:
            normalized[n] = geo
    return normalized


# ---------------------------------------------------------------------------
# Excel data loading
# ---------------------------------------------------------------------------

def _discover_excel_files():
    if not _BOREHOLES_DIR.exists():
        return []
    all_xlsx = sorted(_BOREHOLES_DIR.glob('*.xlsx'))
    sample = _BOREHOLES_DIR / 'boreholes.xlsx'
    user_files = [f for f in all_xlsx if f != sample]
    fallback = [sample] if sample.exists() else []
    return user_files if user_files else fallback


def _parse_single_excel(file_path):
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
    except Exception as e:
        print(f'[borehole] 跳过 {file_path.name}: {e}')
        return {}

    reverse_map = {v: k for k, v in _FIELD_MAP.items()}
    df = df.rename(columns=reverse_map)

    required = list(_FIELD_MAP.keys())
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f'[borehole] 跳过 {file_path.name}: 缺少列 {[_FIELD_MAP[c] for c in missing]}')
        return {}

    boreholes = {}
    for _, row in df.iterrows():
        name = str(row['borehole_name']).strip()
        if not name or name == 'nan':
            continue
        if name not in boreholes:
            boreholes[name] = {'name': name, 'layers': []}
        try:
            bottom_depth = float(row['depth'])
            thickness = float(row['thickness'])
        except (ValueError, TypeError):
            continue
        top_depth = round(bottom_depth - thickness, 4)
        boreholes[name]['layers'].append({
            'layerName':   str(row['layer_name']).strip(),
            'topDepth':    top_depth,
            'thickness':   thickness,
            'bottomDepth': bottom_depth,
        })
    return boreholes


def _load_excel():
    files = _discover_excel_files()
    if not files:
        return []

    merged = {}
    for f in files:
        merged.update(_parse_single_excel(f))

    loc_raw = _load_location_index()
    loc_normalized = _build_location_match_index(loc_raw)

    result = []
    for idx, (name, data) in enumerate(merged.items()):
        layers = data['layers']
        total_depth = max((l['bottomDepth'] for l in layers), default=0)
        bh = {
            'id': str(idx + 1),
            'name': name,
            'totalDepth': total_depth,
            'layerCount': len(layers),
            'layers': layers,
        }
        raw_loc = loc_raw.get(name) or loc_normalized.get(_normalize_name(name))
        if raw_loc:
            bh['location'] = {
                'x': round(raw_loc['x'], 3),
                'y': round(raw_loc['y'], 3),
                'z': round(raw_loc['z'], 3),
            }
        result.append(bh)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_borehole_list(keyword=None, min_depth=None, max_depth=None):
    boreholes = _load_excel()
    if keyword:
        kw = keyword.lower()
        boreholes = [b for b in boreholes if kw in b['name'].lower()]
    if min_depth is not None:
        boreholes = [b for b in boreholes if b['totalDepth'] >= float(min_depth)]
    if max_depth is not None:
        boreholes = [b for b in boreholes if b['totalDepth'] <= float(max_depth)]
    return [
        {
            'id': b['id'], 'name': b['name'],
            'totalDepth': b['totalDepth'], 'layerCount': b['layerCount'],
            'location': b.get('location'),
        }
        for b in boreholes
    ]


def get_borehole_detail(borehole_id):
    for b in _load_excel():
        if str(b['id']) == str(borehole_id):
            return b
    return None


def search_boreholes(keyword):
    return get_borehole_list(keyword=keyword)


def get_thickness_stats():
    boreholes = _load_excel()
    layer_thickness = {}
    for b in boreholes:
        for l in b['layers']:
            name = l['layerName']
            layer_thickness.setdefault(name, []).append(l['thickness'])
    return [
        {'layerName': k, 'avgThickness': round(sum(v) / len(v), 2), 'count': len(v)}
        for k, v in layer_thickness.items()
    ]


def get_depth_stats():
    return [{'name': b['name'], 'totalDepth': b['totalDepth']} for b in _load_excel()]


def get_layer_frequency():
    boreholes = _load_excel()
    freq = {}
    for b in boreholes:
        for l in b['layers']:
            if l.get('thickness', 0) <= 0:
                continue
            freq[l['layerName']] = freq.get(l['layerName'], 0) + 1
    return [
        {'layerName': k, 'count': v}
        for k, v in sorted(freq.items(), key=lambda x: -x[1])
    ]


def get_borehole_raw_locations():
    raw = _load_location_index()
    return [
        {'id': str(i + 1), 'name': name, 'x': v['x'], 'y': v['y'], 'z': v['z']}
        for i, (name, v) in enumerate(raw.items())
    ]


def get_borehole_wgs84_locations():
    items = get_borehole_raw_locations()
    result = []
    for item in items:
        try:
            x, y, z = float(item['x']), float(item['y']), float(item['z'])
            converted = _convert_point_to_wgs84(x, y)
            if not converted:
                continue
            lon, lat = converted
        except Exception:
            continue
        result.append({
            'id': item['id'], 'name': item['name'],
            'longitude': round(lon, 8), 'latitude': round(lat, 8),
            'altitude': round(z, 3),
            'source': {'x': item['x'], 'y': item['y'], 'z': item['z']},
        })
    return result
