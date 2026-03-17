<template>
    <div ref="chartRef" class="stats-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ChartOption = Record<string, any>

const props = defineProps<{
    option: ChartOption
    loading?: boolean
}>()

const emit = defineEmits<{
    (e: 'itemClick', params: any): void
}>()

const chartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

onMounted(() => {
    if (!chartRef.value) return
    chart = echarts.init(chartRef.value)
    chart.on('click', (params: any) => emit('itemClick', params))
    if (props.option) chart.setOption(props.option)
    window.addEventListener('resize', () => chart?.resize())
})

watch(() => props.option, (val) => {
    if (val && chart) chart.setOption(val, true)
}, { deep: true })

watch(() => props.loading, (val) => {
    if (chart) {
        val ? chart.showLoading({ textColor: '#e8f4ff', maskColor: 'rgba(10,22,40,0.8)' }) : chart.hideLoading()
    }
})

onUnmounted(() => {
    chart?.dispose()
    window.removeEventListener('resize', () => chart?.resize())
})
</script>

<style scoped>
.stats-chart {
    width: 100%;
    height: 100%;
}
</style>
