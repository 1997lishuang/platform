<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h2>规则审批</h2>
        <p>审核已提交的综合单价规则，通过后进入价格规则库并参与自动计价。</p>
      </div>
      <div class="header-actions">
        <button class="secondary" @click="loadReviewing"><RefreshCw :size="17" />刷新</button>
      </div>
    </div>

    <section class="panel">
      <div class="section-head">
        <h3>审批筛选</h3>
      </div>
      <div class="form-grid">
        <label>
          关键词
          <input v-model="filters.keyword" placeholder="规则ID或项目名称关键词" @keyup.enter="search" />
        </label>
        <label>
          版本
          <input v-model="filters.version" placeholder="如 excel-import-202607" @keyup.enter="search" />
        </label>
      </div>
    </section>

    <section class="panel">
      <div class="section-head">
        <h3>待审批规则</h3>
        <div class="header-actions rule-bulk-actions">
          <button class="secondary" :disabled="bulkBusy" @click="approveAll">
            <CheckCheck :size="17" />全部通过
          </button>
          <button class="danger-button subtle-danger" :disabled="bulkBusy" @click="rejectAll">
            <XCircle :size="17" />全部驳回
          </button>
          <button class="secondary" :disabled="!selectedRules.length || bulkBusy" @click="approveSelected">
            <Check :size="17" />选择通过
          </button>
          <button class="danger-button subtle-danger" :disabled="!selectedRules.length || bulkBusy" @click="rejectSelected">
            <X :size="17" />选择驳回
          </button>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th class="select-col">
              <input type="checkbox" :checked="allPageSelected" @change="toggleCurrentPage" />
            </th>
            <th>规则ID</th>
            <th>项目名称关键词</th>
            <th>单位</th>
            <th>单价</th>
            <th>版本</th>
            <th>提交人</th>
            <th>特征条件</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rule in rules" :key="ruleKey(rule)">
            <td class="select-col">
              <input
                type="checkbox"
                :checked="selectedKeys.has(ruleKey(rule))"
                @change="toggleRule(rule)"
              />
            </td>
            <td>{{ rule.rule_id }}</td>
            <td>{{ rule.item_name_contains }}</td>
            <td>{{ rule.unit || '-' }}</td>
            <td>{{ rule.unit_price }}</td>
            <td>{{ rule.version }}</td>
            <td>{{ rule.submitted_by || '-' }}</td>
            <td class="conditions-cell">{{ formatConditions(rule.feature_conditions) }}</td>
            <td class="action-cell">
              <button class="small-action" @click="approve(rule)">
                <Check :size="16" />通过
              </button>
              <button class="small-action danger" @click="reject(rule)">
                <X :size="16" />驳回
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!rules.length" class="empty">暂无待审批规则。请先在价格规则库中将草稿规则提交审批。</p>
      <div v-if="total > 0" class="pager">
        <span>共 {{ total }} 条，第 {{ page }} / {{ pageCount }} 页，已选 {{ selectedRules.length }} 条</span>
        <div class="pager-actions">
          <button class="secondary" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
          <button class="secondary" :disabled="page >= pageCount" @click="changePage(page + 1)">下一页</button>
        </div>
      </div>
    </section>

    <p v-if="message" class="success">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { Check, CheckCheck, RefreshCw, X, XCircle } from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  approveRule,
  approveRulesBulk,
  fetchRulePage,
  rejectRule,
  rejectRulesBulk,
  type PriceRuleIdentity,
  type PriceRuleSummary
} from '../api/client'

const rules = ref<PriceRuleSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const bulkBusy = ref(false)
const message = ref('')
const error = ref('')
const selectedKeys = ref(new Set<string>())
const selectedMap = ref(new Map<string, PriceRuleIdentity>())

const filters = reactive({
  keyword: '',
  version: ''
})

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const selectedRules = computed(() => Array.from(selectedMap.value.values()))
const allPageSelected = computed(() => rules.value.length > 0 && rules.value.every((rule) => selectedKeys.value.has(ruleKey(rule))))

async function loadReviewing() {
  error.value = ''
  const data = await fetchRulePage({
    status: 'reviewing',
    keyword: filters.keyword || undefined,
    version: filters.version || undefined,
    page: page.value,
    page_size: pageSize
  })
  rules.value = data.items
  total.value = data.total
}

function search() {
  page.value = 1
  loadReviewing()
}

function changePage(nextPage: number) {
  page.value = nextPage
  loadReviewing()
}

async function approve(rule: PriceRuleSummary) {
  message.value = ''
  error.value = ''
  try {
    await approveRule(rule.rule_id, rule.version, '审批通过')
    message.value = '规则已通过'
    removeSelected(rule)
    await loadReviewing()
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : '审批通过失败'
  }
}

async function reject(rule: PriceRuleSummary) {
  message.value = ''
  error.value = ''
  try {
    await rejectRule(rule.rule_id, rule.version, '请补充价格来源或特征条件')
    message.value = '规则已驳回'
    removeSelected(rule)
    await loadReviewing()
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : '审批驳回失败'
  }
}

async function approveSelected() {
  if (!selectedRules.value.length) return
  await runBulk(() => approveRulesBulk({ items: selectedRules.value, comment: '批量审批通过' }), '选中规则已通过')
}

async function rejectSelected() {
  if (!selectedRules.value.length) return
  const comment = window.prompt('请输入批量驳回原因', '请补充价格来源或特征条件')
  if (comment === null) return
  await runBulk(() => rejectRulesBulk({ items: selectedRules.value, comment }), '选中规则已驳回')
}

async function approveAll() {
  if (!window.confirm('确认通过当前筛选条件下的全部待审批规则？')) return
  await runBulk(
    () => approveRulesBulk({
      all_matching: true,
      status: 'reviewing',
      version: filters.version || undefined,
      keyword: filters.keyword || undefined,
      comment: '批量审批通过'
    }),
    '符合条件的规则已全部通过'
  )
}

async function rejectAll() {
  const comment = window.prompt('请输入全部驳回原因', '请补充价格来源或特征条件')
  if (comment === null) return
  if (!window.confirm('确认驳回当前筛选条件下的全部待审批规则？')) return
  await runBulk(
    () => rejectRulesBulk({
      all_matching: true,
      status: 'reviewing',
      version: filters.version || undefined,
      keyword: filters.keyword || undefined,
      comment
    }),
    '符合条件的规则已全部驳回'
  )
}

async function runBulk(action: () => Promise<{ message: string }>, fallback: string) {
  message.value = ''
  error.value = ''
  bulkBusy.value = true
  try {
    const result = await action()
    message.value = result.message || fallback
    clearSelection()
    await loadReviewing()
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : '批量审批失败'
  } finally {
    bulkBusy.value = false
  }
}

function toggleRule(rule: PriceRuleSummary) {
  if (selectedKeys.value.has(ruleKey(rule))) {
    removeSelected(rule)
  } else {
    addSelected(rule)
  }
}

function toggleCurrentPage() {
  if (allPageSelected.value) {
    for (const rule of rules.value) removeSelected(rule)
  } else {
    for (const rule of rules.value) addSelected(rule)
  }
}

function addSelected(rule: PriceRuleSummary) {
  const key = ruleKey(rule)
  const keys = new Set(selectedKeys.value)
  const map = new Map(selectedMap.value)
  keys.add(key)
  map.set(key, { rule_id: rule.rule_id, version: rule.version })
  selectedKeys.value = keys
  selectedMap.value = map
}

function removeSelected(rule: PriceRuleSummary) {
  const key = ruleKey(rule)
  const keys = new Set(selectedKeys.value)
  const map = new Map(selectedMap.value)
  keys.delete(key)
  map.delete(key)
  selectedKeys.value = keys
  selectedMap.value = map
}

function clearSelection() {
  selectedKeys.value = new Set()
  selectedMap.value = new Map()
}

function formatConditions(conditions: Record<string, string>) {
  const entries = Object.entries(conditions)
  if (!entries.length) return '-'
  return entries.map(([key, value]) => `${key}=${value}`).join('；')
}

function ruleKey(rule: PriceRuleSummary | PriceRuleIdentity) {
  return `${rule.rule_id}-${rule.version}`
}

onMounted(loadReviewing)
</script>
