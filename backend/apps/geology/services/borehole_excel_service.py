"""
borehole_excel_service.py

钻孔数据服务层。

数据来源：
    - data/boreholes/ 目录下的 .xlsx 文件（地层数据）
    - data/location/钻孔位置.xlsx（钻孔坐标数据，列：name / y / x / z）

地层列名映射（_FIELD_MAP）：
    - 深度：每层的底边深度（bottom depth of layer）
    - 厚度：本层厚度（bottomDepth - topDepth）

坐标说明：
    - 对外接口返回原始坐标（x/y/z）
    - 前端渲染时再映射到 Three.js 轴
"""
import pandas as pd
from pathlib import Path
from django.conf import settings

_BASE_DIR        = Path(settings.BASE_DIR)
_BOREHOLES_DIR   = _BASE_DIR / 'data' / 'boreholes'
_LOCATION_FILE   = _BASE_DIR / 'data' / 'location' / '钻孔位置.xlsx'

# 地层数据字段映射（中文列名 → 内部字段名）
_FIELD_MAP = {
    'borehole_name': '钻孔名称',
    'layer_name':    '地层名称',
    'depth':         '深度',      # 每层底边深度
    'thickness':     '厚度',      # 本层厚度
}


def _normalize_name(name: str) -> str:
    """标准化名称用于位置表匹配，尽量容忍空格/符号差异。"""
    if not name:
        return ''
    return ''.join(ch for ch in str(name).strip().upper() if ch.isalnum())


# ---------------------------------------------------------------------------
# Location 数据加载
# ---------------------------------------------------------------------------

def _load_location_index():
    """
    加载 data/location/钻孔位置.xlsx，返回 {name: {x, y, z}} 字典。
    x / y / z 均为原始地理坐标（未归一化）。
    若文件不存在或格式错误则返回空字典。
    """
    if not _LOCATION_FILE.exists():
        print(f'[borehole_excel_service] 位置文件不存在: {_LOCATION_FILE}')
        return {}
    try:
        df = pd.read_excel(_LOCATION_FILE, engine='openpyxl')
    except Exception as e:
        print(f'[borehole_excel_service] 位置文件读取失败: {e}')
        return {}

    required_cols = {'name', 'x', 'y', 'z'}
    missing = required_cols - set(df.columns)
    if missing:
        print(f'[borehole_excel_service] 位置文件缺少列: {missing}，实际列名: {list(df.columns)}')
        return {}

    index = {}
    for _, row in df.iterrows():
        name = str(row['name']).strip()
        if not name or name == 'nan':
            continue
        try:
            index[name] = {
                'x': float(row['x']),
                'y': float(row['y']),
                'z': float(row['z']),
            }
        except (ValueError, TypeError):
            continue
    return index


def _build_location_match_index(loc_index):
    """为位置匹配建立名称索引：精确名与标准化名。"""
    normalized_index = {}
    for name, geo in loc_index.items():
        normalized = _normalize_name(name)
        if normalized and normalized not in normalized_index:
            normalized_index[normalized] = geo
    return normalized_index


# ---------------------------------------------------------------------------
# 地层 Excel 数据加载
# ---------------------------------------------------------------------------

def _discover_excel_files():
    """
    扫描 boreholes 目录，返回要加载的 .xlsx 文件列表。
    优先使用非 boreholes.xlsx 的文件；若无，则回退到 boreholes.xlsx。
    """
    if not _BOREHOLES_DIR.exists():
        return []
    all_xlsx = sorted(_BOREHOLES_DIR.glob('*.xlsx'))
    sample_file = _BOREHOLES_DIR / 'boreholes.xlsx'
    user_files = [f for f in all_xlsx if f != sample_file]
    fallback = [sample_file] if sample_file.exists() else []
    return user_files if user_files else fallback


def _parse_single_excel(file_path):
    """
    解析单个地层 Excel 文件，返回 {borehole_name: {...}} 字典。
    列名以 _FIELD_MAP 中定义的中文名为准；
    若缺少必要列则返回空字典并打印警告。

    深度解读：
      depth     = 该层底边深度（bottom depth）
      thickness = 本层厚度 = bottomDepth - topDepth
      topDepth  = depth - thickness
    """
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
    except Exception as e:
        print(f'[borehole_excel_service] 跳过 {file_path.name}: 读取失败 - {e}')
        return {}

    reverse_map = {v: k for k, v in _FIELD_MAP.items()}
    df = df.rename(columns=reverse_map)

    required = list(_FIELD_MAP.keys())
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(
            f'[borehole_excel_service] 跳过 {file_path.name}: '
            f'缺少列 {[_FIELD_MAP[c] for c in missing]}，'
            f'实际列名: {list(df.columns)}'
        )
        return {}

    boreholes = {}
    for _, row in df.iterrows():
        name = str(row['borehole_name']).strip()
        if not name or name == 'nan':
            continue
        if name not in boreholes:
            boreholes[name] = {'name': name, 'layers': []}
        try:
            bottom_depth = float(row['depth'])      # 底边深度
            thickness    = float(row['thickness'])  # 本层厚度
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
    """加载所有地层 Excel + 位置文件，返回结构化钻孔数据列表"""
    files = _discover_excel_files()
    if not files:
        return []

    # 地层数据合并
    merged = {}
    for f in files:
        data = _parse_single_excel(f)
        merged.update(data)

    # 位置数据（原始坐标）
    loc_raw = _load_location_index()
    loc_normalized_index = _build_location_match_index(loc_raw)

    result = []
    for idx, (name, data) in enumerate(merged.items()):
        layers = data['layers']
        total_depth = max((l['bottomDepth'] for l in layers), default=0)
        bh = {
            'id':         str(idx + 1),
            'name':       name,
            'totalDepth': total_depth,
            'layerCount': len(layers),
            'layers':     layers,
        }
        # 优先精确匹配，失败后走标准化名称匹配
        raw_loc = loc_raw.get(name)
        if not raw_loc:
            raw_loc = loc_normalized_index.get(_normalize_name(name))

        if raw_loc:
            bh['location'] = {
                'x': round(raw_loc['x'], 3),
                'y': round(raw_loc['y'], 3),
                'z': round(raw_loc['z'], 3),
            }
        result.append(bh)
    return result


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def get_borehole_list(keyword=None, min_depth=None, max_depth=None):
    boreholes = _load_excel()
    if keyword:
        keyword = keyword.lower()
        boreholes = [b for b in boreholes if keyword in b['name'].lower()]
    if min_depth is not None:
        boreholes = [b for b in boreholes if b['totalDepth'] >= float(min_depth)]
    if max_depth is not None:
        boreholes = [b for b in boreholes if b['totalDepth'] <= float(max_depth)]
    return [
        {
            'id':         b['id'],
            'name':       b['name'],
            'totalDepth': b['totalDepth'],
            'layerCount': b['layerCount'],
            'location':   b.get('location'),   # 原始坐标，可为 None
        }
        for b in boreholes
    ]


def get_borehole_detail(borehole_id):
    boreholes = _load_excel()
    for b in boreholes:
        if str(b['id']) == str(borehole_id):
            return b
    return None


def search_boreholes(keyword):
    return get_borehole_list(keyword=keyword)


def get_thickness_stats():
    """统计各地层平均厚度"""
    boreholes = _load_excel()
    layer_thickness = {}
    for b in boreholes:
        for l in b['layers']:
            name = l['layerName']
            if name not in layer_thickness:
                layer_thickness[name] = []
            layer_thickness[name].append(l['thickness'])
    return [
        {
            'layerName':    k,
            'avgThickness': round(sum(v) / len(v), 2),
            'count':        len(v),
        }
        for k, v in layer_thickness.items()
    ]


def get_depth_stats():
    """获取每个钻孔的总深度"""
    boreholes = _load_excel()
    return [{'name': b['name'], 'totalDepth': b['totalDepth']} for b in boreholes]


def get_layer_frequency():
    """统计各地层出现次数"""
    boreholes = _load_excel()
    freq = {}
    for b in boreholes:
        for l in b['layers']:
            thickness = l.get('thickness', 0)
            if thickness <= 0:
                continue
            freq[l['layerName']] = freq.get(l['layerName'], 0) + 1
    return [
        {'layerName': k, 'count': v}
        for k, v in sorted(freq.items(), key=lambda x: -x[1])
    ]


def get_borehole_raw_locations():
    """返回钻孔原始坐标（不归一化），用于统计分析中的 XY 位置图。"""
    raw_locations = _load_location_index()
    # 直接返回位置表中的全部点，避免因名称匹配失败导致散点缺失。
    return [
        {
            'id': str(idx + 1),
            'name': name,
            'x': raw['x'],
            'y': raw['y'],
            'z': raw['z'],
        }
        for idx, (name, raw) in enumerate(raw_locations.items())
    ]
