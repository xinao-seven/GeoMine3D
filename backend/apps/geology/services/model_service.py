"""
model_service.py

模型资源服务层。
策略：
  1. 自动扫描 static/models/{type}/ 目录下的 .glb 文件
  2. 若 models_meta.json 中存在对应 fileName 的元数据条目，则合并使用
  3. 若无元数据，自动生成默认元数据
  4. models_meta.json 中 fileName 指向不存在文件的条目会被跳过

这样只需把 .glb 文件放入正确目录，系统即可自动识别，无需手动修改 JSON。
"""
import json
from pathlib import Path
from django.conf import settings

_BASE = Path(settings.BASE_DIR)
_META_FILE = _BASE / 'data' / 'models_meta.json'
_STATIC_MODELS_DIR = _BASE / 'static' / 'models'

# 目录名 -> 模型类型
_DIR_TYPE_MAP = {
    'strata': 'stratum',
    'workingfaces': 'workingface',
    'boreholes': 'borehole',
}

# 默认名称前缀（用于自动生成元数据时）
_TYPE_NAME_PREFIX = {
    'stratum': '地层模型',
    'workingface': '工作面模型',
    'borehole': '钻孔模型',
}


def _load_meta_index():
    """加载 models_meta.json，以 fileName 为 key 返回查找字典"""
    if not _META_FILE.exists():
        return {}
    with open(_META_FILE, 'r', encoding='utf-8') as f:
        items = json.load(f)
    return {item['fileName']: item for item in items}


def _scan_glb_files():
    """
    扫描 static/models 下各类型子目录，返回已发现 .glb 文件的元数据列表。
    优先使用 models_meta.json 中匹配 fileName 的条目，否则自动生成。
    """
    meta_index = _load_meta_index()
    results = []
    auto_id_counter = 1000

    for dir_name, model_type in _DIR_TYPE_MAP.items():
        type_dir = _STATIC_MODELS_DIR / dir_name
        if not type_dir.exists():
            continue

        for glb_file in sorted(type_dir.glob('*.glb')):
            file_name = glb_file.name
            file_url = f'/static/models/{dir_name}/{file_name}'

            if file_name in meta_index:
                # 有元数据 -> 直接用，修正 fileUrl 确保路径正确
                entry = dict(meta_index[file_name])
                entry['fileUrl'] = file_url
                results.append(entry)
            else:
                # 无元数据 -> 自动生成
                auto_id = f'auto-{auto_id_counter}'
                auto_id_counter += 1
                display_name = f'{_TYPE_NAME_PREFIX.get(model_type, "模型")}-{file_name[:-4]}'
                results.append({
                    'id': auto_id,
                    'name': display_name,
                    'type': model_type,
                    'version': '1.0',
                    'format': 'glb',
                    'description': f'自动识别: {file_name}',
                    'fileName': file_name,
                    'fileUrl': file_url,
                    'bbox': None,
                })

    return results


def get_model_list(model_type=None, keyword=None):
    models = _scan_glb_files()
    if model_type:
        models = [m for m in models if m.get('type') == model_type]
    if keyword:
        kw = keyword.lower()
        models = [
            m for m in models
            if kw in m.get('name', '').lower() or kw in m.get('description', '').lower()
        ]
    return models


def get_model_detail(model_id):
    for m in _scan_glb_files():
        if str(m.get('id')) == str(model_id):
            return m
    return None


def get_model_resource(model_id):
    model = get_model_detail(model_id)
    if not model:
        return None
    return {
        'id': model['id'],
        'name': model['name'],
        'fileUrl': model['fileUrl'],
        'format': model.get('format', 'glb'),
        'bbox': model.get('bbox'),
    }
