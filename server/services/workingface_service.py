import json
from config import DATA_DIR

_DATA_FILE = DATA_DIR / 'workingfaces.json'


def _load_data():
    if not _DATA_FILE.exists():
        return []
    with open(_DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_workingface_list(keyword=None, status=None):
    items = _load_data()
    if keyword:
        kw = keyword.lower()
        items = [
            i for i in items
            if kw in i.get('name', '').lower() or kw in i.get('code', '').lower()
        ]
    if status:
        items = [i for i in items if i.get('status') == status]
    return items


def get_workingface_detail(wf_id):
    for i in _load_data():
        if str(i.get('id')) == str(wf_id):
            return i
    return None


def get_status_stats():
    items = _load_data()
    stats = {}
    for i in items:
        s = i.get('status', '未知')
        stats[s] = stats.get(s, 0) + 1
    return [{'status': k, 'count': v} for k, v in stats.items()]
