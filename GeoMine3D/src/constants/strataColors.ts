/**
 * 钻孔分层配色（与后端 `server_import_service.LAYER_COLORS` 保持一致）。
 *
 * 后端导入时已把颜色写进 `borehole_segments.color`，前端应优先使用接口返回值；
 * 这里的常量只作为接口缺色时的兜底，同时保证柱状图与属性面板用同一套颜色。
 * 顺序 = 层顶→层底：风积砂层 / 土层 / 4-1 旋回(泥岩·砂岩) / 煤顶泥岩层 / 煤3-1 / 直接底层 / 下伏岩层
 */
export const BOREHOLE_LAYER_COLORS = [
    '#e8d7a4', // 风积砂层
    '#8f7a63', // 土层
    '#9ab98f', // 第4旋回泥岩层
    '#e6c878', // 第4旋回砂岩层
    '#58a086', // 第3旋回泥岩层
    '#cf8b4f', // 第3旋回砂岩层
    '#8fb0d4', // 第2旋回泥岩层
    '#a8ab63', // 第2旋回砂岩层
    '#5484a8', // 第1旋回泥岩层
    '#b4738a', // 第1旋回砂岩层
    '#b0a08c', // 煤顶泥岩层
    '#6a6a72', // 煤3-1
    '#b7bcc2', // 直接底层
    '#85878f', // 下伏岩层
] as const

/** 层数超出配色表时的兜底色 */
export const BOREHOLE_LAYER_FALLBACK_COLOR = '#8d7358'

/** 取某层的显示颜色：优先用接口返回的颜色，其次按层序取兜底配色 */
export function boreholeLayerColor(color: string | undefined | null, index: number) {
    if (color) return color
    return BOREHOLE_LAYER_COLORS[index % BOREHOLE_LAYER_COLORS.length] ?? BOREHOLE_LAYER_FALLBACK_COLOR
}
