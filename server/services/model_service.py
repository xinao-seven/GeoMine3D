import json
from config import DATA_DIR, STATIC_DIR

_META_FILE = DATA_DIR / 'models_meta.json'
_STATIC_MODELS = STATIC_DIR / 'models'

_DIR_TYPE_MAP = {
    'strata': 'stratum',
    'workingfaces': 'workingface',
    'boreholes': 'borehole',
}

_TYPE_NAME_PREFIX = {
    'stratum': '地层',
    'workingface': '工作面',
    'borehole': '钻孔',
}


def _load_meta_index():
    if not _META_FILE.exists():
        return {}
    with open(_META_FILE, 'r', encoding='utf-8') as f:
        items = json.load(f)
    return {item['fileName']: item for item in items}


def _scan_glb_files():
    meta_index = _load_meta_index()
    results = []
    auto_id = 1000

    for dir_name, model_type in _DIR_TYPE_MAP.items():
        type_dir = _STATIC_MODELS / dir_name
        if not type_dir.exists():
            continue

        for glb_file in sorted(type_dir.glob('*.glb')):
            file_name = glb_file.name
            file_url = f'/static/models/{dir_name}/{file_name}'

            if file_name in meta_index:
                entry = dict(meta_index[file_name])
                entry['fileUrl'] = file_url
                results.append(entry)
            else:
                display = f'{_TYPE_NAME_PREFIX.get(model_type, "模型")}-{file_name[:-4]}'
                results.append({
                    'id': f'auto-{auto_id}',
                    'name': display,
                    'type': model_type,
                    'version': '1.0',
                    'format': 'glb',
                    'description': f'自动识别: {file_name}',
                    'fileName': file_name,
                    'fileUrl': file_url,
                    'bbox': None,
                })
                auto_id += 1

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
