<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h2>清单映射校准</h2>
        <p>计价时自动判断映射置信度；低于阈值或存在歧义的清单项在这里人工校准，可选择是否沉淀为后续规则。</p>
      </div>
      <button class="secondary" @click="reloadAll"><RefreshCw :size="17" />刷新</button>
    </div>

    <section class="panel">
      <div class="section-head">
        <h3>自动映射阈值</h3>
      </div>
      <div class="form-grid compact-grid">
        <label>
          人工校准阈值
          <input v-model.number="thresholdPercent" type="number" min="0" max="100" step="1" />
          <span class="field-hint">计价时自动映射置信度低于该值，会进入人工校准。默认 85%。</span>
        </label>
      </div>
      <div class="form-actions">
        <span class="field-hint">当前阈值：{{ thresholdPercent }}%</span>
        <button class="primary" @click="saveSetting"><Save :size="17" />保存阈值</button>
      </div>
      <div class="info-strip">
        阈值只控制“是否自动通过映射”。低于 {{ thresholdPercent }}% 的清单项会进入人工校准；候选标准对象仍会展示相近项，低于阈值的候选仅供人工参考，不会自动计价通过。
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <h3>待人工校准</h3>
      </div>
      <div class="form-grid">
        <label>
          关键词
          <input v-model="reviewFilters.keyword" placeholder="原始项目名称或标准对象" @keyup.enter="searchReviews" />
        </label>
        <label>
          状态
          <select v-model="reviewFilters.status" @change="searchReviews">
            <option value="pending">待校准</option>
            <option value="">全部</option>
          </select>
        </label>
      </div>
      <table>
        <thead>
          <tr>
            <th>来源</th>
            <th>原始项目</th>
            <th>候选标准对象</th>
            <th>特征</th>
            <th>校准结果</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="review in reviews" :key="review.review_code">
            <td>
              <div class="cell-stack">
                <strong>{{ review.workbook_name || '-' }}</strong>
                <span>{{ review.source_sheet || '-' }} / 第 {{ review.source_row_number || '-' }} 行</span>
              </div>
            </td>
            <td>{{ review.source_item_name }} / {{ review.unit || '-' }}</td>
            <td class="conditions-cell">
              <button
                v-for="candidate in review.candidates"
                :key="String(candidate.mapping_code || candidate.standard_item_name)"
                class="choice-pill"
                :data-confidence="candidateMeetsThreshold(candidate) ? 'pass' : 'below'"
                :title="candidateTitle(candidate)"
                @click="selectCandidate(review, String(candidate.standard_item_name || ''))"
              >
                <span>{{ candidate.standard_item_name }}</span>
                <em>{{ formatScore(candidate.score) }}</em>
                <small>{{ candidateMeetsThreshold(candidate) ? '达标' : '低于阈值' }}</small>
              </button>
              <p class="candidate-help">
                最佳候选 {{ bestCandidateScore(review) }}；低于 {{ thresholdPercent }}% 表示系统已拦截为人工校准。
              </p>
            </td>
            <td class="conditions-cell">{{ formatConditions(review.features as Record<string, string>) }}</td>
            <td>
              <input v-model="reviewDrafts[review.review_code]" :disabled="review.status !== 'pending'" placeholder="选择或填写标准计价对象" />
            </td>
            <td class="action-cell">
              <button
                class="small-action"
                :disabled="review.status !== 'pending' || !reviewDrafts[review.review_code]"
                @click="resolveReview(review.review_code, false)"
              >
                仅校准
              </button>
              <button
                class="small-action"
                :disabled="review.status !== 'pending' || !reviewDrafts[review.review_code]"
                @click="resolveReview(review.review_code, true)"
              >
                校准并沉淀
              </button>
            </td>
          </tr>
          <tr v-if="reviews.length === 0">
            <td colspan="6" class="empty-row">暂无需要人工校准的清单项</td>
          </tr>
        </tbody>
      </table>
      <div class="pager">
        <span>共 {{ reviewTotal }} 条，第 {{ reviewPage }} / {{ reviewPageCount }} 页</span>
        <div class="pager-actions">
          <button class="secondary" :disabled="reviewPage <= 1" @click="reviewPage--; loadReviews()">上一页</button>
          <button class="secondary" :disabled="reviewPage >= reviewPageCount" @click="reviewPage++; loadReviews()">下一页</button>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <div>
          <h3>已校准结果</h3>
          <p class="field-hint">默认显示已校准但未沉淀的记录，方便确认哪些校准结果尚未进入映射库。</p>
        </div>
      </div>
      <div class="form-grid">
        <label>
          关键词
          <input v-model="resultFilters.keyword" placeholder="原始项目名称、标准计价对象" @keyup.enter="searchResults" />
        </label>
        <label>
          沉淀状态
          <select v-model="resultFilters.persistedStatus" @change="searchResults">
            <option value="unpersisted">未沉淀</option>
            <option value="persisted">已沉淀</option>
            <option value="resolved_all">全部已校准</option>
            <option value="all">全部记录</option>
          </select>
        </label>
      </div>
      <table>
        <thead>
          <tr>
            <th>来源</th>
            <th>原始项目</th>
            <th>校准结果</th>
            <th>单位</th>
            <th>沉淀状态</th>
            <th>校准时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in results" :key="item.review_code">
            <td>
              <div class="cell-stack">
                <strong>{{ item.workbook_name || '-' }}</strong>
                <span>{{ item.source_sheet || '-' }} / 第 {{ item.source_row_number || '-' }} 行</span>
              </div>
            </td>
            <td>{{ item.source_item_name }}</td>
            <td><strong>{{ item.selected_standard_item_name || '-' }}</strong></td>
            <td>{{ item.unit || '-' }}</td>
            <td>
              <span class="status-badge" :data-status="item.persisted ? 'priced' : 'unpriced'">
                {{ item.persisted ? '已沉淀' : '未沉淀' }}
              </span>
            </td>
            <td>{{ formatDate(item.reviewed_at || item.created_at) }}</td>
            <td class="action-cell">
              <button
                v-if="item.status === 'resolved' && !item.persisted && item.selected_standard_item_name"
                class="small-action"
                @click="persistReview(item)"
              >
                沉淀
              </button>
            </td>
          </tr>
          <tr v-if="results.length === 0">
            <td colspan="7" class="empty-row">暂无符合条件的校准结果</td>
          </tr>
        </tbody>
      </table>
      <div class="pager">
        <span>共 {{ resultTotal }} 条，第 {{ resultPage }} / {{ resultPageCount }} 页</span>
        <div class="pager-actions">
          <button class="secondary" :disabled="resultPage <= 1" @click="resultPage--; loadResults()">上一页</button>
          <button class="secondary" :disabled="resultPage >= resultPageCount" @click="resultPage++; loadResults()">下一页</button>
        </div>
      </div>
    </section>

    <p v-if="message" class="success">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { RefreshCw, Save } from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  fetchItemMappingReviewPage,
  fetchItemMappingSetting,
  resolveItemMappingReview,
  saveItemMappingSetting,
  type ItemMappingReviewSummary
} from '../api/client'

const pageSize = 20
const reviews = ref<ItemMappingReviewSummary[]>([])
const results = ref<ItemMappingReviewSummary[]>([])
const reviewTotal = ref(0)
const resultTotal = ref(0)
const reviewPage = ref(1)
const resultPage = ref(1)
const thresholdPercent = ref(85)
const message = ref('')
const error = ref('')
const reviewDrafts = reactive<Record<string, string>>({})
const reviewFilters = reactive({ keyword: '', status: 'pending' })
const resultFilters = reactive({
  keyword: '',
  persistedStatus: 'unpersisted' as 'unpersisted' | 'persisted' | 'resolved_all' | 'all'
})

const reviewPageCount = computed(() => Math.max(1, Math.ceil(reviewTotal.value / pageSize)))
const resultPageCount = computed(() => Math.max(1, Math.ceil(resultTotal.value / pageSize)))

async function reloadAll() {
  await Promise.all([loadSetting(), loadReviews(), loadResults()])
}

async function loadSetting() {
  const setting = await fetchItemMappingSetting()
  thresholdPercent.value = Math.round(Number(setting.confidence_threshold) * 100)
}

async function saveSetting() {
  error.value = ''
  message.value = ''
  const normalized = Math.min(100, Math.max(0, Number(thresholdPercent.value || 0)))
  thresholdPercent.value = normalized
  try {
    await saveItemMappingSetting((normalized / 100).toFixed(4))
    message.value = '自动映射阈值已保存'
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '阈值保存失败'
  }
}

async function searchReviews() {
  reviewPage.value = 1
  await loadReviews()
}

async function loadReviews() {
  const page = await fetchItemMappingReviewPage({
    keyword: reviewFilters.keyword || undefined,
    status: reviewFilters.status || undefined,
    page: reviewPage.value,
    page_size: pageSize
  })
  reviews.value = page.items
  reviewTotal.value = page.total
  for (const item of page.items) {
    reviewDrafts[item.review_code] = item.selected_standard_item_name || ''
  }
}

async function searchResults() {
  resultPage.value = 1
  await loadResults()
}

async function loadResults() {
  const persistedStatus = resultFilters.persistedStatus
  const page = await fetchItemMappingReviewPage({
    keyword: resultFilters.keyword || undefined,
    status: persistedStatus === 'all' ? undefined : 'resolved',
    persisted: persistedStatus === 'unpersisted' ? false : persistedStatus === 'persisted' ? true : undefined,
    page: resultPage.value,
    page_size: pageSize
  })
  results.value = page.items
  resultTotal.value = page.total
}

function selectCandidate(review: ItemMappingReviewSummary, standardItemName: string) {
  if (review.status !== 'pending') return
  reviewDrafts[review.review_code] = standardItemName
}

async function resolveReview(reviewCode: string, createMapping: boolean) {
  const standardItemName = reviewDrafts[reviewCode]
  if (!standardItemName) return
  await resolveItemMappingReview(reviewCode, {
    standard_item_name: standardItemName,
    comment: createMapping ? '人工校准并沉淀为映射规则' : '人工校准，暂不沉淀',
    create_mapping: createMapping
  })
  message.value = createMapping ? '校准结果已沉淀，后续计价会自动使用' : '校准完成，结果暂未沉淀'
  await Promise.all([loadReviews(), loadResults()])
}

async function persistReview(item: ItemMappingReviewSummary) {
  if (!item.selected_standard_item_name) return
  await resolveItemMappingReview(item.review_code, {
    standard_item_name: item.selected_standard_item_name,
    comment: '已校准结果补充沉淀',
    create_mapping: true
  })
  message.value = '校准结果已沉淀'
  await loadResults()
}

function formatConditions(value: Record<string, unknown>) {
  const entries = Object.entries(value || {})
  if (!entries.length) return '-'
  return entries.map(([key, val]) => `${key}=${String(val)}`).join('；')
}

function formatScore(value: unknown) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '-'
  return `${Math.round(numeric * 100)}%`
}

function candidateScore(candidate: Record<string, unknown>) {
  const numeric = Number(candidate.score)
  return Number.isFinite(numeric) ? numeric : 0
}

function candidateMeetsThreshold(candidate: Record<string, unknown>) {
  return candidateScore(candidate) >= thresholdPercent.value / 100
}

function candidateTitle(candidate: Record<string, unknown>) {
  const thresholdText = candidateMeetsThreshold(candidate)
    ? '达到当前阈值，可作为优先候选复核'
    : `低于当前 ${thresholdPercent.value}% 阈值，仅供人工参考，不会自动通过`
  const reason = String(candidate.reason || '').trim()
  return reason ? `${thresholdText}；匹配原因：${reason}` : thresholdText
}

function bestCandidateScore(review: ItemMappingReviewSummary) {
  const best = Math.max(0, ...review.candidates.map(candidateScore))
  return formatScore(best)
}

function formatDate(value: string | null | undefined) {
  return value ? value.replace('T', ' ').slice(0, 19) : '-'
}

onMounted(reloadAll)
</script>
