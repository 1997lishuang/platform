<template>
  <section class="page-stack">
    <div class="panel monitor-hero">
      <div>
        <h2>模型调用监控</h2>
        <p>实时查看第三方询价接口调用状态、耗时和 Token 用量，便于控制成本与排查失败原因。</p>
      </div>
      <div class="monitor-actions">
        <select v-model="statusFilter" class="compact-select" @change="reloadFirstPage">
          <option value="">全部状态</option>
          <option value="running">调用中</option>
          <option value="succeeded">成功</option>
          <option value="failed">失败</option>
        </select>
        <label class="inline-switch">
          <input v-model="autoRefresh" type="checkbox" />
          自动刷新
        </label>
        <button class="secondary-button" @click="loadLogs()">
          <RefreshCw :size="17" />
          刷新
        </button>
      </div>
    </div>

    <div class="metric-grid">
      <div class="metric-card">
        <span>当前页调用</span>
        <strong>{{ logs.length }}</strong>
      </div>
      <div class="metric-card">
        <span>调用中</span>
        <strong>{{ runningCount }}</strong>
      </div>
      <div class="metric-card">
        <span>成功</span>
        <strong>{{ succeededCount }}</strong>
      </div>
      <div class="metric-card">
        <span>当前页 Token</span>
        <strong>{{ pageTokens }}</strong>
      </div>
    </div>

    <div class="panel">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>场景</th>
              <th>询价对象</th>
              <th>平台/模型</th>
              <th>Token</th>
              <th>耗时</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading && logs.length === 0">
              <td colspan="7" class="muted-cell">正在加载调用记录...</td>
            </tr>
            <tr v-else-if="logs.length === 0">
              <td colspan="7" class="muted-cell">暂无调用记录</td>
            </tr>
            <tr v-for="item in logs" :key="item.call_code">
              <td>
                <div>{{ formatDate(item.created_at) }}</div>
                <small v-if="item.task_code">任务 {{ shortCode(item.task_code) }}</small>
              </td>
              <td>{{ scenarioLabel(item.scenario) }}</td>
              <td>
                <strong>{{ item.item_name || '-' }}</strong>
                <small v-if="item.created_by">触发人：{{ item.created_by }}</small>
              </td>
              <td>
                <div>{{ providerLabel(item.provider) }}</div>
                <small>{{ item.model }}</small>
              </td>
              <td>
                <div class="token-line">总计 {{ item.total_tokens ?? '-' }}</div>
                <small>输入 {{ item.prompt_tokens ?? '-' }} / 输出 {{ item.completion_tokens ?? '-' }}</small>
              </td>
              <td>{{ item.duration_ms == null ? '-' : `${item.duration_ms} ms` }}</td>
              <td>
                <span :class="['status-pill', item.status]">{{ statusLabel(item.status) }}</span>
                <small v-if="item.error_message" class="error-text">{{ item.error_message }}</small>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pager">
        <span>共 {{ total }} 条，第 {{ page }} / {{ totalPages }} 页</span>
        <div>
          <button class="secondary-button" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
          <button class="secondary-button" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RefreshCw } from '@lucide/vue'
import { fetchModelCallLogPage, type ModelCallLogSummary } from '../api/client'

const logs = ref<ModelCallLogSummary[]>([])
const loading = ref(false)
const statusFilter = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const autoRefresh = ref(true)
const lastUpdated = ref('')
let timer: number | undefined
let requestInFlight = false

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const runningCount = computed(() => logs.value.filter((item) => item.status === 'running').length)
const succeededCount = computed(() => logs.value.filter((item) => item.status === 'succeeded').length)
const pageTokens = computed(() => logs.value.reduce((sum, item) => sum + (item.total_tokens || 0), 0))

async function loadLogs(options: { silent?: boolean } = {}) {
  if (requestInFlight) return
  requestInFlight = true
  if (!options.silent) loading.value = true
  try {
    const result = await fetchModelCallLogPage({
      status: statusFilter.value || undefined,
      page: page.value,
      page_size: pageSize
    })
    logs.value = result.items
    total.value = result.total
    lastUpdated.value = new Date().toLocaleTimeString()
  } finally {
    requestInFlight = false
    if (!options.silent) loading.value = false
  }
}

function reloadFirstPage() {
  page.value = 1
  loadLogs()
}

function changePage(nextPage: number) {
  page.value = nextPage
  loadLogs()
}

function statusLabel(status: string) {
  if (status === 'running') return '调用中'
  if (status === 'succeeded') return '成功'
  if (status === 'failed') return '失败'
  return status
}

function scenarioLabel(scenario: string) {
  if (scenario === 'single_market_quote') return '单项询价'
  if (scenario === 'excel_market_quote') return 'Excel 批量询价'
  if (scenario === 'pricing_auto_market_quote') return '计价自动询价'
  return scenario
}

function providerLabel(provider: string) {
  if (provider === 'doubao') return '豆包/火山方舟'
  if (provider === 'closeai') return 'CloseAI'
  if (provider === 'local') return '本地模型'
  return provider
}

function shortCode(value: string) {
  return value.length > 12 ? `${value.slice(0, 12)}...` : value
}

function formatDate(value: string) {
  return value?.replace('T', ' ').slice(0, 19)
}

onMounted(() => {
  loadLogs()
  timer = window.setInterval(() => {
    if (autoRefresh.value) {
      loadLogs({ silent: true })
    }
  }, 5000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>
