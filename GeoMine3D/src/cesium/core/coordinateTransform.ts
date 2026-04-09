import { Cartesian3, Cartographic, Ellipsoid, Math as CesiumMath, Matrix4, Transforms } from 'cesium'

export interface DegreePosition {
    lon: number
    lat: number
    height?: number
}

export interface DegreePositionRequiredHeight {
    lon: number
    lat: number
    height: number
}

/**
 * 将经纬高坐标转换为笛卡尔坐标。
 */
export function degreesToCartesian(position: DegreePosition): Cartesian3 {
    return Cartesian3.fromDegrees(position.lon, position.lat, position.height ?? 0)
}

/**
 * 将笛卡尔坐标转换为经纬高坐标。
 */
export function cartesianToDegrees(position: Cartesian3): DegreePositionRequiredHeight | null {
    const cartographic = Cartographic.fromCartesian(position)
    if (!cartographic) {
        return null
    }

    return {
        lon: CesiumMath.toDegrees(cartographic.longitude),
        lat: CesiumMath.toDegrees(cartographic.latitude),
        height: cartographic.height,
    }
}

/**
 * 批量将经纬高数组转换为笛卡尔坐标数组。
 */
export function degreesArrayToCartesianArray(positions: DegreePosition[]): Cartesian3[] {
    const cartographics = positions.map((item) =>
        Cartographic.fromDegrees(item.lon, item.lat, item.height ?? 0),
    )
    return Ellipsoid.WGS84.cartographicArrayToCartesianArray(cartographics)
}

/**
 * 批量将笛卡尔坐标数组转换为经纬高数组。
 */
export function cartesianArrayToDegreesArray(positions: Cartesian3[]): DegreePositionRequiredHeight[] {
    const cartographics = Ellipsoid.WGS84.cartesianArrayToCartographicArray(positions)
    return cartographics.map((item) => ({
        lon: CesiumMath.toDegrees(item.longitude),
        lat: CesiumMath.toDegrees(item.latitude),
        height: item.height,
    }))
}

/**
 * 生成 East-North-Up 到地固坐标系的变换矩阵。
 */
export function createEastNorthUpTransform(origin: Cartesian3): Matrix4 {
    return Transforms.eastNorthUpToFixedFrame(origin)
}

/**
 * 基于 ENU 偏移量计算世界坐标点。
 */
export function translateFromEnuOffset(origin: Cartesian3, east: number, north: number, up: number): Cartesian3 {
    const enu = Transforms.eastNorthUpToFixedFrame(origin)
    return Matrix4.multiplyByPoint(enu, new Cartesian3(east, north, up), new Cartesian3())
}

/**
 * 根据平移向量创建平移矩阵。
 */
export function createTranslationMatrix(offset: Cartesian3): Matrix4 {
    return Matrix4.fromTranslation(offset)
}

/**
 * 计算两个模型矩阵的乘积。
 */
export function multiplyModelMatrix(left: Matrix4, right: Matrix4): Matrix4 {
    return Matrix4.multiply(left, right, new Matrix4())
}
