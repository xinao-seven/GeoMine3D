from pathlib import Path
from typing import Any

import shapefile
from django.conf import settings
from pyproj import CRS, Transformer


TARGET_CRS = 'EPSG:4326'

_BASE_DIR = Path(settings.BASE_DIR)
_SHP_DIR = _BASE_DIR / 'data' / 'shp'
_MINE_AREA_SHP = _SHP_DIR / '锦界矿边界.shp'
_WORKING_FACE_SHP = _SHP_DIR / '开采工作面.shp'
_ENCODING_CANDIDATES = ('utf-8', 'gbk', 'gb18030', 'latin1')


def _to_wgs84(x: float, y: float, transformer: Transformer) -> list[float]:
    lon, lat = transformer.transform(x, y)
    return [round(float(lon), 8), round(float(lat), 8)]


def _split_parts(points: list[Any], parts: list[int]) -> list[list[Any]]:
    boundaries = list(parts) + [len(points)]
    return [points[boundaries[i]:boundaries[i + 1]] for i in range(len(boundaries) - 1)]


def _ensure_ring_closed(coords: list[list[float]]) -> list[list[float]]:
    if not coords:
        return coords
    if coords[0] != coords[-1]:
        return coords + [coords[0]]
    return coords


def _shape_to_geojson(shape: shapefile.Shape, transformer: Transformer) -> dict[str, Any] | None:
    parts = _split_parts(shape.points, list(shape.parts))
    converted_parts = []
    for part in parts:
        converted = [_to_wgs84(pt[0], pt[1], transformer) for pt in part]
        if converted:
            converted_parts.append(converted)

    if not converted_parts:
        return None

    if shape.shapeType in (shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM):
        rings = [_ensure_ring_closed(part) for part in converted_parts]
        return {'type': 'Polygon', 'coordinates': rings}

    if shape.shapeType in (shapefile.POLYLINE, shapefile.POLYLINEZ, shapefile.POLYLINEM):
        if len(converted_parts) == 1:
            return {'type': 'LineString', 'coordinates': converted_parts[0]}
        return {'type': 'MultiLineString', 'coordinates': converted_parts}

    if shape.shapeType in (shapefile.POINT, shapefile.POINTZ, shapefile.POINTM):
        first = converted_parts[0][0]
        return {'type': 'Point', 'coordinates': first}

    return None


def _detect_encodings(shp_path: Path) -> list[str]:
    # Prefer .cpg declaration if present, then try common fallbacks.
    cpg_path = shp_path.with_suffix('.cpg')
    candidates: list[str] = []
    if cpg_path.exists():
        try:
            cpg_encoding = cpg_path.read_text(encoding='utf-8', errors='ignore').strip()
            if cpg_encoding:
                candidates.append(cpg_encoding)
        except Exception:
            pass

    for enc in _ENCODING_CANDIDATES:
        if enc not in candidates:
            candidates.append(enc)
    return candidates


def _open_reader_with_fallback(shp_path: Path) -> shapefile.Reader:
    last_error: Exception | None = None
    for encoding in _detect_encodings(shp_path):
        try:
            return shapefile.Reader(str(shp_path), encoding=encoding, encodingErrors='replace')
        except Exception as ex:
            last_error = ex

    if last_error:
        raise RuntimeError(f'Unable to open shapefile with any supported encoding: {last_error}')
    raise RuntimeError('Unable to open shapefile for unknown reason')


def _get_source_crs(shp_path: Path) -> CRS:
    prj_path = shp_path.with_suffix('.prj')
    if prj_path.exists():
        prj_text = prj_path.read_text(encoding='utf-8', errors='ignore').strip()
        if prj_text:
            return CRS.from_wkt(prj_text)
    # Fallback for missing .prj; keeps service usable when metadata is incomplete.
    return CRS.from_epsg(4326)


def _build_transformer(source_crs: CRS) -> Transformer:
    target_crs = CRS.from_epsg(4326)
    return Transformer.from_crs(source_crs, target_crs, always_xy=True)


def _reader_to_feature_collection(shp_path: Path, source_name: str) -> dict[str, Any]:
    if not shp_path.exists():
        raise FileNotFoundError(f'SHP file not found: {shp_path}')

    source_crs = _get_source_crs(shp_path)
    transformer = _build_transformer(source_crs)
    reader = _open_reader_with_fallback(shp_path)
    field_names = [field[0] for field in reader.fields[1:]]
    features = []

    for shape_record in reader.shapeRecords():
        geometry = _shape_to_geojson(shape_record.shape, transformer)
        if not geometry:
            continue

        attrs = dict(zip(field_names, list(shape_record.record)))
        props = {
            'source': source_name,
            **attrs,
        }
        features.append({
            'type': 'Feature',
            'properties': props,
            'geometry': geometry,
        })

    return {
        'type': 'FeatureCollection',
        'sourceCrs': source_crs.to_string(),
        'targetCrs': TARGET_CRS,
        'features': features,
    }


def get_mine_area_boundary() -> dict[str, Any]:
    return _reader_to_feature_collection(_MINE_AREA_SHP, source_name='mine-area')


def get_working_face_boundaries() -> dict[str, Any]:
    return _reader_to_feature_collection(_WORKING_FACE_SHP, source_name='working-face')


def get_projection_metadata() -> dict[str, Any]:
    mine_source = _get_source_crs(_MINE_AREA_SHP).to_string() if _MINE_AREA_SHP.exists() else None
    working_source = _get_source_crs(_WORKING_FACE_SHP).to_string() if _WORKING_FACE_SHP.exists() else None
    return {
        'sourceCrs': mine_source or working_source,
        'mineAreaSourceCrs': mine_source,
        'workingFaceSourceCrs': working_source,
        'targetCrs': TARGET_CRS,
        'sourceShpDir': str(_SHP_DIR),
    }
