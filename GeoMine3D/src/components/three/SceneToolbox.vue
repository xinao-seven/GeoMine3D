<template>
    <div class="toolbox" :class="{ 'is-collapsed': collapsed }">
        <!-- 竖排导轨 -->
        <nav class="tb-rail">
            <button class="tb-rail-toggle" :title="collapsed ? '展开工具箱' : '收起工具箱'" @click="collapsed = !collapsed">
                <el-icon><component :is="collapsed ? 'DArrowLeft' : 'DArrowRight'" /></el-icon>
            </button>

            <button
                v-for="group in groups"
                :key="group.key"
                class="tb-rail-btn"
                :class="{ active: openKey === group.key && !collapsed, engaged: group.engaged }"
                :title="group.label"
                @click="toggleGroup(group.key)"
            >
                <el-icon><component :is="group.icon" /></el-icon>
                <i v-if="group.engaged" class="tb-dot"></i>
            </button>
        </nav>

        <!-- 展开的功能页 -->
        <section v-if="!collapsed && current" class="tb-page">
            <header class="tb-page-head">
                <span>{{ current.label }}</span>
                <button title="关闭" @click="openKey = ''">
                    <el-icon><Close /></el-icon>
                </button>
            </header>

            <div class="tb-page-body">
                <template v-for="(c, i) in current.controls" :key="`${groupKey(c, i)}`">
                    <!-- 动作按钮 -->
                    <button
                        v-if="c.kind === 'action'"
                        class="tb-action"
                        :class="{ primary: c.primary }"
                        :disabled="c.disabled"
                        @click="emitTool(c.event)"
                    >
                        <el-icon v-if="c.icon"><component :is="c.icon" /></el-icon>
                        <span>{{ c.label }}</span>
                        <kbd v-if="c.shortcut">{{ c.shortcut }}</kbd>
                    </button>

                    <!-- 开关 -->
                    <label v-else-if="c.kind === 'switch'" class="tb-switch">
                        <span>{{ c.label }}</span>
                        <el-switch
                            :model-value="c.value"
                            :disabled="c.disabled"
                            inline-prompt
                            active-text="开"
                            inactive-text="关"
                            @update:model-value="(v: boolean | string | number) => emitTool(c.event, Boolean(v))"
                        />
                    </label>

                    <!-- 滑块 -->
                    <div v-else-if="c.kind === 'slider'" class="tb-slider" :class="{ disabled: c.disabled }">
                        <div class="tb-row"><span>{{ c.label }}</span><b>{{ c.display }}</b></div>
                        <el-slider
                            :model-value="c.value"
                            :min="c.min" :max="c.max" :step="c.step"
                            :disabled="c.disabled"
                            :show-tooltip="false"
                            @update:model-value="(v: number | number[]) => emitTool(c.event, Number(v))"
                        />
                    </div>

                    <!-- 分段选择 -->
                    <div v-else-if="c.kind === 'segment'" class="tb-segment" :class="{ disabled: c.disabled }">
                        <span class="tb-seg-label">{{ c.label }}</span>
                        <div class="tb-seg-buttons">
                            <button
                                v-for="o in c.options"
                                :key="o.value"
                                :class="{ on: c.value === o.value }"
                                :disabled="c.disabled"
                                @click="emitTool(c.event, o.value)"
                            >{{ o.label }}</button>
                        </div>
                    </div>

                    <!-- 读数网格 -->
                    <div v-else-if="c.kind === 'stats'" class="tb-stats">
                        <div v-for="it in c.items" :key="it.label">
                            <span>{{ it.label }}</span><b>{{ it.value }}</b>
                        </div>
                    </div>

                    <!-- 单行读数 -->
                    <div v-else-if="c.kind === 'readout'" class="tb-readout">
                        <span>{{ c.label }}</span><b>{{ c.value }}</b>
                    </div>

                    <!-- 说明文字 -->
                    <p v-else-if="c.kind === 'note'" class="tb-note" :class="{ warn: c.warn }" v-html="c.text"></p>
                </template>
            </div>
        </section>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

/** 控件描述:工具箱是纯展示组件,所有状态与动作都由宿主(SceneCanvas)提供 */
export type ToolControl =
    | { kind: 'action'; label: string; icon?: string; event: string; primary?: boolean; shortcut?: string; disabled?: boolean }
    | { kind: 'switch'; label: string; value: boolean; event: string; disabled?: boolean }
    | { kind: 'slider'; label: string; value: number; display: string; min: number; max: number; step: number; event: string; disabled?: boolean }
    | { kind: 'segment'; label: string; value: string; options: Array<{ value: string; label: string }>; event: string; disabled?: boolean }
    | { kind: 'stats'; items: Array<{ label: string; value: string }> }
    | { kind: 'readout'; label: string; value: string }
    | { kind: 'note'; text: string; warn?: boolean }

export interface ToolGroup {
    key: string
    label: string
    icon: string
    /** 该组里有工具处于激活态 → 导轨按钮显示小圆点 */
    engaged?: boolean
    controls: ToolControl[]
}

const props = defineProps<{ groups: ToolGroup[]; initial?: string }>()
const emit = defineEmits<{ (e: 'tool', event: string, payload?: any): void }>()

const collapsed = ref(false)
const openKey = ref(props.initial ?? '')
const current = computed(() => props.groups.find(g => g.key === openKey.value))

// 分组是宿主算出来的;若当前分组消失(例如面板被裁掉)则自动收起
watch(() => props.groups, (list) => {
    if (openKey.value && !list.some(g => g.key === openKey.value)) openKey.value = ''
})

function toggleGroup(key: string) {
    if (collapsed.value) collapsed.value = false
    openKey.value = openKey.value === key ? '' : key
}

function emitTool(event: string, payload?: any) {
    emit('tool', event, payload)
}

function groupKey(c: ToolControl, i: number) {
    return `${c.kind}-${i}-${'label' in c ? c.label : ''}`
}
</script>

<style scoped>
.toolbox{position:absolute;top:14px;right:12px;display:flex;align-items:flex-start;gap:0;z-index:8;pointer-events:none}
.toolbox > *{pointer-events:auto}

/* ---------------- 导轨 ---------------- */
.tb-rail{width:40px;display:flex;flex-direction:column;align-items:center;gap:2px;padding:4px 0;
  background:rgba(16,21,17,.94);border:1px solid #333c34;backdrop-filter:blur(8px);
  box-shadow:0 12px 32px rgba(0,0,0,.35);border-radius:2px}
.tb-rail-toggle{width:30px;height:26px;margin-bottom:3px;border:0;border-bottom:1px solid #2b322c;
  background:transparent;color:#6b756d;cursor:pointer;display:grid;place-items:center}
.tb-rail-toggle:hover{color:#d7d4ca}
.tb-rail-btn{position:relative;width:30px;height:30px;border:0;border-left:2px solid transparent;
  background:transparent;color:#79837b;cursor:pointer;display:grid;place-items:center;font-size:14px}
.tb-rail-btn:hover{color:#dfd9ca;background:#1b211c}
.tb-rail-btn.active{color:#e2c79a;background:#1d2320;border-left-color:var(--studio-copper)}
.tb-rail-btn.engaged{color:#d7b483}
.tb-dot{position:absolute;right:4px;top:5px;width:4px;height:4px;border-radius:50%;background:var(--studio-copper)}

/* ---------------- 功能页 ---------------- */
.tb-page{width:252px;max-height:calc(100vh - 140px);margin-right:6px;display:flex;flex-direction:column;
  background:rgba(16,21,17,.96);border:1px solid #333c34;backdrop-filter:blur(10px);
  box-shadow:0 12px 32px rgba(0,0,0,.4);border-radius:2px}
.tb-page-head{flex:none;height:32px;display:flex;align-items:center;justify-content:space-between;
  padding:0 6px 0 11px;border-bottom:1px solid #2b322c}
.tb-page-head span{font:9px Bahnschrift;letter-spacing:.16em;color:var(--studio-copper);text-transform:uppercase}
.tb-page-head button{width:24px;height:24px;border:0;background:transparent;color:#6b756d;cursor:pointer;display:grid;place-items:center}
.tb-page-head button:hover{color:#d7d4ca}
.tb-page-body{flex:1;min-height:0;overflow-y:auto;padding:10px 11px 12px}

/* 动作 */
.tb-action{width:100%;height:32px;display:flex;align-items:center;gap:8px;padding:0 10px;margin-bottom:6px;
  border:1px solid #333c34;background:#181e19;color:#b3bcb4;font-size:11px;cursor:pointer;border-radius:1px}
.tb-action:hover:not(:disabled){border-color:var(--studio-copper);color:#e6e1d4}
.tb-action.primary{border-color:#60492a;color:#d5a468;background:#1d1a13}
.tb-action:disabled{opacity:.42;cursor:default}
.tb-action span{flex:1;text-align:left}
.tb-action kbd{font:9px Bahnschrift;color:#5d675f;border:1px solid #313832;padding:1px 4px}

/* 开关 */
.tb-switch{display:flex;align-items:center;justify-content:space-between;gap:8px;
  padding:7px 0;font-size:11px;color:#9aa39b}
.tb-switch + .tb-switch{border-top:1px solid #232a24}

/* 滑块 */
.tb-slider{margin:9px 0 4px}
.tb-slider.disabled{opacity:.45}
.tb-row{display:flex;justify-content:space-between;align-items:baseline;font-size:10px;color:#7d867e}
.tb-row b{font:10px Bahnschrift;color:#c38c4c}

/* 分段 */
.tb-segment{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:9px 0;font-size:10px;color:#7d867e}
.tb-segment.disabled{opacity:.45}
.tb-seg-buttons{display:flex;gap:3px}
.tb-seg-buttons button{min-width:26px;padding:3px 7px;border:1px solid #2b322c;background:#151a16;
  color:#79837b;font-size:9px;cursor:pointer}
.tb-seg-buttons button.on{color:#dfd9ca;border-color:var(--studio-copper);background:#1d2320}
.tb-seg-buttons button:disabled{opacity:.45;cursor:default}

/* 读数 */
.tb-stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;margin-top:10px;
  background:#252c26;border:1px solid #2b322c}
.tb-stats div{padding:6px;background:#151a16;display:flex;flex-direction:column;gap:2px}
.tb-stats span{font-size:8px;color:#6b756d}
.tb-stats b{font:11px Bahnschrift;color:#d8d6cc}
.tb-readout{display:flex;justify-content:space-between;align-items:baseline;margin-top:8px;font-size:10px;color:#7d867e}
.tb-readout b{font:11px Bahnschrift;color:#c38c4c}

/* 说明 */
.tb-note{margin:10px 0 0;font-size:9px;line-height:1.65;color:#69736b}
.tb-note :deep(b){color:#c38c4c}
.tb-note.warn{color:#c98a6a}
.tb-note.warn :deep(b){color:#e0a077}
</style>
