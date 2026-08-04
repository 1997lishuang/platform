<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h2>计价批次</h2>
        <p>查看清单计价批次、命中明细、待补价项和最近完成时间。</p>
      </div>
      <button class="secondary" @click="loadRuns"><RefreshCw :size="17" />刷新</button>
    </div>

    <section class="panel">
      <table class="run-table">
        <thead>
          <tr>
            <th>批次号</th>
            <th>项目</th>
            <th>地区</th>
            <th>清单项</th>
            <th>已取价</th>
            <th>待补价</th>
            <th>创建时间</th>
            <th>更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="run in runs" :key="run.run_code">
            <td>
              <button class="batch-link" @click="openRun(run.run_code)">
                {{ run.run_code }}
              </button>
            </td>
            <td>{{ run.project_name || '-' }}</td>
            <td>{{ regionLabel(run.region_code) }}</td>
            <td>{{ run.item_count }}</td>
            <td><span class="metric good">{{ run.priced_count }}</span></td>
            <td><span class="metric warn">{{ run.unpriced_count }}</span></td>
            <td>{{ formatDate(run.created_at) }}</td>
            <td>{{ formatDate(run.updated_at) }}</td>
            <td>
              <div class="action-cell">
                <button class="small-action" :disabled="downloadingCode === run.run_code" @click="downloadRun(run.run_code)">
                  <Download :size="15" />
                  下载
                </button>
                <button class="danger-text" :disabled="deletingCode === run.run_code" @click="removeRun(run)">
                  <Trash2 :size="15" />
                  删除
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="runs.length === 0">
            <td colspan="9" class="empty-row">暂无批次记录</td>
          </tr>
        </tbody>
      </table>
    </section>

    <div v-if="selectedRun" class="modal-backdrop" @click.self="closeDetail">
      <section class="run-detail-modal">
        <header class="run-detail-header">
          <div>
            <span class="eyebrow">批次详情</span>
            <h3>{{ selectedRun.run_code }}</h3>
            <p>{{ selectedRun.workbook_name }}</p>
          </div>
          <div class="modal-actions">
            <button class="secondary" :disabled="downloadingCode === selectedRun.run_code" @click="downloadRun(selectedRun.run_code)">
              <Download :size="16" />
              下载结果
            </button>
            <button class="icon-button" @click="closeDetail"><X :size="18" /></button>
          </div>
        </header>

        <div class="run-summary">
          <div>
            <span>项目</span>
            <strong>{{ selectedRun.project_name || '-' }}</strong>
          </div>
          <div>
            <span>地区</span>
            <strong>{{ regionLabel(selectedRun.region_code) }}</strong>
          </div>
          <div>
            <span>规则版本</span>
            <strong>{{ selectedRun.rule_version || '全部可用版本' }}</strong>
          </div>
          <div>
            <span>创建时间</span>
            <strong>{{ formatDate(selectedRun.created_at) }}</strong>
          </div>
          <div>
            <span>更新时间</span>
            <strong>{{ formatDate(selectedRun.updated_at) }}</strong>
          </div>
          <div class="summary-number">
            <span>清单项</span>
            <strong>{{ selectedRun.item_count }}</strong>
          </div>
          <div class="summary-number">
            <span>已取价</span>
            <strong>{{ selectedRun.priced_count }}</strong>
          </div>
          <div class="summary-number">
            <span>待补价</span>
            <strong>{{ selectedRun.unpriced_count }}</strong>
          </div>
        </div>

        <div class="run-detail-tools">
          <label class="search-box">
            <Search :size="16" />
            <input v-model="detailKeyword" placeholder="搜索项目名称、Sheet、行号、规则号、说明" />
          </label>
          <select v-model="detailStatus">
            <option value="all">全部明细</option>
            <option value="priced">只看已取价</option>
            <option value="unpriced">只看待补价</option>
            <option value="issue">只看有说明</option>
          </select>
          <span class="result-count">{{ filteredResults.length }} / {{ selectedRun.results.length }} 条</span>
        </div>

        <div class="run-result-table-wrap">
          <table class="run-result-table">
            <thead>
              <tr>
                <th>定位</th>
                <th>项目名称</th>
                <th>单位</th>
                <th>工程量</th>
                <th>单价</th>
                <th>合价</th>
                <th>规则</th>
                <th>状态</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pagedResults" :key="`${item.source_sheet}-${item.source_row_number}`">
                <td>
                  <div class="cell-stack">
                    <strong>{{ item.source_sheet }}</strong>
                    <span>第 {{ item.source_row_number }} 行</span>
                  </div>
                </td>
                <td class="item-name">
                  <div class="cell-stack item-identity">
                    <strong>{{ item.item_name }}</strong>
                    <span>{{ itemIdentity(item) }}</span>
                    <span v-if="featureSummary(item)" class="feature-preview">{{ featureSummary(item) }}</span>
                  </div>
                </td>
                <td>{{ item.unit || '-' }}</td>
                <td>{{ item.quantity || '-' }}</td>
                <td>{{ item.unit_price || '-' }}</td>
                <td>{{ item.total_price || '-' }}</td>
                <td>
                  <div class="cell-stack">
                    <strong>{{ item.rule_code || '-' }}</strong>
                    <span>{{ item.rule_version || '' }}</span>
                  </div>
                </td>
                <td>
                  <span class="status-badge" :data-status="item.unit_price ? 'priced' : 'unpriced'">
                    {{ item.unit_price ? '已取价' : '待补价' }}
                  </span>
                </td>
                <td class="issue-cell">{{ item.issues.length ? item.issues.join('；') : '已匹配' }}</td>
              </tr>
              <tr v-if="pagedResults.length === 0">
                <td colspan="9" class="empty-row">没有符合筛选条件的明细</td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="run-detail-footer">
          <span>第 {{ detailPage }} / {{ detailPageCount }} 页，每页 {{ detailPageSize }} 条</span>
          <div class="pager-actions">
            <button class="secondary" :disabled="detailPage <= 1" @click="detailPage -= 1">上一页</button>
            <button class="secondary" :disabled="detailPage >= detailPageCount" @click="detailPage += 1">下一页</button>
          </div>
        </footer>
      </section>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { Download, RefreshCw, Search, Trash2, X } from '@lucide/vue'
import { computed, onMounted, ref, watch } from 'vue'
import {
  deleteRun,
  downloadRunExcel,
  fetchRunDetail,
  fetchRuns,
  type PricingRunDetail,
  type PricingRunSummary
} from '../api/client'
import { regionLabel } from '../regionOptions'

const runs = ref<PricingRunSummary[]>([])
const selectedRun = ref<PricingRunDetail | null>(null)
const deletingCode = ref('')
const downloadingCode = ref('')
const error = ref('')
const detailKeyword = ref('')
const detailStatus = ref<'all' | 'priced' | 'unpriced' | 'issue'>('all')
const detailPage = ref(1)
const detailPageSize = 20

const filteredResults = computed(() => {
  const source = selectedRun.value?.results || []
  const keyword = detailKeyword.value.trim().toLowerCase()
  return source.filter((item) => {
    const matchesStatus =
      detailStatus.value === 'all' ||
      (detailStatus.value === 'priced' && Boolean(item.unit_price)) ||
      (detailStatus.value === 'unpriced' && !item.unit_price) ||
      (detailStatus.value === 'issue' && item.issues.length > 0)
    if (!matchesStatus) return false
    if (!keyword) return true
    const haystack = [
      item.source_sheet,
      String(item.source_row_number),
      item.sequence_no || '',
      item.item_code || '',
      item.item_name,
      item.unit || '',
      item.rule_code || '',
      item.rule_version || '',
      item.price_source || '',
      item.issues.join('；'),
      JSON.stringify(item.features)
    ]
      .join(' ')
      .toLowerCase()
    return haystack.includes(keyword)
  })
})

const detailPageCount = computed(() => Math.max(1, Math.ceil(filteredResults.value.length / detailPageSize)))

const pagedResults = computed(() => {
  const start = (detailPage.value - 1) * detailPageSize
  return filteredResults.value.slice(start, start + detailPageSize)
})

async function loadRuns() {
  error.value = ''
  try {
    runs.value = await fetchRuns()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '批次列表加载失败'
  }
}

async function openRun(runCode: string) {
  error.value = ''
  try {
    selectedRun.value = await fetchRunDetail(runCode)
    resetDetailFilters()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '批次详情加载失败'
  }
}

function closeDetail() {
  selectedRun.value = null
  resetDetailFilters()
}

function resetDetailFilters() {
  detailKeyword.value = ''
  detailStatus.value = 'all'
  detailPage.value = 1
}

function itemIdentity(item: { sequence_no: string | null; item_code: string | null; source_row_number: number }) {
  const parts = []
  if (item.sequence_no) parts.push(`序号 ${item.sequence_no}`)
  if (item.item_code) parts.push(`编码 ${item.item_code}`)
  if (!parts.length) parts.push(`第 ${item.source_row_number} 行`)
  return parts.join(' / ')
}

function featureSummary(item: { features: Record<string, unknown> }) {
  const entries = Object.entries(item.features || {}).filter(([, value]) => value !== null && value !== undefined && value !== '')
  const text = entries.map(([key, value]) => `${key}=${String(value)}`).join('；')
  return text.length > 120 ? `${text.slice(0, 120)}...` : text
}

async function downloadRun(runCode: string) {
  downloadingCode.value = runCode
  error.value = ''
  try {
    const response = await downloadRunExcel(runCode)
    const filename = filenameFromDisposition(response.headers['content-disposition']) || `${runCode}-计价结果.xlsx`
    const url = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '结果文件下载失败'
  } finally {
    downloadingCode.value = ''
  }
}

function filenameFromDisposition(disposition: string | undefined) {
  if (!disposition) return ''
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1])
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i)
  return plainMatch?.[1] || ''
}

async function removeRun(run: PricingRunSummary) {
  const confirmed = window.confirm(`确认删除批次 ${run.run_code} 及其关联明细和任务记录？此操作不可恢复。`)
  if (!confirmed) return
  deletingCode.value = run.run_code
  error.value = ''
  try {
    await deleteRun(run.run_code)
    if (selectedRun.value?.run_code === run.run_code) {
      selectedRun.value = null
    }
    await loadRuns()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '批次删除失败'
  } finally {
    deletingCode.value = ''
  }
}

function formatDate(value: string | null | undefined) {
  return value ? value.replace('T', ' ').slice(0, 19) : '-'
}

onMounted(loadRuns)

watch([detailKeyword, detailStatus], () => {
  detailPage.value = 1
})

watch(detailPageCount, (pageCount) => {
  if (detailPage.value > pageCount) {
    detailPage.value = pageCount
  }
})
</script>
