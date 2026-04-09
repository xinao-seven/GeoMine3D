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

export function degreesToCartesian(position: DegreePosition): Cartesian3 {
    return Cartesian3.fromDegrees(position.lon, position.lat, position.height ?? 0)
}

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

export function degreesArrayToCartesianArray(positions: DegreePosition[]): Cartesian3[] {
    const cartographics = positions.map((item) =>
        Cartographic.fromDegrees(item.lon, item.lat, item.height ?? 0),
    )
    return Ellipsoid.WGS84.cartographicArrayToCartesianArray(cartographics)
}

export function cartesianArrayToDegreesArray(positions: Cartesian3[]): DegreePositionRequiredHeight[] {
    const cartographics = Ellipsoid.WGS84.cartesianArrayToCartographicArray(positions)
    return cartographics.map((item) => ({
        lon: CesiumMath.toDegrees(item.longitude),
        lat: CesiumMath.toDegrees(item.latitude),
        height: item.height,
    }))
}

export function createEastNorthUpTransform(origin: Cartesian3): Matrix4 {
    return Transforms.eastNorthUpToFixedFrame(origin)
}

export function translateFromEnuOffset(origin: Cartesian3, east: number, north: number, up: number): Cartesian3 {
    const enu = Transforms.eastNorthUpToFixedFrame(origin)
    return Matrix4.multiplyByPoint(enu, new Cartesian3(east, north, up), new Cartesian3())
}

export function createTranslationMatrix(offset: Cartesian3): Matrix4 {
    return Matrix4.fromTranslation(offset)
}

export function multiplyModelMatrix(left: Matrix4, right: Matrix4): Matrix4 {
    return Matrix4.multiply(left, right, new Matrix4())
}
