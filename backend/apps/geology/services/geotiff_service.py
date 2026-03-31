from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from django.conf import settings
from pyproj import CRS, Transformer

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional at import time
    Image = None


TARGET_CRS = 'EPSG:4326'

_BASE_DIR = Path(settings.BASE_DIR)
_TIF_DIR = _BASE_DIR / 'data' / 'tif'
_MINE_AREA_PRJ = _BASE_DIR / 'data' / 'shp' / '锦界矿边界.prj'
_TIF_PREVIEW_DIR = _BASE_DIR / 'static' / 'tif-previews'
_DEFAULT_SOURCE_CRS = 'EPSG:4326'
_FALLBACK_SOURCE_CRS = (
    'EPSG:32649',  # WGS84 / UTM zone 49N
    'EPSG:32648',  # WGS84 / UTM zone 48N
    'EPSG:4547',   # CGCS2000 / 3-degree GK CM 111E
    'EPSG:4548',   # CGCS2000 / 3-degree GK CM 114E
)


def _is_lonlat(lon: float, lat: float) -> bool:
    return -180 <= lon <= 180 and -90 <= lat <= 90


def _build_transformer_candidates() -> tuple[list[tuple[str, Transformer]], str]:
    source_crs = CRS.from_string(_DEFAULT_SOURCE_CRS)
    if _MINE_AREA_PRJ.exists():
        try:
            prj_text = _MINE_AREA_PRJ.read_text(encoding='utf-8', errors='ignore').strip()
            if prj_text:
                source_crs = CRS.from_wkt(prj_text)
        except Exception:
            pass

    target_crs = CRS.from_epsg(4326)
    source_crs_text = source_crs.to_string()

    candidates: list[tuple[str, Transformer]] = [
        (source_crs_text, Transformer.from_crs(source_crs, target_crs, always_xy=True))
    ]
    for crs_text in _FALLBACK_SOURCE_CRS:
        if crs_text == source_crs_text:
            continue
        try:
            fallback = CRS.from_string(crs_text)
            candidates.append((crs_text, Transformer.from_crs(fallback, target_crs, always_xy=True)))
        except Exception:
            continue

    return candidates, source_crs_text


def _read_tfw(path: Path) -> tuple[float, float, float, float, float, float]:
    values: list[float] = []
    for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        text = line.strip()
        if not text:
            continue
        values.append(float(text))
    if len(values) != 6:
        raise ValueError(f'Invalid TFW file, expected 6 lines: {path.name}')
    return values[0], values[1], values[2], values[3], values[4], values[5]


def _read_uint(data: bytes, endian: str) -> int:
    if len(data) == 2:
        return struct.unpack(f'{endian}H', data)[0]
    if len(data) == 4:
        return struct.unpack(f'{endian}I', data)[0]
    if len(data) == 8:
        return struct.unpack(f'{endian}Q', data)[0]
    raise ValueError(f'Unsupported unsigned integer byte length: {len(data)}')


def _extract_inline_value(value_bytes: bytes, byte_count: int, endian: str) -> bytes:
    if byte_count > 4:
        raise ValueError('Inline TIFF value is larger than 4 bytes')
    if endian == '<':
        return value_bytes[:byte_count]
    return value_bytes[4 - byte_count:]


def _read_tiff_size(path: Path) -> tuple[int, int]:
    type_size_map = {
        1: 1,   # BYTE
        2: 1,   # ASCII
        3: 2,   # SHORT
        4: 4,   # LONG
        5: 8,   # RATIONAL
        6: 1,   # SBYTE
        7: 1,   # UNDEFINED
        8: 2,   # SSHORT
        9: 4,   # SLONG
        10: 8,  # SRATIONAL
        11: 4,  # FLOAT
        12: 8,  # DOUBLE
    }

    width: int | None = None
    height: int | None = None

    with path.open('rb') as fh:
        header = fh.read(8)
        if len(header) < 8:
            raise ValueError(f'Invalid TIFF header: {path.name}')

        order = header[:2]
        if order == b'II':
            endian = '<'
        elif order == b'MM':
            endian = '>'
        else:
            raise ValueError(f'Unsupported TIFF byte order: {path.name}')

        magic = struct.unpack(f'{endian}H', header[2:4])[0]
        if magic != 42:
            raise ValueError(f'Unsupported TIFF format (not classic TIFF): {path.name}')

        ifd_offset = struct.unpack(f'{endian}I', header[4:8])[0]
        fh.seek(ifd_offset)
        entry_count_bytes = fh.read(2)
        if len(entry_count_bytes) < 2:
            raise ValueError(f'Invalid TIFF IFD entry count: {path.name}')
        entry_count = struct.unpack(f'{endian}H', entry_count_bytes)[0]

        for _ in range(entry_count):
            entry = fh.read(12)
            if len(entry) < 12:
                break

            tag = struct.unpack(f'{endian}H', entry[0:2])[0]
            field_type = struct.unpack(f'{endian}H', entry[2:4])[0]
            count = struct.unpack(f'{endian}I', entry[4:8])[0]
            value_or_offset = entry[8:12]

            if tag not in (256, 257):
                continue

            unit = type_size_map.get(field_type)
            if unit is None:
                continue

            total_size = unit * count
            if total_size <= 4:
                value_bytes = _extract_inline_value(value_or_offset, unit, endian)
            else:
                offset = struct.unpack(f'{endian}I', value_or_offset)[0]
                current_pos = fh.tell()
                fh.seek(offset)
                value_bytes = fh.read(unit)
                fh.seek(current_pos)

            value = _read_uint(value_bytes, endian)
            if tag == 256:
                width = int(value)
            else:
                height = int(value)

            if width is not None and height is not None:
                break

    if width is None or height is None:
        raise ValueError(f'Unable to read TIFF width/height from {path.name}')
    return width, height


def _to_wgs84(x: float, y: float, transformer: Transformer) -> tuple[float, float] | None:
    if _is_lonlat(x, y):
        return x, y

    def _valid(lon: float, lat: float) -> bool:
        return (
            lon is not None
            and lat is not None
            and lon == lon
            and lat == lat
            and abs(lon) != float('inf')
            and abs(lat) != float('inf')
            and _is_lonlat(lon, lat)
        )

    # Try standard axis order first.
    lon, lat = transformer.transform(x, y)
    if _valid(lon, lat):
        return lon, lat

    # Fallback for datasets where x/y are swapped in source metadata.
    lon2, lat2 = transformer.transform(y, x)
    if _valid(lon2, lat2):
        return lon2, lat2

    return None


def _compute_bounds_wgs84(
    width: int,
    height: int,
    tfw: tuple[float, float, float, float, float, float],
    transformer_candidates: list[tuple[str, Transformer]],
) -> tuple[dict[str, float], str]:
    a, d, b, e, c, f = tfw

    # TFW C/F are center coordinates of top-left pixel. Convert to image outer edge.
    edge_x = c - (a + b) / 2.0
    edge_y = f - (d + e) / 2.0

    corners = [
        (0, 0),
        (width, 0),
        (0, height),
        (width, height),
    ]

    for crs_used, transformer in transformer_candidates:
        points: list[tuple[float, float]] = []
        valid = True
        for col, row in corners:
            x = edge_x + a * col + b * row
            y = edge_y + d * col + e * row
            pt = _to_wgs84(x, y, transformer)
            if pt is None:
                valid = False
                break
            points.append(pt)

        if not valid:
            continue

        lons = [pt[0] for pt in points]
        lats = [pt[1] for pt in points]
        bounds = {
            'west': round(min(lons), 8),
            'east': round(max(lons), 8),
            'south': round(min(lats), 8),
            'north': round(max(lats), 8),
        }
        return bounds, crs_used

    raise ValueError('Unable to transform TIFF bounds to WGS84 with configured CRS candidates')


def _build_file_urls(tif_path: Path) -> dict[str, str]:
    name = tif_path.name
    return {
        'tifUrl': f'/data/tif/{name}',
        'tfwUrl': f'/data/tif/{tif_path.with_suffix(".tfw").name}',
        'auxXmlUrl': f'/data/tif/{name}.aux.xml',
        'ovrUrl': f'/data/tif/{name}.ovr',
    }


def _ensure_preview_png(tif_path: Path) -> str:
    if Image is None:
        raise RuntimeError('Pillow is required to render TIFF preview. Please install Pillow.')

    _TIF_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    preview_path = _TIF_PREVIEW_DIR / f'{tif_path.stem}.png'
    if preview_path.exists() and preview_path.stat().st_mtime >= tif_path.stat().st_mtime:
        return f'/static/tif-previews/{preview_path.name}'

    with Image.open(tif_path) as img:
        converted = img.convert('RGBA')
        converted.save(preview_path, format='PNG', optimize=True)

    return f'/static/tif-previews/{preview_path.name}'


def get_geotiff_layers() -> dict[str, Any]:
    transformer_candidates, source_crs = _build_transformer_candidates()

    items: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    if not _TIF_DIR.exists():
        return {
            'sourceCrs': source_crs,
            'targetCrs': TARGET_CRS,
            'items': items,
            'skipped': skipped,
        }

    for tif_path in sorted(_TIF_DIR.glob('*.tif')):
        tfw_path = tif_path.with_suffix('.tfw')
        aux_path = Path(f'{tif_path}.aux.xml')
        ovr_path = Path(f'{tif_path}.ovr')

        missing = [
            file_path.name
            for file_path in (tfw_path, aux_path, ovr_path)
            if not file_path.exists()
        ]
        if missing:
            skipped.append({
                'fileName': tif_path.name,
                'reason': f'Missing companion files: {", ".join(missing)}',
            })
            continue

        try:
            width, height = _read_tiff_size(tif_path)
            tfw = _read_tfw(tfw_path)
            bounds, crs_used = _compute_bounds_wgs84(width, height, tfw, transformer_candidates)
            preview_url = _ensure_preview_png(tif_path)
        except Exception as ex:
            skipped.append({'fileName': tif_path.name, 'reason': str(ex)})
            continue

        item_id = tif_path.stem
        items.append({
            'id': item_id,
            'name': tif_path.stem,
            'fileName': tif_path.name,
            **_build_file_urls(tif_path),
            'previewUrl': preview_url,
            'sourceCrsUsed': crs_used,
            'width': width,
            'height': height,
            'bounds': bounds,
        })

    return {
        'sourceCrs': source_crs,
        'targetCrs': TARGET_CRS,
        'items': items,
        'skipped': skipped,
    }
