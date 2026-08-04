<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h2>计价工作台</h2>
        <p>上传工程量清单，系统自动匹配价格规则；低置信度进入映射校准，缺价项进入市场询价复核。</p>
      </div>
      <button class="primary" :disabled="!file || loading" @click="runPricing">
        <Play :size="17" />
        {{ loading ? '已提交' : '开始计价' }}
      </button>
    </div>

    <div class="workbench-grid">
      <section class="panel upload-panel">
        <h3>清单文件</h3>
        <label class="drop-zone">
          <UploadCloud :size="30" />
          <span>{{ file?.name || '选择 .xlsx 工程量清单' }}</span>
          <input type="file" accept=".xlsx,.xls" @change="onFileChange" />
        </label>
      </section>

      <section class="panel">
        <h3>工程项目维度</h3>
        <div class="form-grid">
          <label>企业编码<input v-model="form.tenantCode" /></label>
          <label>工程项目名称<input v-model="form.projectName" /></label>
          <label>计价地区
            <select v-model="form.regionCode">
              <option v-for="region in regionOptions" :key="region.code" :value="region.code">
                {{ region.name }}（{{ region.code }}） - {{ region.scope }}
              </option>
            </select>
          </label>
          <label>专业/工程<input v-model="form.specialty" placeholder="如 桩基、土建、安装" /></label>
          <label>费用/标段类别<input v-model="form.costCategory" placeholder="如 主体、临建、桩基工程" /></label>
          <label>价库规则版本
            <select v-model="form.ruleVersion" :disabled="versionLoading">
              <option value="">留空则使用全部可用版本</option>
              <option v-for="version in ruleVersions" :key="`${version.version}-${version.status}`" :value="version.version">
                {{ version.version }} - {{ version.status }} / {{ version.rule_count }} 条
              </option>
            </select>
            <span v-if="versionError" class="field-hint">{{ versionError }}</span>
          </label>
        </div>
        <label class="toggle">
          <input v-model="form.writeAudit" type="checkbox" />
          完成后写入 MySQL 审计
        </label>
      </section>
    </div>

    <section class="panel task-center">
      <div class="section-head">
        <div>
          <h3>计价任务</h3>
          <p class="field-hint">可展开不同状态的任务，选择任一任务查看进度、停止或恢复计价。</p>
        </div>
        <button class="secondary" :disabled="tasksLoading" @click="loadTasks">
          <RefreshCw :size="17" />刷新任务
        </button>
      </div>

      <div v-if="tasksLoading && !tasks.length" class="empty">正在加载计价任务...</div>
      <div v-else-if="!tasks.length" class="empty">暂无计价任务</div>
      <div v-else class="task-groups">
        <section v-for="group in taskGroups" :key="group.key" class="task-group">
          <button class="task-group-head" @click="toggleTaskGroup(group.key)">
            <component :is="collapsedTaskGroups.includes(group.key) ? ChevronRight : ChevronDown" :size="18" />
            <span>{{ group.title }}</span>
            <strong>{{ group.items.length }}</strong>
          </button>
          <div v-if="!collapsedTaskGroups.includes(group.key)" class="task-list">
            <article
              v-for="item in group.items"
              :key="item.task_code"
              :class="['task-card', { active: task?.task_code === item.task_code }]"
              @click="selectTask(item)"
            >
              <div class="task-card-main">
                <div>
                  <strong>{{ item.project_name || item.workbook_name || '未命名任务' }}</strong>
                  <span>{{ shortCode(item.task_code) }}</span>
                </div>
                <span class="status-pill" :data-status="item.status">{{ taskStatusText(item.status) }}</span>
              </div>
              <div class="progress compact-progress"><span :style="{ width: `${item.progress}%` }"></span></div>
              <div class="task-card-metrics">
                <span>清单 {{ item.item_count }}</span>
                <span>已取价 {{ item.priced_count }}</span>
                <span>待处理 {{ item.unpriced_count }}</span>
              </div>
              <div class="task-card-meta">
                <span>{{ item.region_code || '-' }}</span>
                <span>{{ formatDate(item.created_at) }}</span>
              </div>
              <div v-if="task?.task_code === item.task_code && (canCancel(item) || canResume(item))" class="task-card-actions">
                <button v-if="canCancel(item)" class="secondary" :disabled="cancelingTask" @click.stop="cancelTask(item)">
                  <Square :size="15" />停止
                </button>
                <button v-if="canResume(item)" class="secondary" :disabled="resumingTask" @click.stop="resumeTask(item)">
                  <RotateCcw :size="15" />恢复计价
                </button>
              </div>
            </article>
          </div>
        </section>
      </div>
    </section>

    <section v-if="task" class="panel">
      <div class="status-head">
        <h3>当前任务状态</h3>
        <div class="inline-actions">
          <button v-if="canResumeTask" class="secondary" :disabled="resumingTask" @click="resumeCurrentTask">
            <RotateCcw :size="17" />恢复计价
          </button>
          <button v-if="canCancelTask" class="secondary danger" :disabled="cancelingTask" @click="cancelCurrentTask">
            <Square :size="16" />停止任务
          </button>
          <span class="status-pill" :data-status="task.status">{{ statusText }}</span>
        </div>
      </div>
      <p>{{ task.message || '正在等待任务状态更新' }}</p>
      <div class="progress"><span :style="{ width: `${task.progress}%` }"></span></div>
      <div v-if="task.failure_reasons?.length" class="failure-box">
        <strong>处理提示</strong>
        <p v-for="reason in task.failure_reasons" :key="reason">{{ reason }}</p>
      </div>
    </section>

    <section v-if="mappingAmbiguities.length" class="attention-panel">
      <div>
        <strong><Braces :size="18" />存在映射歧义，需要人工校准</strong>
        <p>系统已生成映射校准记录。完成校准后回到本页，选择该任务并点击“恢复计价”。</p>
      </div>
      <RouterLink class="secondary" to="/item-mappings">去映射校准</RouterLink>
    </section>

    <section v-if="needsManualMarketQuote" class="attention-panel">
      <div>
        <strong><AlertTriangle :size="18" />规则库缺少价格，需要补充市场询价或价格规则</strong>
        <p>请先在市场询价页人工获取参考价并复核，或在价格规则库导入并审批对应规则；补完后回到本页恢复计价。</p>
      </div>
      <RouterLink class="secondary" :to="marketQuoteLink">去市场询价</RouterLink>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="task" class="result-strip">
      <div><strong>{{ task.item_count }}</strong><span>清单项</span></div>
      <div><strong>{{ task.priced_count }}</strong><span>已取价</span></div>
      <div><strong>{{ task.unpriced_count }}</strong><span>待处理</span></div>
      <div><strong>{{ shortCode(task.task_code) }}</strong><span>批次号</span></div>
    </div>

    <div v-if="task?.excel_path || task?.missing_rules_path || task?.audit_path" class="output-grid">
      <div v-if="task.excel_path" class="output-card">
        <FileSpreadsheet :size="20" /><span>结果文件</span><code>{{ task.excel_path }}</code>
      </div>
      <div v-if="task.missing_rules_path" class="output-card">
        <FileWarning :size="20" /><span>缺价清单</span><code>{{ task.missing_rules_path }}</code>
      </div>
      <div v-if="task.audit_path" class="output-card">
        <FileSpreadsheet :size="20" /><span>审计文件</span><code>{{ task.audit_path }}</code>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import {
  AlertTriangle,
  Braces,
  ChevronDown,
  ChevronRight,
  FileSpreadsheet,
  FileWarning,
  Play,
  RefreshCw,
  RotateCcw,
  Square,
  UploadCloud
} from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import {
  cancelPricingTask,
  fetchPricingTask,
  fetchPricingTasks,
  fetchRuleVersions,
  resumePricingTask,
  submitPricingTask,
  type PriceRuleVersionSummary,
  type PricingTaskStatus
} from '../api/client'
import { regionOptions } from '../regionOptions'

type TaskGroup = {
  key: string
  title: string
  items: PricingTaskStatus[]
}

const file = ref<File | null>(null)
const loading = ref(false)
const tasksLoading = ref(false)
const cancelingTask = ref(false)
const resumingTask = ref(false)
const error = ref('')
const task = ref<PricingTaskStatus | null>(null)
const tasks = ref<PricingTaskStatus[]>([])
const collapsedTaskGroups = ref<string[]>(['completed'])
const ruleVersions = ref<PriceRuleVersionSummary[]>([])
const versionLoading = ref(false)
const versionError = ref('')
let pollTimer: number | undefined

const form = reactive({
  tenantCode: 'default',
  projectName: '中广核叶集区集安200MW光伏项目',
  regionCode: 'CN',
  specialty: '',
  costCategory: '',
  ruleVersion: '',
  writeAudit: true
})

const statusText = computed(() => taskStatusText(task.value?.status || ''))
const taskGroups = computed<TaskGroup[]>(() => [
  {
    key: 'active',
    title: '进行中',
    items: tasks.value.filter((item) => ['pending', 'running'].includes(item.status))
  },
  {
    key: 'waiting',
    title: '待人工处理',
    items: tasks.value.filter((item) => ['waiting_mapping', 'waiting_market_quote'].includes(item.status))
  },
  {
    key: 'stopped',
    title: '异常或已停止',
    items: tasks.value.filter((item) => ['failed', 'canceled'].includes(item.status))
  },
  {
    key: 'completed',
    title: '已完成',
    items: tasks.value.filter((item) => item.status === 'succeeded')
  }
].filter((group) => group.items.length > 0))

const mappingAmbiguities = computed(() =>
  (task.value?.failure_reasons || []).filter((reason) =>
    reason.includes('映射存在歧义') || reason.includes('映射置信度不足') || reason.includes('ITEM_MAPPING')
  )
)

const needsManualMarketQuote = computed(() => {
  const message = task.value?.message || ''
  return (
    task.value?.status === 'waiting_market_quote' &&
    (message.includes('BOQ_AUTO_MARKET_QUOTE_LIMIT=0') ||
      message.includes('未自动调用模型') ||
      message.includes('暂未生成可复核报价'))
  )
})

const canCancelTask = computed(() => task.value ? canCancel(task.value) : false)
const canResumeTask = computed(() => task.value ? canResume(task.value) : false)
const marketQuoteLink = computed(() => ({
  path: '/market-quotes',
  query: task.value?.task_code ? { task_code: task.value.task_code } : {}
}))

async function loadRuleVersions() {
  versionLoading.value = true
  versionError.value = ''
  try {
    ruleVersions.value = await fetchRuleVersions({
      tenant_code: form.tenantCode,
      status: 'active'
    })
    if (ruleVersions.value.length === 0) {
      versionError.value = '暂无已启用规则版本，请先在价格规则库提交并审批规则'
    }
  } catch (caught) {
    ruleVersions.value = []
    versionError.value = caught instanceof Error ? caught.message : '版本列表加载失败，可留空使用全部版本'
  } finally {
    versionLoading.value = false
  }
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    const loaded = await fetchPricingTasks()
    tasks.value = loaded
    if (!task.value && loaded.length) {
      const restored = loaded.find(shouldAutoShowTask) || loaded[0]
      selectTask(restored)
    } else if (task.value) {
      const current = loaded.find((item) => item.task_code === task.value?.task_code)
      if (current) task.value = current
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '计价任务加载失败'
  } finally {
    tasksLoading.value = false
  }
}

function shouldAutoShowTask(item: PricingTaskStatus) {
  return ['pending', 'running', 'waiting_mapping', 'waiting_market_quote'].includes(item.status)
}

function shouldPollTask(item: PricingTaskStatus) {
  return item.status === 'pending' || item.status === 'running'
}

function canCancel(item: PricingTaskStatus) {
  return item.status === 'pending' || item.status === 'running'
}

function canResume(item: PricingTaskStatus) {
  return ['canceled', 'failed', 'waiting_market_quote', 'waiting_mapping'].includes(item.status)
}

function selectTask(item: PricingTaskStatus) {
  task.value = item
  syncFormFromTask(item)
  if (shouldPollTask(item)) {
    loading.value = true
    startPolling(item.task_code)
  } else {
    loading.value = false
    stopPolling()
  }
}

function syncFormFromTask(item: PricingTaskStatus) {
  form.tenantCode = 'default'
  form.projectName = item.project_name || form.projectName
  form.regionCode = item.region_code || form.regionCode
}

function toggleTaskGroup(key: string) {
  collapsedTaskGroups.value = collapsedTaskGroups.value.includes(key)
    ? collapsedTaskGroups.value.filter((item) => item !== key)
    : [...collapsedTaskGroups.value, key]
}

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  file.value = target.files?.[0] || null
}

async function runPricing() {
  if (!file.value) return
  loading.value = true
  error.value = ''
  const payload = new FormData()
  payload.append('file', file.value)
  payload.append('tenant_code', form.tenantCode)
  payload.append('project_name', form.projectName)
  payload.append('region_code', form.regionCode)
  payload.append('specialty', form.specialty)
  payload.append('cost_category', form.costCategory)
  payload.append('rule_version', form.ruleVersion)
  try {
    const accepted = await submitPricingTask(payload)
    const draft: PricingTaskStatus = {
      task_code: accepted.task_code,
      status: accepted.status,
      progress: accepted.progress,
      message: accepted.message,
      workbook_name: file.value.name,
      project_name: form.projectName,
      region_code: form.regionCode,
      item_count: 0,
      priced_count: 0,
      unpriced_count: 0,
      excel_path: null,
      missing_rules_path: null,
      audit_path: null,
      mysql_run_code: null,
      failure_reasons: [],
      created_at: new Date().toISOString(),
      started_at: null,
      finished_at: null
    }
    task.value = draft
    replaceTask(draft)
    await loadTasks()
    startPolling(accepted.task_code)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '计价失败'
    loading.value = false
  }
}

async function cancelCurrentTask() {
  if (!task.value) return
  await cancelTask(task.value)
}

async function cancelTask(item: PricingTaskStatus) {
  if (!canCancel(item)) return
  cancelingTask.value = true
  error.value = ''
  try {
    const updated = await cancelPricingTask(item.task_code)
    task.value = updated
    replaceTask(updated)
    loading.value = false
    stopPolling()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '停止任务失败'
  } finally {
    cancelingTask.value = false
  }
}

async function resumeCurrentTask() {
  if (!task.value) return
  await resumeTask(task.value)
}

async function resumeTask(item: PricingTaskStatus) {
  if (!canResume(item)) return
  resumingTask.value = true
  error.value = ''
  try {
    const updated = await resumePricingTask(item.task_code)
    task.value = updated
    replaceTask(updated)
    loading.value = true
    startPolling(updated.task_code)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '恢复计价失败'
  } finally {
    resumingTask.value = false
  }
}

function replaceTask(updated: PricingTaskStatus) {
  const index = tasks.value.findIndex((item) => item.task_code === updated.task_code)
  if (index >= 0) {
    tasks.value.splice(index, 1, updated)
  } else {
    tasks.value.unshift(updated)
  }
}

function startPolling(taskCode: string) {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    try {
      const updated = await fetchPricingTask(taskCode)
      task.value = updated
      replaceTask(updated)
      if (!shouldPollTask(updated)) {
        loading.value = false
        stopPolling()
        await loadTasks()
      }
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : '任务状态查询失败'
      loading.value = false
      stopPolling()
    }
  }, 1500)
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
}

function taskStatusText(status: string) {
  if (status === 'pending') return '等待处理'
  if (status === 'running') return '处理中'
  if (status === 'waiting_mapping') return '等待映射校准'
  if (status === 'waiting_market_quote') return '等待询价复核'
  if (status === 'succeeded') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'canceled') return '已停止'
  return '未提交'
}

function shortCode(value: string) {
  return value.length > 12 ? `${value.slice(0, 12)}...` : value
}

function formatDate(value: string) {
  return value ? value.replace('T', ' ').slice(0, 19) : '-'
}

onBeforeUnmount(() => {
  stopPolling()
})

onMounted(() => {
  loadRuleVersions()
  loadTasks()
})

watch(
  () => form.tenantCode,
  () => {
    loadRuleVersions()
  }
)
</script>
