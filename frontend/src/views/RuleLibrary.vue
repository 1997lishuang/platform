<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h2>价格规则库</h2>
        <p>维护综合单价规则，支持查询、Excel 导入、批量提交审批、编辑、删除和分页管理。</p>
      </div>
      <div class="header-actions">
        <button class="secondary" @click="loadRules"><RefreshCw :size="17" />刷新</button>
        <button class="secondary" @click="openImportModal"><Upload :size="17" />Excel 导入</button>
        <button class="primary" @click="startCreate"><Plus :size="17" />新增规则</button>
      </div>
    </div>

    <section class="panel">
      <div class="section-head">
        <div>
          <h3>规则列表</h3>
          <p class="field-hint">按规则 ID、清单项、地区、状态、版本、专业工程和费用类别查询规则。</p>
        </div>
        <div class="header-actions rule-bulk-actions">
          <button class="secondary" :disabled="bulkBusy" @click="submitAllForReview">
            <Send :size="17" />全部提交审批
          </button>
          <button class="secondary" :disabled="!selectedRules.length || bulkBusy" @click="submitSelectedForReview">
            <Send :size="17" />提交选中
          </button>
          <button class="danger-button subtle-danger" :disabled="!selectedRules.length || bulkBusy" @click="deleteSelected">
            <Trash2 :size="17" />批量删除
          </button>
        </div>
      </div>

      <div class="rule-filter-grid">
        <label>
          关键词
          <input v-model="filters.keyword" placeholder="规则ID、项目名称、来源、单位" @keyup.enter="search" />
        </label>
        <label>
          状态
          <select v-model="filters.status" @change="search">
            <option value="">全部</option>
            <option value="active">已启用</option>
            <option value="draft">草稿</option>
            <option value="reviewing">待审批</option>
            <option value="rejected">已驳回</option>
          </select>
        </label>
        <label>
          地区
          <select v-model="filters.region_code" @change="search">
            <option value="">全部地区</option>
            <option v-for="region in regionOptions" :key="region.code" :value="region.code">
              {{ region.name }}（{{ region.code }}）
            </option>
          </select>
        </label>
        <label>
          版本
          <input v-model="filters.version" placeholder="如 v1、excel-import" @keyup.enter="search" />
        </label>
        <label>
          专业工程
          <input v-model="filters.specialty" placeholder="如 桩基、土建、安装" @keyup.enter="search" />
        </label>
        <label>
          费用/标段类别
          <input v-model="filters.cost_category" placeholder="如 主体、临建、桩基工程" @keyup.enter="search" />
        </label>
      </div>

      <div class="filter-actions">
        <span>{{ loading ? '正在查询...' : `共 ${total} 条规则，已选 ${selectedRules.length} 条` }}</span>
        <div class="header-actions">
          <button class="secondary" :disabled="loading" @click="resetSearch">重置</button>
          <button class="primary" :disabled="loading" @click="search">查询</button>
        </div>
      </div>

      <div class="table-wrap">
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
              <th>地区</th>
              <th>版本</th>
              <th>状态</th>
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
              <td>
                <strong>{{ rule.item_name_contains }}</strong>
                <div class="muted">{{ rule.source }}</div>
              </td>
              <td>{{ rule.unit || '-' }}</td>
              <td>{{ rule.unit_price }}</td>
              <td>{{ regionLabel(rule.region_code) }}</td>
              <td>{{ rule.version }}</td>
              <td>{{ formatStatus(rule.status) }}</td>
              <td class="conditions-cell">{{ formatConditions(rule.feature_conditions) }}</td>
              <td class="action-cell">
                <button
                  v-if="canSubmit(rule)"
                  class="small-action"
                  :disabled="submittingKey === ruleKey(rule)"
                  @click="submitForReview(rule)"
                >
                  提交审批
                </button>
                <button class="small-action" @click="startEdit(rule)">编辑</button>
                <button class="small-action danger" @click="removeRule(rule)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p v-if="!loading && !rules.length" class="empty">暂无规则</p>
      <div v-if="total > 0" class="pager">
        <span>共 {{ total }} 条，第 {{ page }} / {{ pageCount }} 页</span>
        <div class="pager-actions">
          <button class="secondary" :disabled="page <= 1 || loading" @click="changePage(page - 1)">上一页</button>
          <button class="secondary" :disabled="page >= pageCount || loading" @click="changePage(page + 1)">下一页</button>
        </div>
      </div>
    </section>

    <div v-if="editing" class="modal-backdrop">
      <section class="modal large-modal">
        <div class="modal-head">
          <div>
            <h3>{{ editMode === 'create' ? '新增规则' : '编辑规则' }}</h3>
            <p>维护规则身份、匹配条件和综合单价。保存后可提交审批。</p>
          </div>
          <button class="icon-button" @click="cancelEdit"><X :size="18" /></button>
        </div>

        <div class="modal-body">
          <div class="form-grid">
            <label>
              规则ID
              <input v-model="form.rule_id" :disabled="editMode === 'edit'" />
            </label>
            <label>
              版本
              <input v-model="form.version" :disabled="editMode === 'edit'" />
            </label>
            <label>
              项目名称关键词
              <input v-model="form.item_name_contains" placeholder="如 预制钢筋混凝土桩" />
            </label>
            <label>
              单位
              <input v-model="form.unit" placeholder="如 m、m3、个" />
            </label>
            <label>
              综合单价
              <input v-model="form.unit_price" type="number" min="0" step="0.0001" />
            </label>
            <label>
              地区
              <select v-model="form.region_code">
                <option value="">全国/不限地区</option>
                <option v-for="region in regionOptions" :key="region.code" :value="region.code">
                  {{ region.name }}（{{ region.code }}）
                </option>
              </select>
            </label>
            <label>
              专业工程
              <input v-model="form.specialty" placeholder="如 桩基、土建、安装" />
            </label>
            <label>
              费用/标段类别
              <input v-model="form.cost_category" placeholder="如 主体、临建、桩基工程" />
            </label>
            <label>
              状态
              <select v-model="form.status">
                <option value="draft">草稿</option>
                <option value="active">已启用</option>
                <option value="reviewing">待审批</option>
                <option value="rejected">已驳回</option>
              </select>
            </label>
            <label>
              匹配优先级
              <input v-model.number="form.match_priority" type="number" min="1" />
            </label>
            <label>
              来源
              <input v-model="form.source" placeholder="如 manual、market_quote:xxx" />
            </label>
            <label class="toggle">
              <input v-model="form.active" type="checkbox" />
              启用参与计价
            </label>
          </div>

          <label class="wide-field">
            特征条件
            <textarea
              v-model="featureText"
              rows="5"
              placeholder="一行一个条件，例如：&#10;桩型=PHC-300-AB-70&#10;桩长度=8-10m&#10;混凝土种类与强度等级=C80"
            ></textarea>
          </label>
        </div>

        <div class="modal-foot">
          <button class="secondary" @click="cancelEdit">取消</button>
          <button class="primary" :disabled="saving" @click="saveRule">
            <Save :size="17" />{{ saving ? '保存中' : '保存规则' }}
          </button>
        </div>
      </section>
    </div>

    <div v-if="importingModal" class="modal-backdrop">
      <section class="modal">
        <div class="modal-head">
          <div>
            <h3>Excel 批量导入</h3>
            <p>导入包含项目名称、技术指标、单位、单价的规则表格。</p>
          </div>
          <button class="icon-button" @click="closeImportModal"><X :size="18" /></button>
        </div>

        <div class="modal-body">
          <div class="form-grid compact-grid">
            <label>
              规则表格
              <input type="file" accept=".xlsx,.xlsm" @change="handleImportFile" />
            </label>
            <label>
              导入版本前缀
              <input v-model="importForm.version" placeholder="如 excel-import-2026-07" />
            </label>
            <label>
              导入地区
              <select v-model="importForm.region_code">
                <option value="">全国/不限地区</option>
                <option v-for="region in regionOptions" :key="region.code" :value="region.code">
                  {{ region.name }}（{{ region.code }}）
                </option>
              </select>
            </label>
            <label>
              导入状态
              <select v-model="importForm.status">
                <option value="draft">草稿，后续提交审批</option>
                <option value="reviewing">直接进入待审批</option>
                <option value="active">直接启用</option>
              </select>
            </label>
          </div>
          <p class="field-hint">{{ importFile ? importFile.name : '请选择 .xlsx 或 .xlsm 文件。' }}</p>
        </div>

        <div class="modal-foot">
          <button class="secondary" @click="closeImportModal">取消</button>
          <button class="primary" :disabled="!importFile || importing" @click="importExcel">
            <Upload :size="17" />{{ importing ? '导入中' : '上传并导入' }}
          </button>
        </div>
      </section>
    </div>

    <p v-if="message" class="success">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { Plus, RefreshCw, Save, Send, Trash2, Upload, X } from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import {
  createRule,
  deleteRule,
  deleteRulesBulk,
  fetchRulePage,
  importRulesExcel,
  submitRule,
  submitRulesBulk,
  updateRule,
  type PriceRuleIdentity,
  type PriceRulePayload,
  type PriceRuleSummary
} from '../api/client'
import { regionLabel, regionOptions } from '../regionOptions'

const rules = ref<PriceRuleSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const importingModal = ref(false)
const bulkBusy = ref(false)
const submittingKey = ref('')
const editing = ref(false)
const editMode = ref<'create' | 'edit'>('create')
const featureText = ref('')
const message = ref('')
const error = ref('')
const selectedKeys = ref(new Set<string>())
const selectedMap = ref(new Map<string, PriceRuleIdentity>())

const filters = reactive({
  keyword: '',
  status: '',
  version: '',
  region_code: '',
  specialty: '',
  cost_category: ''
})

const importFile = ref<File | null>(null)
const importForm = reactive({
  version: 'excel-import',
  region_code: '',
  status: 'draft'
})

const form = reactive<PriceRulePayload>({
  rule_id: '',
  version: 'v1',
  status: 'draft',
  region_code: '',
  specialty: '',
  cost_category: '',
  item_name_contains: '',
  unit: '',
  unit_price: '',
  source: 'manual',
  feature_conditions: {},
  match_priority: 100,
  active: false
})

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const selectedRules = computed(() => Array.from(selectedMap.value.values()))
const allPageSelected = computed(() => rules.value.length > 0 && rules.value.every((rule) => selectedKeys.value.has(ruleKey(rule))))

async function loadRules() {
  error.value = ''
  loading.value = true
  try {
    const data = await fetchRulePage({
      keyword: normalizedFilter(filters.keyword),
      status: filters.status || undefined,
      version: normalizedFilter(filters.version),
      region_code: filters.region_code || undefined,
      specialty: normalizedFilter(filters.specialty),
      cost_category: normalizedFilter(filters.cost_category),
      page: page.value,
      page_size: pageSize.value
    })
    rules.value = data.items
    total.value = data.total
    page.value = data.page
    pageSize.value = data.page_size
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : '规则查询失败'
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  clearSelection()
  loadRules()
}

function resetSearch() {
  Object.assign(filters, {
    keyword: '',
    status: '',
    version: '',
    region_code: '',
    specialty: '',
    cost_category: ''
  })
  search()
}

function changePage(nextPage: number) {
  page.value = nextPage
  loadRules()
}

function startCreate() {
  editMode.value = 'create'
  editing.value = true
  Object.assign(form, {
    rule_id: '',
    version: 'v1',
    status: 'draft',
    region_code: '',
    specialty: '',
    cost_category: '',
    item_name_contains: '',
    unit: '',
    unit_price: '',
    source: 'manual',
    feature_conditions: {},
    match_priority: 100,
    active: false
  })
  featureText.value = ''
}

function openImportModal() {
  importingModal.value = true
  importFile.value = null
}

function closeImportModal() {
  if (importing.value) return
  importingModal.value = false
}

function handleImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  importFile.value = input.files?.[0] || null
}

async function importExcel() {
  if (!importFile.value) return
  message.value = ''
  error.value = ''
  importing.value = true
  const formData = new FormData()
  formData.append('file', importFile.value)
  formData.append('version', importForm.version || 'excel-import')
  formData.append('status', importForm.status)
  if (importForm.region_code) formData.append('region_code', importForm.region_code)
  try {
    const result = await importRulesExcel(formData)
    message.value = result.message
    importingModal.value = false
    page.value = 1
    await loadRules()
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : 'Excel 导入失败'
  } finally {
    importing.value = false
  }
}

function startEdit(rule: PriceRuleSummary) {
  editMode.value = 'edit'
  editing.value = true
  Object.assign(form, {
    rule_id: rule.rule_id,
    version: rule.version,
    status: rule.status,
    region_code: rule.region_code || '',
    specialty: rule.specialty || '',
    cost_category: rule.cost_category || '',
    item_name_contains: rule.item_name_contains,
    unit: rule.unit || '',
    unit_price: rule.unit_price,
    source: rule.source,
    feature_conditions: { ...rule.feature_conditions },
    match_priority: 100,
    active: rule.status === 'active'
  })
  featureText.value = Object.entries(rule.feature_conditions)
    .map(([key, value]) => `${key}=${value}`)
    .join('\n')
}

function cancelEdit() {
  editing.value = false
}

async function saveRule() {
  message.value = ''
  error.value = ''
  const payload = normalizePayload()
  if (!payload.rule_id || !payload.version || !payload.item_name_contains || !payload.unit_price) {
    error.value = '规则ID、版本、项目名称关键词和综合单价不能为空'
    return
  }
  saving.value = true
  try {
    if (editMode.value === 'create') {
      await createRule(payload)
      message.value = '规则已新增'
    } else {
      await updateRule(form.rule_id, form.version, payload)
      message.value = '规则已更新'
    }
    editing.value = false
    await loadRules()
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : '规则保存失败'
  } finally {
    saving.value = false
  }
}

async function submitForReview(rule: PriceRuleSummary) {
  message.value = ''
  error.value = ''
  submittingKey.value = ruleKey(rule)
  try {
    await submitRule(rule.rule_id, rule.version)
    message.value = '规则已提交审批，可到规则审批页面处理'
    removeSelected(rule)
    await loadRules()
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : '提交审批失败'
  } finally {
    submittingKey.value = ''
  }
}

async function submitSelectedForReview() {
  if (!selectedRules.value.length) return
  await runBulk(async () => submitRulesBulk({ items: selectedRules.value }), '选中规则已提交审批')
}

async function submitAllForReview() {
  if (!window.confirm('确认将当前筛选条件下所有草稿/驳回规则提交审批？')) return
  await runBulk(
    async () => submitRulesBulk({
      all_matching: true,
      status: filters.status || undefined,
      version: normalizedFilter(filters.version),
      region_code: filters.region_code || undefined,
      specialty: normalizedFilter(filters.specialty),
      cost_category: normalizedFilter(filters.cost_category),
      keyword: normalizedFilter(filters.keyword)
    }),
    '符合条件的规则已提交审批'
  )
}

async function deleteSelected() {
  if (!selectedRules.value.length) return
  if (!window.confirm(`确认删除选中的 ${selectedRules.value.length} 条规则记录？旧版本删除后不可恢复。`)) return
  await runBulk(async () => deleteRulesBulk({ items: selectedRules.value }), '选中规则已删除')
}

async function runBulk(action: () => Promise<{ message: string }>, fallback: string) {
  message.value = ''
  error.value = ''
  bulkBusy.value = true
  try {
    const result = await action()
    message.value = result.message || fallback
    clearSelection()
    await loadRules()
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : '批量操作失败'
  } finally {
    bulkBusy.value = false
  }
}

async function removeRule(rule: PriceRuleSummary) {
  if (!window.confirm(`确认删除规则 ${rule.rule_id} / ${rule.version}？`)) return
  error.value = ''
  message.value = ''
  try {
    await deleteRule(rule.rule_id, rule.version)
    message.value = '规则已删除'
    removeSelected(rule)
    await loadRules()
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : '规则删除失败'
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

function normalizePayload(): PriceRulePayload {
  return {
    ...form,
    region_code: form.region_code || null,
    specialty: form.specialty || null,
    cost_category: form.cost_category || null,
    unit: form.unit || null,
    source: form.source || 'manual',
    active: form.status === 'active' && form.active,
    feature_conditions: parseFeatureText(featureText.value)
  }
}

function parseFeatureText(text: string) {
  const result: Record<string, string> = {}
  for (const line of text.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const separatorIndex = trimmed.indexOf('=')
    if (separatorIndex <= 0) continue
    const key = trimmed.slice(0, separatorIndex).trim()
    const value = trimmed.slice(separatorIndex + 1).trim()
    if (key && value) result[key] = value
  }
  return result
}

function formatConditions(conditions: Record<string, string>) {
  const entries = Object.entries(conditions)
  if (!entries.length) return '-'
  return entries.map(([key, value]) => `${key}=${value}`).join('；')
}

function formatStatus(status: string) {
  if (status === 'active') return '已启用'
  if (status === 'draft') return '草稿'
  if (status === 'reviewing') return '待审批'
  if (status === 'rejected') return '已驳回'
  return status
}

function canSubmit(rule: PriceRuleSummary) {
  return rule.status === 'draft' || rule.status === 'rejected'
}

function ruleKey(rule: PriceRuleSummary | PriceRuleIdentity) {
  return `${rule.rule_id}-${rule.version}`
}

function normalizedFilter(value: string) {
  const trimmed = value.trim()
  return trimmed || undefined
}

onMounted(loadRules)
</script>
