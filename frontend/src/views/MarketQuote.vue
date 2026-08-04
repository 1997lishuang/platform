<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h2>市场询价</h2>
        <p>通过模型检索公开市场参考价，结果进入待复核区，不能直接覆盖正式规则。</p>
      </div>
      <div class="header-actions">
        <button class="secondary" @click="loadQuotes">
          刷新价格库
        </button>
        <button class="primary" :disabled="quoteSubmitDisabled" @click="estimate">
          <Search :size="17" />
          {{ loading ? '询价中' : '获取参考价' }}
        </button>
      </div>
    </div>

    <section v-if="taskCode" class="panel attention-panel">
      <div class="section-head">
        <div>
          <h3>当前计价任务缺价项</h3>
          <p class="field-hint">选择一个缺价清单项后点击“获取参考价”，生成的复核记录会关联原计价任务；复核通过后可回工作台恢复计价。</p>
        </div>
        <div class="task-actions">
          <button class="secondary" @click="taskTargetsCollapsed = !taskTargetsCollapsed">
            {{ taskTargetsCollapsed ? '展开缺价项' : '折叠缺价项' }}
          </button>
          <button class="secondary" @click="loadTaskTargets">刷新缺价项</button>
        </div>
      </div>
      <div v-if="!taskTargetsCollapsed" class="bulk-toolbar">
        <span>已选择 {{ selectedTaskTargetKeys.length }} 项</span>
        <button class="small-action" :disabled="batchLoading || selectedTaskTargetKeys.length === 0" @click="estimateSelectedTargets">
          {{ batchLoading ? '批量询价中' : '批量询价' }}
        </button>
      </div>
      <table v-if="!taskTargetsCollapsed">
        <thead>
          <tr>
            <th class="select-col">选择</th>
            <th>清单项</th>
            <th>单位</th>
            <th>工程量</th>
            <th>特征</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="target in pagedTaskTargets"
            :key="targetKey(target)"
            :class="{ 'selected-row': selectedTargetKey === targetKey(target), 'submitted-row': isTargetSubmitted(target) }"
          >
            <td class="select-col">
              <input
                type="checkbox"
                :checked="selectedTaskTargetKeys.includes(targetKey(target))"
                :disabled="isTargetSubmitted(target) || loading || batchLoading"
                @change="toggleTaskTargetSelection(target)"
              />
            </td>
            <td>
              <strong>{{ target.item_name }}</strong>
              <div class="muted">{{ target.source_sheet }} / 第 {{ target.source_row_number }} 行</div>
            </td>
            <td>{{ target.unit || '-' }}</td>
            <td>{{ target.quantity || '-' }}</td>
            <td class="conditions-cell">{{ formatTargetFeatures(target.features) }}</td>
            <td>
              <button class="small-action" :disabled="isTargetSubmitted(target)" @click="useTaskTarget(target)">
                {{ selectedTargetKey === targetKey(target) ? '已填入' : '填入询价' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!taskTargetsCollapsed && taskTargets.length > taskTargetPageSize" class="pager">
        <span>共 {{ taskTargets.length }} 项，第 {{ taskTargetPage }} / {{ taskTargetTotalPages }} 页</span>
        <div>
          <button class="secondary" :disabled="taskTargetPage <= 1" @click="changeTaskTargetPage(taskTargetPage - 1)">上一页</button>
          <button class="secondary" :disabled="taskTargetPage >= taskTargetTotalPages" @click="changeTaskTargetPage(taskTargetPage + 1)">下一页</button>
        </div>
      </div>
      <p v-if="taskTargetsLoaded && !taskTargets.length" class="empty">当前任务没有可读取的缺价项。请确认任务已有批次号，或回工作台重新恢复计价。</p>
    </section>

    <section ref="quoteFormPanel" class="panel">
      <p v-if="fillMessage" class="success">{{ fillMessage }}</p>
      <h3>单项询价</h3>
      <div class="form-grid">
        <label>清单项目名称/询价对象<input v-model="form.itemName" /></label>
        <label>计量单位<input v-model="form.unit" /></label>
        <label>计价地区
          <select v-model="form.region">
            <option v-for="region in regionOptions" :key="region.code" :value="region.code">
              {{ region.name }}（{{ region.code }}） - {{ region.scope }}
            </option>
          </select>
        </label>
        <label>模型渠道
          <select v-model="form.provider">
            <option value="doubao">豆包/火山方舟</option>
            <option value="closeai">CloseAI</option>
            <option value="local">本地大模型</option>
          </select>
        </label>
        <label>价格月份<input v-model="form.priceMonth" /></label>
        <label>标准<input v-model="form.standard" /></label>
        <label>项目特征/规格参数<input v-model="form.featureText" /></label>
      </div>
      <div class="form-actions quote-form-actions">
        <span>{{ fillMessage || '确认询价对象、地区、模型渠道后获取参考价。' }}</span>
        <button class="primary" :disabled="quoteSubmitDisabled" @click="estimate">
          <Search :size="17" />
          {{ loading ? '询价中' : '获取参考价' }}
        </button>
      </div>
    </section>

    <section class="panel">
      <h3>Excel 批量询价</h3>
      <div class="form-grid">
        <label>询价表格
          <input type="file" accept=".xlsx,.xlsm" @change="onExcelChange" />
        </label>
        <label>模型渠道
          <select v-model="excelForm.provider">
            <option value="doubao">豆包/火山方舟</option>
            <option value="closeai">CloseAI</option>
            <option value="local">本地大模型</option>
          </select>
        </label>
        <label>计价地区
          <select v-model="excelForm.region">
            <option v-for="region in regionOptions" :key="region.code" :value="region.code">
              {{ region.name }}（{{ region.code }}） - {{ region.scope }}
            </option>
          </select>
        </label>
        <label>价格月份<input v-model="excelForm.priceMonth" /></label>
        <label>标准<input v-model="excelForm.standard" /></label>
        <label>最大询价行数<input v-model.number="excelForm.limit" type="number" min="1" max="200" /></label>
      </div>
      <div class="form-actions">
        <span>{{ excelFile?.name || '请选择包含项目名称、技术指标、单位、工程量的 .xlsx 文件' }}</span>
        <button class="primary" :disabled="!excelFile || excelLoading" @click="estimateExcel">
          <Search :size="17" />
          {{ excelLoading ? '批量询价中' : '上传并询价' }}
        </button>
      </div>
    </section>

    <section v-if="quote" class="result-strip">
      <div><strong>{{ quote.price_min || '-' }}</strong><span>最低参考价</span></div>
      <div><strong>{{ quote.price_max || '-' }}</strong><span>最高参考价</span></div>
      <div><strong>{{ quote.recommended_price || '-' }}</strong><span>推荐价</span></div>
      <div><strong>{{ quote.confidence }}</strong><span>置信度</span></div>
    </section>

    <section v-if="quote" class="panel">
      <h3>来源与假设</h3>
      <div class="output-list">
        <div>询价编号：{{ quote.quote_code }}</div>
        <div>模型：{{ quote.provider }} / {{ quote.model }}</div>
        <div>状态：{{ quote.status }}</div>
        <div>来源：{{ quote.source_urls.join(', ') || '-' }}</div>
        <div>假设：{{ quote.assumptions }}</div>
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <h3>价格库复核</h3>
        <select v-model="quoteStatusFilter" @change="changeQuoteStatus">
          <option value="">全部</option>
          <option value="pending_review">待复核</option>
          <option value="adopted">已采纳</option>
          <option value="rejected">已驳回</option>
        </select>
      </div>
      <table>
        <thead>
          <tr>
            <th>询价对象</th>
            <th>地区</th>
            <th>推荐价</th>
            <th>来源证据</th>
            <th>置信度</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in quoteRows" :key="item.quote_code">
            <td>
              <strong>{{ item.item_name }}</strong>
              <div class="muted">{{ item.unit || '-' }} / {{ item.provider }} / {{ item.model }}</div>
            </td>
            <td>{{ item.region_code || '-' }}</td>
            <td>{{ item.recommended_price || '-' }}</td>
            <td>
              <div class="source-list">
                <a
                  v-for="url in quoteSourceUrls(item)"
                  :key="url"
                  :href="url"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ shortUrl(url) }}
                </a>
                <span v-for="evidence in quoteEvidences(item)" :key="evidence" class="source-evidence">
                  {{ evidence }}
                </span>
                <span v-if="!quoteSourceUrls(item).length && !quoteEvidences(item).length">-</span>
              </div>
            </td>
            <td>{{ item.confidence }}</td>
            <td>{{ quoteStatusText(item.status) }}</td>
            <td class="action-cell">
              <button
                v-if="item.status === 'pending_review'"
                class="small-action"
                title="采纳"
                @click="approveQuote(item)"
              >
                采纳
              </button>
              <button
                v-if="item.status === 'pending_review'"
                class="small-action danger"
                title="驳回"
                @click="rejectQuote(item)"
              >
                驳回
              </button>
              <span v-if="item.status !== 'pending_review'" class="muted">{{ item.reviewed_by || '-' }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!quoteRows.length" class="empty">暂无记录</p>
      <div class="pager" v-if="quoteTotal > 0">
        <span>共 {{ quoteTotal }} 条，第 {{ quotePage }} / {{ quoteTotalPages }} 页</span>
        <div class="pager-actions">
          <button class="secondary" :disabled="quotePage <= 1" @click="changeQuotePage(quotePage - 1)">上一页</button>
          <button class="secondary" :disabled="quotePage >= quoteTotalPages" @click="changeQuotePage(quotePage + 1)">下一页</button>
        </div>
      </div>
    </section>

    <section v-if="excelResult" class="panel">
      <h3>Excel 询价结果</h3>
      <div class="output-list">
        <div>识别清单项：{{ excelResult.item_count }}</div>
        <div>询价成功：{{ excelResult.quoted_count }}</div>
        <div>询价失败：{{ excelResult.failed_count }}</div>
        <div>结果文件：{{ excelResult.output_path }}</div>
      </div>
    </section>

    <section v-if="excelTask" class="panel task-panel">
      <div class="task-head">
        <div>
          <h3>Excel 询价任务</h3>
          <p>{{ excelTask.message || excelStatusText }}</p>
        </div>
        <span class="status-pill" :data-status="excelTask.status">{{ excelStatusText }}</span>
      </div>
      <div class="progress-track">
        <div class="progress-bar" :style="{ width: `${excelTask.progress}%` }"></div>
      </div>
      <div class="output-list">
        <div>识别清单项：{{ excelTask.item_count }}</div>
        <div>已入库：{{ excelTask.priced_count }}</div>
        <div>询价失败：{{ excelTask.unpriced_count }}</div>
        <div v-if="excelTask.excel_path">结果文件：{{ excelTask.excel_path }}</div>
      </div>
      <div v-if="excelTask.failure_reasons.length" class="failure-list">
        <strong>失败原因</strong>
        <div v-for="reason in excelTask.failure_reasons" :key="reason">{{ reason }}</div>
      </div>
      <div class="form-actions" v-if="excelTask.status === 'pending' || excelTask.status === 'running'">
        <span>停止后会在当前行结束后中断，并保留已处理结果。</span>
        <button class="secondary danger-button" :disabled="cancelingExcelTask" @click="cancelExcelTask">
          {{ cancelingExcelTask ? '停止中' : '停止任务' }}
        </button>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { Search } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  approveMarketQuote,
  cancelMarketQuoteExcelTask,
  estimateMarketQuote,
  fetchMarketQuotePage,
  fetchMarketQuoteExcelTask,
  fetchMarketQuoteTargets,
  rejectMarketQuote,
  submitMarketQuoteExcelTask,
  type ExcelMarketQuoteResponse,
  type MarketQuoteSummary,
  type MarketQuoteTaskTarget,
  type PricingTaskStatus
} from '../api/client'
import { regionOptions } from '../regionOptions'

const loading = ref(false)
const batchLoading = ref(false)
const excelLoading = ref(false)
const cancelingExcelTask = ref(false)
const error = ref('')
const quote = ref<MarketQuoteSummary | null>(null)
const route = useRoute()
const taskCode = computed(() => String(route.query.task_code || ''))
const taskTargets = ref<MarketQuoteTaskTarget[]>([])
const taskTargetsLoaded = ref(false)
const selectedTargetKey = ref('')
const fillMessage = ref('')
const quoteFormPanel = ref<HTMLElement | null>(null)
const taskTargetsCollapsed = ref(false)
const taskTargetPage = ref(1)
const taskTargetPageSize = ref(8)
const selectedTaskTargetKeys = ref<string[]>([])
const submittedTaskTargetKeys = ref<string[]>([])
const targetQuoteMessages = ref<Record<string, string>>({})
const quoteRows = ref<MarketQuoteSummary[]>([])
const quoteStatusFilter = ref('pending_review')
const quotePage = ref(1)
const quotePageSize = ref(10)
const quoteTotal = ref(0)
const excelFile = ref<File | null>(null)
const excelResult = ref<ExcelMarketQuoteResponse | null>(null)
const excelTask = ref<PricingTaskStatus | null>(null)
let excelPollTimer: number | undefined
const form = reactive({
  itemName: '预制钢筋混凝土桩',
  unit: 'm',
  region: 'CN',
  provider: 'doubao',
  priceMonth: '2026-07',
  standard: 'GB13476-2023',
  featureText: '桩型=PHC-300-AB-70; 桩长度=8-10m; 混凝土种类与强度等级=C80'
})
const excelForm = reactive({
  provider: 'doubao',
  region: 'CN',
  priceMonth: '2026-07',
  standard: '',
  limit: 1
})
const excelStatusText = computed(() => {
  const status = excelTask.value?.status
  if (status === 'pending') return '等待处理'
  if (status === 'running') return '询价中'
  if (status === 'succeeded') return excelTask.value?.priced_count ? '已入库' : '未入库'
  if (status === 'failed') return '失败'
  if (status === 'canceled') return '已停止'
  return '未提交'
})
const quoteTotalPages = computed(() => Math.max(1, Math.ceil(quoteTotal.value / quotePageSize.value)))
const taskTargetTotalPages = computed(() => Math.max(1, Math.ceil(taskTargets.value.length / taskTargetPageSize.value)))
const pagedTaskTargets = computed(() => {
  const start = (taskTargetPage.value - 1) * taskTargetPageSize.value
  return taskTargets.value.slice(start, start + taskTargetPageSize.value)
})
const quoteSubmitDisabled = computed(() => loading.value || batchLoading.value || Boolean(selectedTargetKey.value && submittedTaskTargetKeys.value.includes(selectedTargetKey.value)))

onMounted(async () => {
  await loadQuotes()
  if (taskCode.value) await loadTaskTargets()
})

watch(
  () => route.query.task_code,
  async () => {
    selectedTargetKey.value = ''
    fillMessage.value = ''
    taskTargets.value = []
    taskTargetsLoaded.value = false
    taskTargetPage.value = 1
    selectedTaskTargetKeys.value = []
    submittedTaskTargetKeys.value = []
    targetQuoteMessages.value = {}
    if (taskCode.value) await loadTaskTargets()
  }
)

async function estimate() {
  if (selectedTargetKey.value && submittedTaskTargetKeys.value.includes(selectedTargetKey.value)) {
    fillMessage.value = '当前清单项已成功提交到价格库复核，不能重复询价。'
    return
  }
  loading.value = true
  error.value = ''
  quote.value = null
  try {
    quote.value = await estimateMarketQuote({
      provider: form.provider,
      item_name: form.itemName,
      unit: form.unit,
      region: form.region,
      price_month: form.priceMonth,
      standard: form.standard,
      features: parseFeatures(form.featureText),
      pricing_task_code: taskCode.value || undefined
    })
    markTargetSubmitted(selectedTargetKey.value, quote.value)
    await loadQuotes()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '市场询价失败'
  } finally {
    loading.value = false
  }
}

async function loadQuotes() {
  try {
    const page = await fetchMarketQuotePage({
      status: quoteStatusFilter.value,
      page: quotePage.value,
      page_size: quotePageSize.value
    })
    quoteRows.value = page.items
    quoteTotal.value = page.total
    quotePage.value = page.page
    quotePageSize.value = page.page_size
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '价格库加载失败'
  }
}

async function loadTaskTargets() {
  if (!taskCode.value) return
  taskTargetsLoaded.value = false
  try {
    taskTargets.value = await fetchMarketQuoteTargets(taskCode.value)
    taskTargetsLoaded.value = true
    taskTargetPage.value = 1
    if (taskTargets.value.length && !form.itemName) {
      useTaskTarget(taskTargets.value[0])
    }
  } catch (caught) {
    taskTargetsLoaded.value = true
    error.value = caught instanceof Error ? caught.message : '缺价清单项加载失败'
  }
}

function useTaskTarget(target: MarketQuoteTaskTarget) {
  form.itemName = target.item_name
  form.unit = target.unit || ''
  form.featureText = Object.entries(target.features || {})
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '')
    .map(([key, value]) => `${key}=${String(value)}`)
    .join('; ')
  selectedTargetKey.value = targetKey(target)
  fillMessage.value = `已填入：${target.item_name}，请点击右上角“获取参考价”。`
  window.setTimeout(() => {
    quoteFormPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, 0)
}

function targetKey(target: MarketQuoteTaskTarget) {
  return `${target.source_sheet}-${target.source_row_number}`
}

function changeTaskTargetPage(page: number) {
  taskTargetPage.value = Math.max(1, Math.min(page, taskTargetTotalPages.value))
}

function toggleTaskTargetSelection(target: MarketQuoteTaskTarget) {
  const key = targetKey(target)
  if (submittedTaskTargetKeys.value.includes(key)) return
  selectedTaskTargetKeys.value = selectedTaskTargetKeys.value.includes(key)
    ? selectedTaskTargetKeys.value.filter((item) => item !== key)
    : [...selectedTaskTargetKeys.value, key]
}

function isTargetSubmitted(target: MarketQuoteTaskTarget) {
  return submittedTaskTargetKeys.value.includes(targetKey(target))
}

function targetQuoteMessage(target: MarketQuoteTaskTarget) {
  return targetQuoteMessages.value[targetKey(target)] || ''
}

function targetByKey(key: string) {
  return taskTargets.value.find((target) => targetKey(target) === key)
}

function targetFeatures(target: MarketQuoteTaskTarget) {
  return Object.fromEntries(
    Object.entries(target.features || {})
      .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '')
      .map(([key, value]) => [key, String(value)])
  )
}

function markTargetSubmitted(key: string, item: MarketQuoteSummary | null) {
  if (!key || !item) return
  submittedTaskTargetKeys.value = Array.from(new Set([...submittedTaskTargetKeys.value, key]))
  selectedTaskTargetKeys.value = selectedTaskTargetKeys.value.filter((selectedKey) => selectedKey !== key)
  targetQuoteMessages.value = {
    ...targetQuoteMessages.value,
    [key]: `已提交复核：${item.recommended_price || '-'}`
  }
  fillMessage.value = `询价成功，已提交到价格库复核：${item.item_name}，推荐价 ${item.recommended_price || '-'}。`
}

async function estimateSelectedTargets() {
  const targets = selectedTaskTargetKeys.value
    .map(targetByKey)
    .filter((target): target is MarketQuoteTaskTarget => target !== undefined)
    .filter((target) => !isTargetSubmitted(target))
  if (!targets.length) return
  batchLoading.value = true
  error.value = ''
  quote.value = null
  let successCount = 0
  const failed: string[] = []
  try {
    for (const target of targets) {
      const key = targetKey(target)
      selectedTargetKey.value = key
      form.itemName = target.item_name
      form.unit = target.unit || ''
      form.featureText = Object.entries(targetFeatures(target)).map(([name, value]) => `${name}=${value}`).join('; ')
      try {
        const result = await estimateMarketQuote({
          provider: form.provider,
          item_name: target.item_name,
          unit: target.unit || undefined,
          region: form.region,
          price_month: form.priceMonth,
          standard: form.standard,
          features: targetFeatures(target),
          pricing_task_code: taskCode.value || undefined
        })
        quote.value = result
        markTargetSubmitted(key, result)
        successCount += 1
      } catch (caught) {
        failed.push(`${target.item_name}：${caught instanceof Error ? caught.message : '询价失败'}`)
      }
    }
    await loadQuotes()
    fillMessage.value = `批量询价完成：成功 ${successCount} 项，失败 ${failed.length} 项。`
    if (failed.length) error.value = failed.slice(0, 3).join('；')
  } finally {
    batchLoading.value = false
  }
}

function formatTargetFeatures(features: Record<string, unknown>) {
  const entries = Object.entries(features || {})
  if (!entries.length) return '-'
  return entries.map(([key, value]) => `${key}=${String(value)}`).join('；')
}

async function changeQuotePage(page: number) {
  quotePage.value = Math.max(1, Math.min(page, quoteTotalPages.value))
  await loadQuotes()
}

async function changeQuoteStatus() {
  quotePage.value = 1
  await loadQuotes()
}

async function approveQuote(item: MarketQuoteSummary) {
  try {
    await approveMarketQuote(item.quote_code, '来源可追溯，采纳进入价格库')
    await loadQuotes()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '采纳失败'
  }
}

async function rejectQuote(item: MarketQuoteSummary) {
  try {
    await rejectMarketQuote(item.quote_code, '来源或规格匹配不足，驳回')
    await loadQuotes()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '驳回失败'
  }
}

function quoteStatusText(status: string) {
  if (status === 'pending_review') return '待复核'
  if (status === 'adopted') return '已采纳'
  if (status === 'rejected') return '已驳回'
  return status
}

function quoteSourceUrls(item: MarketQuoteSummary) {
  const urls = new Set(item.source_urls)
  const supplierQuotes = item.assumptions?.supplier_quotes
  if (Array.isArray(supplierQuotes)) {
    for (const quote of supplierQuotes) {
      if (typeof quote !== 'object' || !quote) continue
      const sourceUrl = (quote as Record<string, unknown>).source_url
      if (typeof sourceUrl === 'string' && sourceUrl) urls.add(sourceUrl)
    }
  }
  return Array.from(urls).slice(0, 5)
}

function quoteEvidences(item: MarketQuoteSummary) {
  const supplierQuotes = item.assumptions?.supplier_quotes
  if (!Array.isArray(supplierQuotes)) return []
  return supplierQuotes
    .map((quote) => (typeof quote === 'object' && quote ? String((quote as Record<string, unknown>).evidence || '') : ''))
    .filter(Boolean)
    .slice(0, 3)
}

function shortUrl(url: string) {
  try {
    const parsed = new URL(url)
    return `${parsed.hostname}${parsed.pathname}`.slice(0, 72)
  } catch {
    return url.slice(0, 72)
  }
}

function parseFeatures(text: string) {
  const features: Record<string, string> = {}
  for (const part of text.split(';')) {
    const [key, value] = part.split('=')
    if (key?.trim() && value?.trim()) features[key.trim()] = value.trim()
  }
  return features
}

function onExcelChange(event: Event) {
  const target = event.target as HTMLInputElement
  excelFile.value = target.files?.[0] || null
}

async function estimateExcel() {
  if (!excelFile.value) return
  excelLoading.value = true
  error.value = ''
  excelResult.value = null
  excelTask.value = null
  const payload = new FormData()
  payload.append('file', excelFile.value)
  payload.append('provider', excelForm.provider)
  payload.append('region', excelForm.region)
  payload.append('price_month', excelForm.priceMonth)
  payload.append('standard', excelForm.standard)
  payload.append('limit', String(excelForm.limit))
  try {
    const accepted = await submitMarketQuoteExcelTask(payload)
    excelTask.value = {
      task_code: accepted.task_code,
      status: accepted.status,
      progress: accepted.progress,
      message: accepted.message,
      workbook_name: excelFile.value.name,
      project_name: null,
      region_code: excelForm.region,
      item_count: 0,
      priced_count: 0,
      unpriced_count: 0,
      excel_path: null,
      missing_rules_path: null,
      audit_path: null,
      mysql_run_code: null,
      failure_reasons: [],
      created_at: '',
      started_at: null,
      finished_at: null
    }
    startExcelPolling(accepted.task_code)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : 'Excel 批量询价失败'
    excelLoading.value = false
  }
}

function startExcelPolling(taskCode: string) {
  stopExcelPolling()
  excelPollTimer = window.setInterval(async () => {
    try {
      excelTask.value = await fetchMarketQuoteExcelTask(taskCode)
      if (['succeeded', 'failed', 'canceled'].includes(excelTask.value.status)) {
        excelLoading.value = false
        if (excelTask.value.status === 'succeeded') await loadQuotes()
        stopExcelPolling()
      }
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : 'Excel 询价任务状态查询失败'
      excelLoading.value = false
      stopExcelPolling()
    }
  }, 1800)
}

function stopExcelPolling() {
  if (excelPollTimer) {
    window.clearInterval(excelPollTimer)
    excelPollTimer = undefined
  }
}

async function cancelExcelTask() {
  if (!excelTask.value) return
  cancelingExcelTask.value = true
  error.value = ''
  try {
    excelTask.value = await cancelMarketQuoteExcelTask(excelTask.value.task_code)
    excelLoading.value = false
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '停止任务失败'
  } finally {
    cancelingExcelTask.value = false
  }
}

onBeforeUnmount(() => {
  stopExcelPolling()
})
</script>
