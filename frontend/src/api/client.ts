import axios from 'axios'
import { readStoredUser, setCurrentUser } from '../authState'

export const api = axios.create({
  baseURL: '/api',
  timeout: 120000
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('boq_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && window.location.pathname !== '/login') {
      localStorage.removeItem('boq_access_token')
      setCurrentUser(null)
      window.location.href = '/login'
    }
    const detail = error.response?.data?.detail
    if (detail) {
      return Promise.reject(new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)))
    }
    return Promise.reject(error)
  }
)

export interface LoginResponse {
  access_token: string
  token_type: string
  username: string
  display_name: string | null
  role: string
  tenant_code: string
}

export interface ManagedUser {
  username: string
  display_name: string | null
  role: string
  active: boolean
  role_active: boolean
  last_login_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ManagedUserPage {
  items: ManagedUser[]
  total: number
  page: number
  page_size: number
}

export async function login(payload: { username: string; password: string; tenant_code: string }) {
  const { data } = await api.post<LoginResponse>('/auth/login', payload)
  localStorage.setItem('boq_access_token', data.access_token)
  setCurrentUser(data)
  return data
}

export async function fetchCurrentUser() {
  const { data } = await api.get<Omit<LoginResponse, 'access_token' | 'token_type'>>('/auth/me')
  setCurrentUser({ ...data, access_token: localStorage.getItem('boq_access_token') || '', token_type: 'bearer' })
  return data
}

export function getStoredUser(): LoginResponse | null {
  return readStoredUser()
}

export function logout() {
  localStorage.removeItem('boq_access_token')
  setCurrentUser(null)
}

export async function fetchUserPage(payload: {
  keyword?: string
  role?: string
  active?: string
  page: number
  page_size: number
}) {
  const { data } = await api.get<ManagedUserPage>('/users', { params: payload })
  return data
}

export async function createManagedUser(payload: {
  username: string
  display_name?: string | null
  password: string
  role: string
  active: boolean
}) {
  const { data } = await api.post<ManagedUser>('/users', payload)
  return data
}

export async function updateManagedUser(username: string, payload: {
  display_name?: string | null
  role: string
  active: boolean
}) {
  const { data } = await api.put<ManagedUser>(`/users/${encodeURIComponent(username)}`, payload)
  return data
}

export async function resetManagedUserPassword(username: string, password: string) {
  const { data } = await api.patch<ManagedUser>(`/users/${encodeURIComponent(username)}/password`, { password })
  return data
}

export async function deleteManagedUser(username: string) {
  const { data } = await api.delete<ManagedUser>(`/users/${encodeURIComponent(username)}`)
  return data
}

export interface PricingRunResponse {
  item_count: number
  priced_count: number
  unpriced_count: number
  issue_counts: Record<string, number>
  excel_path: string
  missing_rules_path: string
  audit_path: string
  mysql_run_code: string | null
}

export interface PricingTaskAccepted {
  task_code: string
  status: string
  progress: number
  message: string | null
}

export interface PricingTaskStatus {
  task_code: string
  status: string
  progress: number
  message: string | null
  workbook_name: string
  project_name: string | null
  region_code: string | null
  item_count: number
  priced_count: number
  unpriced_count: number
  excel_path: string | null
  missing_rules_path: string | null
  audit_path: string | null
  mysql_run_code: string | null
  failure_reasons: string[]
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface PriceRuleSummary {
  rule_id: string
  version: string
  status: string
  region_code: string | null
  specialty: string | null
  cost_category: string | null
  item_name_contains: string
  unit: string | null
  unit_price: string
  source: string
  feature_conditions: Record<string, string>
  created_by: string | null
  submitted_by: string | null
  reviewed_by: string | null
  review_comment: string | null
}

export interface PriceRulePage {
  items: PriceRuleSummary[]
  total: number
  page: number
  page_size: number
}

export interface PriceRuleVersionSummary {
  version: string
  status: string
  rule_count: number
}

export interface PriceRuleImportResponse {
  imported_count: number
  skipped_count: number
  message: string
}

export interface PriceRuleIdentity {
  rule_id: string
  version: string
}

export interface PriceRuleBulkActionResponse {
  affected_count: number
  skipped_count: number
  message: string
}

export interface ItemMappingSummary {
  mapping_code: string
  source_item_name: string
  standard_item_name: string
  match_keywords: string[]
  unit: string | null
  feature_conditions: Record<string, string>
  status: string
  priority: number
  active: boolean
  created_by: string | null
  submitted_by: string | null
  reviewed_by: string | null
  review_comment: string | null
}

export interface ItemMappingPage {
  items: ItemMappingSummary[]
  total: number
  page: number
  page_size: number
}

export interface ItemMappingSettingSummary {
  confidence_threshold: string
}

export interface ItemMappingPayload {
  mapping_code: string
  source_item_name: string
  standard_item_name: string
  match_keywords: string[]
  unit?: string | null
  feature_conditions: Record<string, string>
  status: string
  priority: number
  active: boolean
}

export interface ItemMappingReviewSummary {
  review_code: string
  pricing_task_code: string | null
  workbook_name: string | null
  source_sheet: string | null
  source_row_number: number | null
  source_item_name: string
  unit: string | null
  features: Record<string, unknown>
  candidates: Array<Record<string, unknown>>
  selected_standard_item_name: string | null
  status: string
  persisted: boolean
  reviewed_by: string | null
  review_comment: string | null
  created_at: string
  reviewed_at: string | null
}

export interface ItemMappingReviewPage {
  items: ItemMappingReviewSummary[]
  total: number
  page: number
  page_size: number
}

export interface PricingRunSummary {
  run_code: string
  project_name: string | null
  region_code: string | null
  item_count: number
  priced_count: number
  unpriced_count: number
  created_at: string
  updated_at: string
}

export interface PricingResultSummary {
  source_sheet: string
  source_row_number: number
  sequence_no: string | null
  item_code: string | null
  item_name: string
  unit: string | null
  quantity: string | null
  unit_price: string | null
  total_price: string | null
  rule_code: string | null
  rule_version: string | null
  price_source: string | null
  confidence: string
  features: Record<string, unknown>
  issues: string[]
}

export interface PricingRunDetail extends PricingRunSummary {
  workbook_name: string
  rule_source: string
  rule_version: string | null
  results: PricingResultSummary[]
}

export interface MarketQuoteSummary {
  quote_code: string
  pricing_task_code: string | null
  provider: string
  model: string
  item_name: string
  unit: string | null
  region_code: string | null
  price_min: string | null
  price_max: string | null
  recommended_price: string | null
  tax_included: boolean
  confidence: string
  source_urls: string[]
  assumptions: Record<string, unknown>
  status: string
  created_by: string | null
  reviewed_by: string | null
  review_comment: string | null
  created_at: string
}

export interface MarketQuoteTaskTarget {
  task_code: string
  source_sheet: string
  source_row_number: number
  item_name: string
  unit: string | null
  quantity: string | null
  features: Record<string, unknown>
  issues: string[]
}

export interface MarketQuotePage {
  items: MarketQuoteSummary[]
  total: number
  page: number
  page_size: number
}

export interface ExcelMarketQuoteResponse {
  item_count: number
  quoted_count: number
  failed_count: number
  output_path: string
}

export interface PlatformConfigSummary {
  provider: string
  display_name: string
  base_url: string
  model: string
  api_key_configured: boolean
  endpoint_type: string
  enable_web_search: boolean
  search_tool_type: string | null
  timeout_seconds: number
  active: boolean
  remark: string | null
  updated_by: string | null
  updated_at: string
}

export interface ModelCallLogSummary {
  call_code: string
  provider: string
  model: string
  scenario: string
  task_code: string | null
  item_name: string | null
  status: string
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  duration_ms: number | null
  response_excerpt: string | null
  error_message: string | null
  created_by: string | null
  created_at: string
  finished_at: string | null
}

export interface ModelCallLogPage {
  items: ModelCallLogSummary[]
  total: number
  page: number
  page_size: number
}

export async function submitPricingRun(form: FormData) {
  const { data } = await api.post<PricingRunResponse>('/pricing/runs', form)
  return data
}

export async function submitPricingTask(form: FormData) {
  const { data } = await api.post<PricingTaskAccepted>('/pricing/tasks', form)
  return data
}

export async function fetchPricingTask(taskCode: string) {
  const { data } = await api.get<PricingTaskStatus>(`/pricing/tasks/${taskCode}`)
  return data
}

export async function fetchPricingTasks() {
  const { data } = await api.get<PricingTaskStatus[]>('/pricing/tasks')
  return data
}

export async function cancelPricingTask(taskCode: string) {
  const { data } = await api.post<PricingTaskStatus>(`/pricing/tasks/${taskCode}/cancel`)
  return data
}

export async function resumePricingTask(taskCode: string) {
  const { data } = await api.post<PricingTaskStatus>(`/pricing/tasks/${taskCode}/resume`)
  return data
}

export async function estimateMarketQuote(payload: {
  provider?: string
  item_name: string
  unit?: string
  region?: string
  price_month?: string
  standard?: string
  features: Record<string, string>
  pricing_task_code?: string
}) {
  const { data } = await api.post<MarketQuoteSummary>('/market-quotes/estimate', payload, {
    params: payload.provider ? { provider: payload.provider } : undefined,
    headers: { 'x-user': 'estimator', 'x-user-role': 'estimator' }
  })
  return data
}

export async function fetchMarketQuoteTargets(taskCode: string) {
  const { data } = await api.get<MarketQuoteTaskTarget[]>(
    `/market-quotes/tasks/${encodeURIComponent(taskCode)}/targets`
  )
  return data
}

export async function fetchMarketQuotes(status?: string) {
  const { data } = await api.get<MarketQuoteSummary[]>('/market-quotes', {
    params: status ? { status } : undefined
  })
  return data
}

export async function fetchMarketQuotePage(payload: {
  status?: string
  page: number
  page_size: number
}) {
  const { data } = await api.get<MarketQuotePage>('/market-quotes/page', {
    params: {
      status: payload.status,
      page: payload.page,
      page_size: payload.page_size
    }
  })
  return data
}

export async function approveMarketQuote(quoteCode: string, comment?: string) {
  const { data } = await api.post<MarketQuoteSummary>(
    `/market-quotes/${encodeURIComponent(quoteCode)}/approve`,
    { comment },
    { headers: { 'x-user': 'reviewer', 'x-user-role': 'reviewer' } }
  )
  return data
}

export async function rejectMarketQuote(quoteCode: string, comment?: string) {
  const { data } = await api.post<MarketQuoteSummary>(
    `/market-quotes/${encodeURIComponent(quoteCode)}/reject`,
    { comment },
    { headers: { 'x-user': 'reviewer', 'x-user-role': 'reviewer' } }
  )
  return data
}

export async function estimateMarketQuoteExcel(form: FormData) {
  const { data } = await api.post<ExcelMarketQuoteResponse>('/market-quotes/excel', form, {
    headers: { 'x-user': 'estimator', 'x-user-role': 'estimator' }
  })
  return data
}

export async function submitMarketQuoteExcelTask(form: FormData) {
  const { data } = await api.post<PricingTaskAccepted>('/market-quotes/excel/tasks', form, {
    headers: { 'x-user': 'estimator', 'x-user-role': 'estimator' }
  })
  return data
}

export async function fetchMarketQuoteExcelTask(taskCode: string) {
  const { data } = await api.get<PricingTaskStatus>(`/market-quotes/excel/tasks/${taskCode}`, {
    headers: { 'x-user': 'estimator', 'x-user-role': 'estimator' }
  })
  return data
}

export async function cancelMarketQuoteExcelTask(taskCode: string) {
  const { data } = await api.post<PricingTaskStatus>(
    `/market-quotes/excel/tasks/${taskCode}/cancel`,
    undefined,
    { headers: { 'x-user': 'estimator', 'x-user-role': 'estimator' } }
  )
  return data
}

export async function fetchPlatformConfigs() {
  const { data } = await api.get<PlatformConfigSummary[]>('/platform-configs')
  return data
}

export async function savePlatformConfig(provider: string, payload: {
  provider: string
  display_name: string
  base_url: string
  model: string
  api_key?: string
  endpoint_type: string
  enable_web_search: boolean
  search_tool_type?: string | null
  timeout_seconds: number
  active: boolean
  remark?: string
}) {
  const { data } = await api.put<PlatformConfigSummary>(
    `/platform-configs/${encodeURIComponent(provider)}`,
    payload,
    { headers: { 'x-user': 'admin', 'x-user-role': 'admin' } }
  )
  return data
}

export async function fetchModelCallLogPage(payload: {
  status?: string
  page: number
  page_size: number
}) {
  const { data } = await api.get<ModelCallLogPage>('/model-call-logs/page', {
    params: payload
  })
  return data
}

export async function fetchRules(status?: string) {
  const { data } = await api.get<PriceRuleSummary[]>('/rules', {
    params: status ? { status } : undefined
  })
  return data
}

export async function fetchRulePage(payload: {
  status?: string
  keyword?: string
  version?: string
  region_code?: string
  specialty?: string
  cost_category?: string
  page: number
  page_size: number
}) {
  const { data } = await api.get<PriceRulePage>('/rules/page', {
    params: payload
  })
  return data
}

export async function fetchRuleVersions(payload?: {
  tenant_code?: string
  status?: string
}) {
  try {
    const { data } = await api.get<PriceRuleVersionSummary[]>('/rules/versions', {
      params: payload
    })
    return data
  } catch (error) {
    const { data: rules } = await api.get<PriceRuleSummary[]>('/rules', {
      params: {
        tenant_code: payload?.tenant_code,
        status: payload?.status
      }
    })
    const grouped = new Map<string, PriceRuleVersionSummary>()
    for (const rule of rules) {
      const key = `${rule.version}:${rule.status}`
      const current = grouped.get(key)
      if (current) {
        current.rule_count += 1
      } else {
        grouped.set(key, {
          version: rule.version,
          status: rule.status,
          rule_count: 1
        })
      }
    }
    return Array.from(grouped.values()).sort((left, right) => right.version.localeCompare(left.version))
  }
}

export async function fetchItemMappingPage(payload: {
  status?: string
  keyword?: string
  page: number
  page_size: number
}) {
  const { data } = await api.get<ItemMappingPage>('/item-mappings/page', { params: payload })
  return data
}

export async function fetchItemMappingSetting() {
  const { data } = await api.get<ItemMappingSettingSummary>('/item-mappings/setting')
  return data
}

export async function saveItemMappingSetting(confidenceThreshold: string) {
  const { data } = await api.put<ItemMappingSettingSummary>('/item-mappings/setting', {
    confidence_threshold: confidenceThreshold
  })
  return data
}

export async function saveItemMapping(mappingCode: string | null, payload: ItemMappingPayload) {
  const method = mappingCode ? api.put : api.post
  const url = mappingCode ? `/item-mappings/${encodeURIComponent(mappingCode)}` : '/item-mappings'
  const { data } = await method<ItemMappingSummary>(url, payload)
  return data
}

export async function deleteItemMapping(mappingCode: string) {
  await api.delete(`/item-mappings/${encodeURIComponent(mappingCode)}`)
}

export async function submitItemMapping(mappingCode: string) {
  const { data } = await api.post<ItemMappingSummary>(`/item-mappings/${encodeURIComponent(mappingCode)}/submit`)
  return data
}

export async function approveItemMapping(mappingCode: string, comment?: string) {
  const { data } = await api.post<ItemMappingSummary>(`/item-mappings/${encodeURIComponent(mappingCode)}/approve`, { comment })
  return data
}

export async function rejectItemMapping(mappingCode: string, comment?: string) {
  const { data } = await api.post<ItemMappingSummary>(`/item-mappings/${encodeURIComponent(mappingCode)}/reject`, { comment })
  return data
}

export async function fetchItemMappingReviewPage(payload: {
  status?: string
  persisted?: boolean
  keyword?: string
  page: number
  page_size: number
}) {
  const { data } = await api.get<ItemMappingReviewPage>('/item-mappings/reviews/page', { params: payload })
  return data
}

export async function resolveItemMappingReview(reviewCode: string, payload: {
  standard_item_name: string
  comment?: string
  create_mapping: boolean
}) {
  const { data } = await api.post<ItemMappingReviewSummary>(
    `/item-mappings/reviews/${encodeURIComponent(reviewCode)}/resolve`,
    payload
  )
  return data
}

export interface PriceRulePayload {
  rule_id: string
  version: string
  status: string
  region_code?: string | null
  specialty?: string | null
  cost_category?: string | null
  item_name_contains: string
  unit?: string | null
  unit_price: string
  source: string
  feature_conditions: Record<string, string>
  match_priority: number
  active: boolean
}

export async function createRule(payload: PriceRulePayload) {
  const { data } = await api.post<PriceRuleSummary>('/rules', payload, {
    headers: { 'x-user': 'admin', 'x-user-role': 'admin' }
  })
  return data
}

export async function submitRule(ruleId: string, version: string) {
  const { data } = await api.post<PriceRuleSummary>(
    `/rules/${encodeURIComponent(ruleId)}/${encodeURIComponent(version)}/submit`,
    undefined,
    { headers: { 'x-user': 'estimator', 'x-user-role': 'estimator' } }
  )
  return data
}

export async function submitRulesBulk(payload: {
  items?: PriceRuleIdentity[]
  all_matching?: boolean
  status?: string
  version?: string
  region_code?: string
  specialty?: string
  cost_category?: string
  keyword?: string
}) {
  const { data } = await api.post<PriceRuleBulkActionResponse>('/rules/bulk-submit', payload, {
    headers: { 'x-user': 'estimator', 'x-user-role': 'estimator' }
  })
  return data
}

export async function updateRule(ruleId: string, version: string, payload: PriceRulePayload) {
  const { data } = await api.put<PriceRuleSummary>(
    `/rules/${encodeURIComponent(ruleId)}/${encodeURIComponent(version)}`,
    payload,
    { headers: { 'x-user': 'admin', 'x-user-role': 'admin' } }
  )
  return data
}

export async function deleteRule(ruleId: string, version: string) {
  await api.delete(`/rules/${encodeURIComponent(ruleId)}/${encodeURIComponent(version)}`, {
    headers: { 'x-user': 'admin', 'x-user-role': 'admin' }
  })
}

export async function deleteRulesBulk(payload: {
  items?: PriceRuleIdentity[]
  all_matching?: boolean
  status?: string
  version?: string
  region_code?: string
  specialty?: string
  cost_category?: string
  keyword?: string
}) {
  const { data } = await api.post<PriceRuleBulkActionResponse>('/rules/bulk-delete', payload, {
    headers: { 'x-user': 'admin', 'x-user-role': 'admin' }
  })
  return data
}

export async function importRulesExcel(form: FormData) {
  const { data } = await api.post<PriceRuleImportResponse>('/rules/import-excel', form, {
    headers: { 'x-user': 'admin', 'x-user-role': 'admin' }
  })
  return data
}

export async function approveRule(ruleId: string, version: string, comment?: string) {
  const { data } = await api.post<PriceRuleSummary>(
    `/rules/${encodeURIComponent(ruleId)}/${encodeURIComponent(version)}/approve`,
    { comment },
    { headers: { 'x-user': 'reviewer', 'x-user-role': 'reviewer' } }
  )
  return data
}

export async function approveRulesBulk(payload: {
  items?: PriceRuleIdentity[]
  all_matching?: boolean
  status?: string
  version?: string
  region_code?: string
  specialty?: string
  cost_category?: string
  keyword?: string
  comment?: string
}) {
  const { data } = await api.post<PriceRuleBulkActionResponse>('/rules/bulk-approve', payload, {
    headers: { 'x-user': 'reviewer', 'x-user-role': 'reviewer' }
  })
  return data
}

export async function rejectRule(ruleId: string, version: string, comment?: string) {
  const { data } = await api.post<PriceRuleSummary>(
    `/rules/${encodeURIComponent(ruleId)}/${encodeURIComponent(version)}/reject`,
    { comment },
    { headers: { 'x-user': 'reviewer', 'x-user-role': 'reviewer' } }
  )
  return data
}

export async function rejectRulesBulk(payload: {
  items?: PriceRuleIdentity[]
  all_matching?: boolean
  status?: string
  version?: string
  region_code?: string
  specialty?: string
  cost_category?: string
  keyword?: string
  comment?: string
}) {
  const { data } = await api.post<PriceRuleBulkActionResponse>('/rules/bulk-reject', payload, {
    headers: { 'x-user': 'reviewer', 'x-user-role': 'reviewer' }
  })
  return data
}

export async function fetchRuns() {
  const { data } = await api.get<PricingRunSummary[]>('/pricing/runs')
  return data
}

export async function fetchRunDetail(runCode: string) {
  const { data } = await api.get<PricingRunDetail>(`/pricing/runs/${encodeURIComponent(runCode)}`)
  return data
}

export async function deleteRun(runCode: string) {
  await api.delete(`/pricing/runs/${encodeURIComponent(runCode)}`)
}

export async function downloadRunExcel(runCode: string) {
  const response = await api.get<Blob>(`/pricing/runs/${encodeURIComponent(runCode)}/download`, {
    responseType: 'blob'
  })
  return response
}
