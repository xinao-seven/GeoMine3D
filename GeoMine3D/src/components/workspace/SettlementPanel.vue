<template>
    <div class="settlement-panel" :class="{ collapsed: !open, active: settlement.enabled }">
        <button class="sp-head" @click="open = !open">
            <span class="sp-tag">SETTLEMENT</span>
            <b>沉陷对比</b>
            <span v-if="settlement.enabled" class="sp-live">ON</span>
            <el-icon class="sp-caret"><component :is="open ? 'ArrowDown' : 'ArrowUp'" /></el-icon>
        </button>

        <div v-if="open" class="sp-body">
            <div v-if="settlement.loadError" class="sp-error">
                位移场加载失败：{{ settlement.loadError }}
            </div>

            <template v-else>
                <label class="sp-switch">
                    <el-switch
                        :model-value="settlement.enabled"
                        :loading="settlement.loading"
                        @update:model-value="onToggle"
                    />
                    <span>启用沉陷对比</span>
                    <b v-if="settlement.boundLayers">{{ settlement.boundLayers }} 层</b>
                </label>

                <div class="sp-row">
                    <span>变形进程</span><b>{{ settlement.timePercent }}%</b>
                </div>
                <el-slider
                    :model-value="settlement.timePercent"
                    :show-tooltip="false"
                    :disabled="!settlement.enabled"
                    @input="(v: number) => settlement.timePercent = Number(v)"
                />

                <div class="sp-row">
                    <span>沉陷夸大</span><b>{{ settlement.exaggeration }}×</b>
                </div>
                <el-slider
                    :model-value="settlement.exaggeration"
                    :min="1" :max="50" :step="1"
                    :show-tooltip="false"
                    :disabled="!settlement.enabled"
                    @input="(v: number) => settlement.exaggeration = Number(v)"
                />

                <div class="sp-row sp-modes">
                    <span>着色</span>
                    <div class="sp-buttons">
                        <button
                            v-for="m in colorModes" :key="m.value"
                            :class="{ on: settlement.colorMode === m.value }"
                            :disabled="!settlement.enabled"
                            @click="settlement.colorMode = m.value"
                        >{{ m.label }}</button>
                    </div>
                </div>

                <div class="sp-actions">
                    <button :disabled="!settlement.enabled" @click="settlement.time = 0">沉陷前</button>
                    <button :disabled="!settlement.enabled" @click="settlement.time = 1">沉陷后</button>
                    <button :disabled="!settlement.enabled" @click="settlement.reset()">复位</button>
                </div>

                <div class="sp-stats">
                    <div><span>最大沉降</span><b>{{ settlement.maxSubsidenceM.toFixed(3) }} m</b></div>
                    <div><span>最大水平</span><b>{{ settlement.maxHorizontalM.toFixed(3) }} m</b></div>
                    <div><span>当前显示高差</span><b>{{ Math.round(settlement.visibleDropDisplayUnits) }}</b></div>
                </div>

                <p class="sp-note">
                    数据为真实米制（未夸大）。场景竖向已 ×{{ settlement.displayZScale }}，
                    再叠加沉陷夸大 <b>{{ settlement.exaggeration }}×</b>，
                    即沉降在图上被放大约
                    <b>{{ settlement.displayZScale * settlement.exaggeration }}×</b>。
                    <span v-if="!settlement.workingsFollow">
                        巷道与工作面属独立系统，<b>不随沉陷移动</b>。
                    </span>
                </p>
                <p v-if="settlement.enabled && !settlement.boundLayers" class="sp-warn">
                    尚未绑定到任何地层：请先加载地层模型。
                </p>
            </template>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useSettlementStore, type SettlementColorMode } from '@/stores/settlementStore'

const settlement = useSettlementStore()
const open = ref(true)

const colorModes: Array<{ value: SettlementColorMode; label: string }> = [
    { value: 'original', label: '地层色' },
    { value: 'dz', label: '沉降量' },
    { value: 'magnitude', label: '位移幅值' },
]

async function onToggle(value: boolean | string | number) {
    // 仅写入意图;真正的位移场拉取与几何挂载由 SceneCanvas 监听 enabled 后完成。
    settlement.enabled = Boolean(value)
}
</script>

<style scoped>
.settlement-panel{position:absolute;top:12px;right:12px;width:268px;background:rgba(16,20,17,.94);border:1px solid var(--studio-border);backdrop-filter:blur(6px);pointer-events:auto;z-index:6}
.settlement-panel.active{border-color:var(--studio-copper)}
.sp-head{width:100%;height:32px;display:flex;align-items:center;gap:6px;padding:0 9px;border:0;border-bottom:1px solid var(--studio-border);background:transparent;color:#c9cec7;cursor:pointer}
.settlement-panel.collapsed .sp-head{border-bottom:0}
.sp-tag{font:8px Bahnschrift;letter-spacing:.14em;color:var(--studio-copper)}
.sp-head b{font-size:11px;font-weight:400}
.sp-live{margin-left:auto;font:8px Bahnschrift;color:#7fbf7f}
.sp-caret{margin-left:auto;color:#6b756d;font-size:11px}
.sp-live + .sp-caret{margin-left:6px}
.sp-body{padding:10px 11px 11px}
.sp-switch{display:flex;align-items:center;gap:8px;margin-bottom:11px;font-size:11px;color:#a8b0a9}
.sp-switch b{margin-left:auto;font:9px Bahnschrift;color:var(--studio-copper)}
.sp-row{display:flex;justify-content:space-between;align-items:center;font-size:10px;color:#7d867e;margin-top:4px}
.sp-row b{font:10px Bahnschrift;color:#c38c4c}
.sp-modes{margin-top:9px}
.sp-buttons{display:flex;gap:3px}
.sp-buttons button{border:1px solid #2b322c;background:#151a16;color:#79837b;font-size:9px;padding:3px 6px;cursor:pointer}
.sp-buttons button.on{color:#dfd9ca;border-color:var(--studio-copper);background:#1d2320}
.sp-buttons button:disabled{opacity:.45;cursor:default}
.sp-actions{display:flex;gap:4px;margin:11px 0 9px}
.sp-actions button{flex:1;border:1px solid #2b322c;background:#151a16;color:#98a29a;font-size:10px;padding:5px 0;cursor:pointer}
.sp-actions button:hover:not(:disabled){border-color:var(--studio-copper);color:#dfd9ca}
.sp-actions button:disabled{opacity:.45;cursor:default}
.sp-stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:var(--studio-border);border:1px solid var(--studio-border)}
.sp-stats div{background:#151a16;padding:6px;display:flex;flex-direction:column;gap:2px}
.sp-stats span{font-size:8px;color:#6b756d}
.sp-stats b{font:11px Bahnschrift;color:#d8d6cc}
.sp-note{margin:10px 0 0;font-size:9px;line-height:1.6;color:#69736b}
.sp-note b{color:#c38c4c}
.sp-warn{margin:7px 0 0;font-size:9px;color:#c98a6a}
.sp-error{margin:0;font-size:10px;color:#cf7a5a;line-height:1.6}
</style>
