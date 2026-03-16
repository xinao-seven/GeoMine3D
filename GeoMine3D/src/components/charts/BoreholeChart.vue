<template>
  <div ref="chartRef" class="borehole-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { BoreholeDetail } from '@/types'

const props = defineProps<{
  borehole: BoreholeDetail | null
}>()

const emit = defineEmits<{
  (e: 'layerClick', layerName: string): void
}>()

const chartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function buildOption(borehole: BoreholeDetail) {
  const layers = [...borehole.layers].reverse()
  const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452']

  return {
    backgroundColor: 'transparent',
    title: {
      text: borehole.name,
      textStyle: { color: '#e8f4ff', fontSize: 13 },
      left: 'center',
      top: 4,
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const l = params.data.layer
        return `<b>${l.layerName}</b><br/>顶深: ${l.topDepth}m<br/>底深: ${l.bottomDepth}m<br/>厚度: ${l.thickness}m`
      },
    },
    grid: { left: 60, right: 20, top: 40, bottom: 20 },
    xAxis: {
      type: 'value',
      show: false,
      max: 1,
    },
    yAxis: {
      type: 'value',
      inverse: true,
      axisLabel: { color: '#8ab4d4', fontSize: 11, formatter: (v: number) => `${v}m` },
      axisLine: { lineStyle: { color: '#1e3a5f' } },
      splitLine: { lineStyle: { color: '#1e3a5f' } },
      min: 0,
      max: borehole.totalDepth,
    },
    series: [
      {
        type: 'custom',
        renderItem: (params: any, api: any) => {
          const layerIdx = params.dataIndex
          const layer = layers[layerIdx]
          const y0 = api.coord([0, layer.topDepth])
          const y1 = api.coord([0, layer.bottomDepth])
          return {
            type: 'rect',
            shape: {
              x: params.coordSys.x + 10,
              y: y0[1],
              width: params.coordSys.width - 20,
              height: Math.max(1, y1[1] - y0[1]),
            },
            style: {
              fill: colors[layerIdx % colors.length],
              opacity: 0.85,
            },
          }
        },
        data: layers.map((l, i) => ({ value: [0, l.topDepth], layer: l, itemStyle: { color: colors[i % colors.length] } })),
        encode: { y: 1 },
      },
    ],
  }
}

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  chart.on('click', (params: any) => {
    if (params.data?.layer) {
      emit('layerClick', params.data.layer.layerName)
    }
  })
}

watch(() => props.borehole, (val) => {
  if (val && chart) {
    chart.setOption(buildOption(val), true)
  }
}, { immediate: true })

onMounted(() => {
  initChart()
  if (props.borehole && chart) {
    chart.setOption(buildOption(props.borehole), true)
  }
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
})
</script>

<style scoped>
.borehole-chart {
  width: 100%;
  height: 100%;
  min-height: 300px;
}
</style>
