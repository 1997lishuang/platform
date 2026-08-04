<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h2>单项报价反推</h2>
        <p>从计价批次成本价出发，按目标总报价反算单项，可锁定固定项并手动调整后重新平衡。</p>
      </div>
      <button class="primary" :disabled="!selectedRunCode || !targetTotal || loading" @click="calculate()">
        <Calculator :size="17" />{{ loading ? '反推中' : '按目标总报价反推单项' }}
      </button>
    </div>

    <section class="panel">
      <div class="form-grid">
        <label>计价批次
          <select v-model="selectedRunCode" @change="onRunChange">
            <option value="">选择批次</option>
            <option v-for="run in runs" :key="run.run_code" :value="run.run_code">
              {{ run.project_name || run.run_code }} / {{ run.item_count }} 项
            </option>
          </select>
        </label>
        <label>目标总报价<input v-model="targetTotal" @input="onTargetTotalInput" /></label>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="notice" class="success">{{ notice }}</p>

    <section v-if="validGameRecommendation" class="attention-panel">
      <div>
        <strong>报价决策推荐</strong>
        <p>
          推荐报价 {{ money(gameRecommendation?.recommendedBid || 0) }}，
          推荐区间 {{ money(gameRecommendation?.intervalLow || 0) }} - {{ money(gameRecommendation?.intervalHigh || 0) }}。
          原始成本 {{ money(gameRecommendation?.originalCostTotal || 0) }}，
          当前调整成本线 {{ money(gameRecommendation?.adjustedCostLine || 0) }}。
        </p>
      </div>
      <button class="secondary" @click="applyGameRecommendation">应用推荐报价</button>
    </section>

    <section v-if="result" class="panel">
      <div class="result-strip">
        <div><strong>{{ money(result.summary.costTotal) }}</strong><span>原始成本合计</span></div>
        <div><strong>{{ money(currentCostTotal) }}</strong><span>当前成本合计</span></div>
        <div><strong>{{ money(costAdjustmentDelta) }}</strong><span>成本调整差额</span></div>
        <div><strong>{{ money(result.summary.targetTotal) }}</strong><span>目标总价</span></div>
        <div><strong>{{ money(targetAdjustmentDelta) }}</strong><span>目标调整差额</span></div>
        <div><strong>{{ money(result.summary.finalTotal) }}</strong><span>反推合计</span></div>
        <div><strong>{{ percent(result.summary.profitRate) }}</strong><span>利润率</span></div>
      </div>
      <div class="section-head">
        <div>
          <h3>单项调整</h3>
          <p class="field-hint">可先调整当前成本单价/合价，勾选固定价后该项报价不参与分摊；点击竞争推演会用当前目标合计重新计算利润最优报价。</p>
        </div>
        <div class="header-actions reverse-main-actions">
          <RouterLink class="secondary" to="/dynamic-game" title="把当前目标合计同步到报价决策中心作为成本线 C" @click="syncCostLine(false)">同步成本</RouterLink>
          <button class="secondary" :disabled="loading" title="用当前目标合计作为报价决策成本线 C，重新计算利润最优报价" @click="runGameWithCurrentCost">竞争推演</button>
          <button class="secondary" :disabled="loading" title="按目标总报价重新分摊所有未固定单项，固定项保持不变" @click="calculate()">重算未固定项</button>
          <button class="secondary" :disabled="!editableItems.length" title="把目标单价/目标合价恢复为当前成本，权重恢复为1，目标调整差额归零" @click="resetTargetAdjustment">初始化调整为0</button>
          <button class="secondary" :disabled="!editableItems.length" title="导出当前筛选范围内的单项反推结果" @click="exportReverseExcel">导出Excel</button>
        </div>
      </div>
      <p class="success">
        原始成本：{{ money(result.summary.costTotal) }}；
        报价决策成本线 C：{{ money(currentAdjustedTotal) }}；
        成本调整差额：{{ money(costAdjustmentDelta) }}；
        当前目标合计：{{ money(currentAdjustedTotal) }}；
        目标调整差额：{{ money(targetAdjustmentDelta) }}。
        竞争推演会把当前目标合计同步为报价决策成本线 C。
      </p>
      <p class="warning">
        权重按单项目标系数使用：未固定项的目标合价 = 当前成本合价 × 权重。修改权重后，目标总报价会跟随所有单项目标合价自动更新，并可同步到报价决策中心作为成本线 C。
      </p>
      <div class="reverse-control-panel">
        <div class="reverse-control-top">
          <div>
            <strong>清单检索与批量操作</strong>
            <p>搜索不会改变已固定状态；解锁后需点击“重算未固定项”才会重新分摊目标报价。</p>
          </div>
          <div class="reverse-stat-pills">
            <span>全部 {{ editableItems.length }}</span>
            <span>筛选 {{ filteredEditableItems.length }}</span>
            <span>已固定 {{ lockedItemCount }}</span>
            <span>筛选合计 {{ money(filteredTargetTotal) }}</span>
          </div>
        </div>
        <div class="reverse-toolbar">
          <div class="reverse-filters">
            <input v-model="itemKeyword" class="compact-search reverse-search" placeholder="搜索清单项、工作表或行号" @input="itemPage = 1" />
            <select v-model="itemLockFilter" class="compact-select" @change="itemPage = 1">
              <option value="all">全部单项</option>
              <option value="locked">只看已固定</option>
              <option value="unlocked">只看未固定</option>
            </select>
            <select v-model.number="itemPageSize" class="compact-select" @change="itemPage = 1">
              <option :value="10">10 条/页</option>
              <option :value="20">20 条/页</option>
              <option :value="50">50 条/页</option>
              <option :value="100">100 条/页</option>
            </select>
          </div>
          <div class="header-actions reverse-unlock-actions">
            <button class="secondary" :disabled="!filteredEditableItems.some(item => item.locked)" @click="unlockFilteredItems">
              解锁筛选项
            </button>
            <button class="secondary" :disabled="!pagedEditableItems.some(item => item.locked)" @click="unlockPagedItems">
              解锁本页
            </button>
          </div>
        </div>
        <div class="pagination-bar reverse-page-summary">
          <span>当前显示 {{ pagedEditableItems.length }} 项</span>
          <div class="header-actions reverse-pager-actions">
            <button class="secondary" :disabled="visibleItemPage <= 1" @click="itemPage -= 1">上一页</button>
            <span>第 {{ visibleItemPage }} / {{ itemPageCount }} 页</span>
            <button class="secondary" :disabled="visibleItemPage >= itemPageCount" @click="itemPage += 1">下一页</button>
          </div>
        </div>
      </div>
      <div class="run-result-table-wrap reverse-table-wrap">
        <table class="run-result-table reverse-table">
          <thead>
            <tr>
              <th>固定报价</th>
              <th>清单项</th>
              <th>工程量</th>
              <th>原始成本单价</th>
              <th>原始成本合价</th>
              <th>当前成本单价</th>
              <th>当前成本合价</th>
              <th>权重</th>
              <th>目标单价</th>
              <th>目标合价</th>
              <th>利润率</th>
              <th>提示</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in pagedEditableItems" :key="item.itemKey">
              <td><input v-model="item.locked" type="checkbox" :title="item.locked ? '已固定：重算时保持目标单价和目标合价' : '未固定：重算时按权重分摊目标总报价'" @change="onLockedChange(item)" /></td>
              <td class="item-name">{{ item.itemName }}<small>{{ item.sourceSheet }} / {{ item.sourceRowNumber }}</small></td>
              <td>{{ item.quantity }}</td>
              <td>{{ money(item.originalCostUnitPrice || item.costUnitPrice) }}</td>
              <td>{{ money(item.originalCostTotal || item.costTotal) }}</td>
              <td><input v-model="item.costUnitPrice" class="compact-input" type="number" min="0" step="0.0001" @input="onCostUnitPriceInput(item)" /></td>
              <td><input v-model="item.costTotal" class="compact-input" type="number" min="0" step="0.01" @input="onCostTotalInput(item)" /></td>
              <td><input v-model="item.weight" class="compact-input" type="number" min="0" step="0.1" @input="onWeightInput" /></td>
              <td><input v-model="item.targetUnitPrice" class="compact-input" type="number" min="0" step="0.0001" @input="onUnitPriceInput(item)" /></td>
              <td><input v-model="item.targetTotal" class="compact-input" type="number" min="0" step="0.01" @input="onTotalInput(item)" /></td>
              <td>{{ percent(item.profitRate) }}</td>
              <td>{{ item.issues?.join('；') || '-' }}</td>
            </tr>
            <tr v-if="!pagedEditableItems.length">
              <td colspan="12" class="empty-table-cell">没有匹配的清单项，请调整搜索条件。</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pagination-bar">
        <span>第 {{ visibleItemPage }} / {{ itemPageCount }} 页</span>
        <div class="header-actions">
          <button class="secondary" :disabled="visibleItemPage <= 1" @click="itemPage -= 1">上一页</button>
          <button class="secondary" :disabled="visibleItemPage >= itemPageCount" @click="itemPage += 1">下一页</button>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Calculator } from '@lucide/vue'
import { api } from '../api/client'

interface PricingRun { run_code: string; project_name: string | null; item_count: number }
interface ReverseItem {
  itemKey: string
  itemName: string
  sourceSheet: string
  sourceRowNumber: number
  quantity: string
  originalCostUnitPrice?: string
  originalCostTotal?: string
  costUnitPrice: string
  costTotal: string
  targetUnitPrice: string
  targetTotal: string
  profitRate: number
  weight: string
  locked: boolean
  issues: string[]
}
interface ReverseResult {
  summary: { costTotal: string; targetTotal: string; finalTotal: string; profitRate: number }
  items: ReverseItem[]
}
interface GameRecommendation {
  syncId?: string
  runCode?: string
  originalCostTotal?: string
  adjustedCostLine?: string
  targetTotal?: string
  recommendedBid: string
  intervalLow: string
  intervalHigh: string
  autoApplyReverse?: boolean
  syncedAt?: string
}
interface ReverseDraft {
  runCode: string
  targetTotal: string
  savedAt: string
  items: Record<string, Partial<ReverseItem>>
}

const runs = ref<PricingRun[]>([])
const route = useRoute()
const selectedRunCode = ref('')
const targetTotal = ref('')
const editableItems = ref<ReverseItem[]>([])
const result = ref<ReverseResult | null>(null)
const loading = ref(false)
const error = ref('')
const notice = ref('')
const gameRecommendation = ref<GameRecommendation | null>(null)
const lastAppliedRecommendationId = ref('')
const targetFromRoute = ref(false)
const itemKeyword = ref('')
const itemLockFilter = ref<'all' | 'locked' | 'unlocked'>('all')
const itemPage = ref(1)
const itemPageSize = ref(20)
const draftStoragePrefix = 'bid_reverse_pricing_draft'
const currentAdjustedTotal = computed(() => editableItems.value.reduce((sum, item) => sum + Number(item.targetTotal || 0), 0))
const currentCostTotal = computed(() => editableItems.value.reduce((sum, item) => sum + Number(item.costTotal || 0), 0))
const costAdjustmentDelta = computed(() => currentCostTotal.value - Number(result.value?.summary.costTotal || 0))
const targetAdjustmentDelta = computed(() => currentAdjustedTotal.value - currentCostTotal.value)
const lockedItemCount = computed(() => editableItems.value.filter(item => item.locked).length)
const filteredEditableItems = computed(() => {
  const keyword = itemKeyword.value.trim().toLowerCase()
  return editableItems.value.filter(item => {
    if (itemLockFilter.value === 'locked' && !item.locked) return false
    if (itemLockFilter.value === 'unlocked' && item.locked) return false
    if (!keyword) return true
    return item.itemName.toLowerCase().includes(keyword) ||
      item.sourceSheet.toLowerCase().includes(keyword) ||
      String(item.sourceRowNumber).includes(keyword)
  })
})
const filteredTargetTotal = computed(() => filteredEditableItems.value.reduce((sum, item) => sum + Number(item.targetTotal || 0), 0))
const itemPageCount = computed(() => Math.max(1, Math.ceil(filteredEditableItems.value.length / itemPageSize.value)))
const visibleItemPage = computed(() => Math.min(Math.max(1, itemPage.value), itemPageCount.value))
const pagedEditableItems = computed(() => {
  const start = (visibleItemPage.value - 1) * itemPageSize.value
  return filteredEditableItems.value.slice(start, start + itemPageSize.value)
})
const validGameRecommendation = computed(() => Boolean(
  gameRecommendation.value?.recommendedBid &&
  gameRecommendation.value?.runCode &&
  gameRecommendation.value.runCode === selectedRunCode.value
))

function money(value: string | number) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(Number(value || 0))
}

function percent(value: number) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`
}

function draftKey(runCode = selectedRunCode.value) {
  return `${draftStoragePrefix}:${runCode}`
}

function saveDraft() {
  if (!selectedRunCode.value || !editableItems.value.length) return
  const draft: ReverseDraft = {
    runCode: selectedRunCode.value,
    targetTotal: targetTotal.value || currentAdjustedTotal.value.toFixed(2),
    savedAt: new Date().toISOString(),
    items: Object.fromEntries(editableItems.value.map(item => [item.itemKey, {
      costUnitPrice: item.costUnitPrice,
      costTotal: item.costTotal,
      targetUnitPrice: item.targetUnitPrice,
      targetTotal: item.targetTotal,
      weight: item.weight,
      locked: item.locked,
      profitRate: item.profitRate,
      issues: item.issues
    }]))
  }
  localStorage.setItem(draftKey(), JSON.stringify(draft))
}

function readDraft(runCode = selectedRunCode.value): ReverseDraft | null {
  if (!runCode) return null
  try {
    const draft = JSON.parse(localStorage.getItem(draftKey(runCode)) || 'null') as ReverseDraft | null
    return draft?.runCode === runCode ? draft : null
  } catch {
    return null
  }
}

function applyDraft() {
  const draft = readDraft()
  if (!draft) return false
  editableItems.value = editableItems.value.map(item => {
    const saved = draft.items[item.itemKey]
    if (!saved) return item
    return {
      ...item,
      costUnitPrice: saved.costUnitPrice ?? item.costUnitPrice,
      costTotal: saved.costTotal ?? item.costTotal,
      targetUnitPrice: saved.targetUnitPrice ?? item.targetUnitPrice,
      targetTotal: saved.targetTotal ?? item.targetTotal,
      weight: saved.weight ?? item.weight,
      locked: saved.locked ?? item.locked,
      profitRate: saved.profitRate ?? item.profitRate,
      issues: saved.issues ?? item.issues
    }
  })
  targetTotal.value = draft.targetTotal || currentAdjustedTotal.value.toFixed(2)
  refreshLocalSummary()
  notice.value = `已恢复当前批次上次调整草稿，保存时间 ${new Date(draft.savedAt).toLocaleString('zh-CN')}。`
  return true
}

function roundMoney(value: number) {
  return Math.round((Number(value || 0) + Number.EPSILON) * 100) / 100
}

function roundUnit(value: number) {
  return Math.round((Number(value || 0) + Number.EPSILON) * 10000) / 10000
}

function unlockItems(items: ReverseItem[]) {
  let count = 0
  items.forEach(item => {
    if (item.locked) {
      item.locked = false
      count += 1
    }
  })
  if (!count) return
  notice.value = `已解锁 ${count} 个单项，当前调整已保存。`
  saveDraft()
  syncCostLine()
}

function unlockFilteredItems() {
  unlockItems(filteredEditableItems.value)
}

function unlockPagedItems() {
  unlockItems(pagedEditableItems.value)
}

function excelCell(value: string | number | undefined | null) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function excelRow(cells: Array<string | number | undefined | null>, header = false) {
  const tag = header ? 'th' : 'td'
  return `<tr>${cells.map(cell => `<${tag}>${excelCell(cell)}</${tag}>`).join('')}</tr>`
}

function exportReverseExcel() {
  const rows = filteredEditableItems.value.length ? filteredEditableItems.value : editableItems.value
  const exportedAt = new Date().toLocaleString('zh-CN')
  const html = `
    <html>
      <head><meta charset="UTF-8" /></head>
      <body>
        <table border="1">
          ${excelRow(['单项报价反推导出'], true)}
          ${excelRow(['导出时间', exportedAt], true)}
          ${excelRow(['计价批次', selectedRunCode.value], true)}
          ${excelRow(['原始成本合计', result.value?.summary.costTotal || ''], true)}
          ${excelRow(['当前成本合计', currentCostTotal.value.toFixed(2)], true)}
          ${excelRow(['目标总报价', targetTotal.value], true)}
          ${excelRow(['筛选项数', rows.length], true)}
          ${excelRow([
            '固定报价',
            '清单项',
            '工作表',
            '行号',
            '工程量',
            '原始成本单价',
            '原始成本合价',
            '当前成本单价',
            '当前成本合价',
            '权重',
            '目标单价',
            '目标合价',
            '利润率',
            '提示'
          ], true)}
          ${rows.map(item => excelRow([
            item.locked ? '是' : '否',
            item.itemName,
            item.sourceSheet,
            item.sourceRowNumber,
            item.quantity,
            item.originalCostUnitPrice || item.costUnitPrice,
            item.originalCostTotal || item.costTotal,
            item.costUnitPrice,
            item.costTotal,
            item.weight,
            item.targetUnitPrice,
            item.targetTotal,
            percent(item.profitRate),
            item.issues?.join('；') || ''
          ])).join('')}
        </table>
      </body>
    </html>
  `
  const blob = new Blob([html], { type: 'application/vnd.ms-excel;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const suffix = itemKeyword.value || itemLockFilter.value !== 'all' ? '筛选' : '全部'
  link.href = url
  link.download = `单项报价反推_${selectedRunCode.value || '未选择批次'}_${suffix}.xls`
  link.click()
  URL.revokeObjectURL(url)
}

function refreshItemProfit(item: ReverseItem) {
  const costTotal = Number(item.costTotal || 0)
  const target = Number(item.targetTotal || 0)
  item.profitRate = costTotal ? (target - costTotal) / costTotal : 0
  const baseIssues = (item.issues || []).filter(issue => issue !== '目标合价低于成本')
  if (target < costTotal) baseIssues.unshift('目标合价低于成本')
  item.issues = baseIssues
}

function applyWeightsToUnlockedItems() {
  if (!editableItems.value.length) return
  const adjustable = editableItems.value.filter(item => !item.locked)
  if (!adjustable.length) {
    refreshLocalSummary()
    return
  }
  error.value = ''
  adjustable.forEach(item => {
    const weight = Math.max(0, Number(item.weight || 0))
    const nextTotal = roundMoney(Number(item.costTotal || 0) * weight)
    const quantity = Number(item.quantity || 0)
    item.targetTotal = nextTotal.toFixed(2)
    if (quantity > 0) item.targetUnitPrice = roundUnit(nextTotal / quantity).toFixed(4)
    refreshItemProfit(item)
  })
  targetTotal.value = currentAdjustedTotal.value.toFixed(2)
  refreshLocalSummary()
  saveDraft()
  syncCostLine()
}

function onWeightInput() {
  notice.value = '权重已更新，目标总报价已按当前单项目标合价自动刷新，并已同步为报价决策成本线 C。'
  applyWeightsToUnlockedItems()
}

function resetTargetAdjustment() {
  if (!editableItems.value.length) return
  editableItems.value.forEach(item => {
    item.locked = false
    item.weight = '1'
    item.targetUnitPrice = Number(item.costUnitPrice || 0).toFixed(4)
    item.targetTotal = Number(item.costTotal || 0).toFixed(2)
    refreshItemProfit(item)
  })
  targetTotal.value = currentCostTotal.value.toFixed(2)
  refreshLocalSummary()
  notice.value = '已初始化目标调整差额为 0：目标价恢复为当前成本价，权重恢复为 1，并已保存草稿。'
  saveDraft()
  syncCostLine()
}

function isAbnormalTargetTotal(value: string | number, costTotal: number) {
  const target = Number(value || 0)
  if (!Number.isFinite(target) || !Number.isFinite(costTotal) || costTotal <= 0) return false
  return target > costTotal * 3 || target < costTotal * 0.5
}

function isMatchingRecommendationTarget(value: string | number) {
  if (!gameRecommendation.value?.runCode || gameRecommendation.value.runCode !== selectedRunCode.value) return false
  return Math.abs(Number(gameRecommendation.value.targetTotal || gameRecommendation.value.recommendedBid) - Number(value || 0)) < 1
}

async function loadRuns() {
  const { data } = await api.get<PricingRun[]>('/pricing/runs?limit=100')
  runs.value = data
}

async function loadRunDetail() {
  const previousTargetTotal = targetTotal.value
  notice.value = ''
  result.value = null
  editableItems.value = []
  if (!selectedRunCode.value) return
  const { data } = await api.get(`/pricing/runs/${selectedRunCode.value}`)
  const total = data.results.reduce((sum: number, item: { total_price: string | null }) => sum + Number(item.total_price || 0), 0)
  if (previousTargetTotal && targetFromRoute.value && isAbnormalTargetTotal(previousTargetTotal, total) && !isMatchingRecommendationTarget(previousTargetTotal)) {
    targetTotal.value = String(Math.round(total))
    notice.value = `已忽略不匹配的目标总报价 ${money(previousTargetTotal)}，当前批次成本为 ${money(total)}。请先在报价决策中心基于当前批次重新生成推荐报价。`
  } else {
    targetTotal.value = previousTargetTotal || String(Math.round(total))
  }
  targetFromRoute.value = false
  itemPage.value = 1
  editableItems.value = data.results.map((item: {
    source_sheet?: string
    source_row_number?: number
    item_name?: string
    quantity?: string | number | null
    unit_price?: string | number | null
    total_price?: string | number | null
    confidence?: string | number | null
    issues?: string[]
  }) => {
    const quantity = String(item.quantity || 0)
    const unitPrice = String(item.unit_price || 0)
    const totalPrice = String(item.total_price || Number(quantity) * Number(unitPrice))
    return {
      itemKey: `${item.source_sheet || ''}:${item.source_row_number || ''}`,
      itemName: item.item_name || '',
      sourceSheet: item.source_sheet || '',
      sourceRowNumber: item.source_row_number || 0,
      quantity,
      originalCostUnitPrice: unitPrice,
      originalCostTotal: Number(totalPrice).toFixed(2),
      costUnitPrice: unitPrice,
      costTotal: Number(totalPrice).toFixed(2),
      targetUnitPrice: unitPrice,
      targetTotal: Number(totalPrice).toFixed(2),
      profitRate: 0,
      weight: '1',
      locked: false,
      issues: item.issues || []
    }
  })
  result.value = {
    summary: {
      costTotal: total.toFixed(2),
      targetTotal: String(targetTotal.value),
      finalTotal: currentAdjustedTotal.value.toFixed(2),
      profitRate: total ? (currentAdjustedTotal.value - total) / total : 0
    },
    items: editableItems.value
  }
  const restored = applyDraft()
  if (!restored) saveDraft()
  syncCostLine(false)
  readGameRecommendation()
}

async function onRunChange() {
  targetTotal.value = ''
  await loadRunDetail()
}

function overrides() {
  return Object.fromEntries(editableItems.value.map(item => [item.itemKey, {
    locked: item.locked,
    weight: item.weight,
    targetUnitPrice: item.locked ? item.targetUnitPrice : undefined,
    targetTotal: item.locked ? item.targetTotal : undefined
  }]))
}

function onTargetTotalInput() {
  if (result.value) result.value.summary.targetTotal = String(targetTotal.value || currentAdjustedTotal.value)
  saveDraft()
}

function onUnitPriceInput(item: ReverseItem) {
  item.locked = true
  item.targetTotal = (Number(item.targetUnitPrice || 0) * Number(item.quantity || 0)).toFixed(2)
  refreshItemProfit(item)
  refreshLocalSummary()
  targetTotal.value = currentAdjustedTotal.value.toFixed(2)
  saveDraft()
  syncCostLine()
}

function onTotalInput(item: ReverseItem) {
  item.locked = true
  const quantity = Number(item.quantity || 0)
  if (quantity > 0) item.targetUnitPrice = (Number(item.targetTotal || 0) / quantity).toFixed(4)
  refreshItemProfit(item)
  refreshLocalSummary()
  targetTotal.value = currentAdjustedTotal.value.toFixed(2)
  saveDraft()
  syncCostLine()
}

function onLockedChange(item: ReverseItem) {
  if (item.locked) {
    item.targetTotal = (Number(item.targetTotal || item.costTotal || 0)).toFixed(2)
    const quantity = Number(item.quantity || 0)
    if (quantity > 0) item.targetUnitPrice = (Number(item.targetTotal || 0) / quantity).toFixed(4)
    refreshItemProfit(item)
  }
  refreshLocalSummary()
  targetTotal.value = currentAdjustedTotal.value.toFixed(2)
  saveDraft()
  syncCostLine()
}

function onCostUnitPriceInput(item: ReverseItem) {
  item.costTotal = (Number(item.costUnitPrice || 0) * Number(item.quantity || 0)).toFixed(2)
  if (!item.locked) {
    const weight = Math.max(0, Number(item.weight || 0))
    item.targetTotal = roundMoney(Number(item.costTotal || 0) * weight).toFixed(2)
    const quantity = Number(item.quantity || 0)
    if (quantity > 0) item.targetUnitPrice = roundUnit(Number(item.targetTotal || 0) / quantity).toFixed(4)
  }
  refreshItemProfit(item)
  refreshLocalSummary()
  targetTotal.value = currentAdjustedTotal.value.toFixed(2)
  saveDraft()
  syncCostLine()
}

function onCostTotalInput(item: ReverseItem) {
  const quantity = Number(item.quantity || 0)
  if (quantity > 0) item.costUnitPrice = (Number(item.costTotal || 0) / quantity).toFixed(4)
  if (!item.locked) {
    const weight = Math.max(0, Number(item.weight || 0))
    item.targetTotal = roundMoney(Number(item.costTotal || 0) * weight).toFixed(2)
    if (quantity > 0) item.targetUnitPrice = roundUnit(Number(item.targetTotal || 0) / quantity).toFixed(4)
  }
  refreshItemProfit(item)
  refreshLocalSummary()
  targetTotal.value = currentAdjustedTotal.value.toFixed(2)
  saveDraft()
  syncCostLine()
}

function refreshLocalSummary() {
  if (!result.value) return
  const finalTotal = currentAdjustedTotal.value
  const costTotal = currentCostTotal.value
  result.value.summary.targetTotal = finalTotal.toFixed(2)
  result.value.summary.finalTotal = finalTotal.toFixed(2)
  result.value.summary.profitRate = costTotal ? (finalTotal - costTotal) / costTotal : 0
}

function syncCostLine(autoRunGame = false) {
  if (!editableItems.value.length) return
  const costLine = currentAdjustedTotal.value.toFixed(2)
  const payload = {
    source: selectedRunCode.value ? `计价批次 ${selectedRunCode.value}` : '单项报价反推',
    runCode: selectedRunCode.value,
    originalCostTotal: result.value?.summary.costTotal || currentCostTotal.value.toFixed(2),
    currentCostTotal: currentCostTotal.value.toFixed(2),
    adjustedCostLine: costLine,
    adjustmentDelta: targetAdjustmentDelta.value.toFixed(2),
    targetTotal: currentAdjustedTotal.value.toFixed(2),
    costLine,
    itemCount: editableItems.value.length,
    autoRunGame,
    syncId: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    syncedAt: new Date().toLocaleString('zh-CN')
  }
  localStorage.setItem('bid_generation_cost_context', JSON.stringify(payload))
}

function buildPricingItems() {
  return editableItems.value.map(item => ({
    itemKey: item.itemKey,
    sourceSheet: item.sourceSheet,
    sourceRowNumber: item.sourceRowNumber,
    itemName: item.itemName,
    quantity: item.quantity,
    unitPrice: item.costUnitPrice,
    totalPrice: item.costTotal,
    confidence: '1',
    issues: item.issues || []
  }))
}

function readGameRecommendation() {
  try {
    const value = JSON.parse(localStorage.getItem('bid_generation_game_recommendation') || 'null') as GameRecommendation | null
    if (!value?.recommendedBid) return null
    if (!selectedRunCode.value || !value.runCode || value.runCode !== selectedRunCode.value) {
      gameRecommendation.value = null
      return null
    }
    gameRecommendation.value = value
    return value
  } catch {
    return null
  }
}

async function onStorage(event: StorageEvent) {
  if (event.key !== 'bid_generation_game_recommendation') return
  const value = readGameRecommendation()
  if (!value?.autoApplyReverse || !selectedRunCode.value) return
  const syncId = value.syncId || `${value.runCode}-${value.recommendedBid}-${value.syncedAt}`
  if (lastAppliedRecommendationId.value === syncId) return
  lastAppliedRecommendationId.value = syncId
  await applyGameRecommendation()
}

async function applyGameRecommendation() {
  if (!gameRecommendation.value?.recommendedBid) return
  if (!validGameRecommendation.value) {
    notice.value = '当前报价决策推荐不属于所选计价批次，已拒绝应用。请基于当前批次重新运行竞争推演。'
    return
  }
  targetTotal.value = String(gameRecommendation.value.targetTotal || gameRecommendation.value.recommendedBid)
  await calculate(false)
}

async function calculate(autoRunGame = false) {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.post<ReverseResult>('/bid-generation/reverse-pricing', {
      run_code: editableItems.value.length ? undefined : selectedRunCode.value,
      items: editableItems.value.length ? buildPricingItems() : [],
      target_total: targetTotal.value,
      locked_items: overrides()
    })
    const previousByKey = Object.fromEntries(editableItems.value.map(item => [item.itemKey, {
      originalCostUnitPrice: item.originalCostUnitPrice || item.costUnitPrice,
      originalCostTotal: item.originalCostTotal || item.costTotal,
      locked: item.locked,
      weight: item.weight,
      targetUnitPrice: item.targetUnitPrice,
      targetTotal: item.targetTotal
    }]))
    result.value = data
    editableItems.value = data.items.map(item => ({
      ...item,
      originalCostUnitPrice: previousByKey[item.itemKey]?.originalCostUnitPrice || item.costUnitPrice,
      originalCostTotal: previousByKey[item.itemKey]?.originalCostTotal || item.costTotal,
      locked: previousByKey[item.itemKey]?.locked ?? item.locked,
      weight: previousByKey[item.itemKey]?.weight || item.weight,
      targetUnitPrice: previousByKey[item.itemKey]?.locked ? previousByKey[item.itemKey].targetUnitPrice : item.targetUnitPrice,
      targetTotal: previousByKey[item.itemKey]?.locked ? previousByKey[item.itemKey].targetTotal : item.targetTotal
    }))
    targetTotal.value = currentAdjustedTotal.value.toFixed(2)
    refreshLocalSummary()
    itemPage.value = 1
    saveDraft()
    syncCostLine(autoRunGame)
    readGameRecommendation()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function runGameWithCurrentCost() {
  syncCostLine(true)
}

onMounted(async () => {
  await loadRuns()
  window.addEventListener('storage', onStorage)
  const runCode = Array.isArray(route.query.run_code) ? route.query.run_code[0] : route.query.run_code
  const queryTargetTotal = Array.isArray(route.query.target_total) ? route.query.target_total[0] : route.query.target_total
  if (!runCode) return
  selectedRunCode.value = String(runCode)
  if (queryTargetTotal) {
    targetTotal.value = String(queryTargetTotal)
    targetFromRoute.value = true
  }
  readGameRecommendation()
  await loadRunDetail()
  if (targetTotal.value) await calculate()
})

onBeforeUnmount(() => window.removeEventListener('storage', onStorage))
</script>
