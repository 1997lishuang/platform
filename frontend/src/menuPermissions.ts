export type UserRole = 'admin' | 'estimator' | 'reviewer' | 'viewer'

export interface MenuPermissionItem {
  id: string
  label: string
  path: string
  description: string
}

export type MenuPermissionConfig = Record<UserRole, Record<string, boolean>>

export const MENU_PERMISSION_STORAGE_KEY = 'boq_menu_permissions'

export const ROLE_OPTIONS: Array<{ role: UserRole; label: string; description: string }> = [
  { role: 'admin', label: '管理员', description: '平台治理、模型配置、权限管理和全部业务功能。' },
  { role: 'estimator', label: '造价人员', description: '计价、询价、报价测算和规则提交。' },
  { role: 'reviewer', label: '审核人员', description: '规则审核、计价结果复核和监控查询。' },
  { role: 'viewer', label: '只读用户', description: '查询与查看，不参与配置和审批操作。' }
]

export const MENU_PERMISSION_ITEMS: MenuPermissionItem[] = [
  { id: 'pricing', label: '计价工作台', path: '/pricing', description: '上传清单并生成综合单价。' },
  { id: 'rules', label: '价格规则库', path: '/rules', description: '维护和查看综合单价规则。' },
  { id: 'item-mappings', label: '映射校准', path: '/item-mappings', description: '处理清单映射和低置信度校准。' },
  { id: 'market-quotes', label: '市场询价', path: '/market-quotes', description: '联网询价、证据复核和价格沉淀。' },
  { id: 'bid-strategy', label: '投标策略', path: '/bid-strategy', description: '原投标策略能力和开标回测。' },
  { id: 'dynamic-game', label: '报价决策', path: '/dynamic-game', description: '竞争推演、报价区间和利润优先推荐。' },
  { id: 'bid-reverse-pricing', label: '单项反推', path: '/bid-reverse-pricing', description: '按目标总价反推单项报价。' },
  { id: 'platform-configs', label: '平台配置', path: '/platform-configs', description: '模型平台、连接参数和菜单权限。' },
  { id: 'users', label: '用户管理', path: '/users', description: '维护平台账号、角色、状态和密码。' },
  { id: 'model-call-logs', label: '调用监控', path: '/model-call-logs', description: '查看接口状态、耗时和 Token 用量。' },
  { id: 'approvals', label: '规则审批', path: '/approvals', description: '审核待发布的计价规则。' },
  { id: 'runs', label: '计价批次', path: '/runs', description: '查看历史计价任务和命中情况。' }
]

export const DEFAULT_MENU_PERMISSIONS: MenuPermissionConfig = {
  admin: Object.fromEntries(MENU_PERMISSION_ITEMS.map((item) => [item.id, true])) as Record<string, boolean>,
  estimator: {
    pricing: true,
    rules: true,
    'item-mappings': true,
    'market-quotes': true,
    'bid-strategy': true,
    'dynamic-game': true,
    'bid-reverse-pricing': true,
    'platform-configs': false,
    users: false,
    'model-call-logs': true,
    approvals: false,
    runs: true
  },
  reviewer: {
    pricing: true,
    rules: true,
    'item-mappings': true,
    'market-quotes': true,
    'bid-strategy': true,
    'dynamic-game': true,
    'bid-reverse-pricing': true,
    'platform-configs': false,
    users: false,
    'model-call-logs': true,
    approvals: true,
    runs: true
  },
  viewer: {
    pricing: true,
    rules: true,
    'item-mappings': false,
    'market-quotes': true,
    'bid-strategy': false,
    'dynamic-game': false,
    'bid-reverse-pricing': false,
    'platform-configs': false,
    users: false,
    'model-call-logs': true,
    approvals: false,
    runs: true
  }
}

export function cloneDefaultMenuPermissions(): MenuPermissionConfig {
  return cloneConfig(DEFAULT_MENU_PERMISSIONS)
}

export function cloneConfig(config: MenuPermissionConfig): MenuPermissionConfig {
  return JSON.parse(JSON.stringify(config)) as MenuPermissionConfig
}

export function normalizeMenuPermissions(value: unknown): MenuPermissionConfig {
  const config = cloneDefaultMenuPermissions()
  if (!value || typeof value !== 'object') return config
  const incoming = value as Partial<MenuPermissionConfig>
  ROLE_OPTIONS.forEach(({ role }) => {
    MENU_PERMISSION_ITEMS.forEach((item) => {
      const explicit = incoming[role]?.[item.id]
      if (typeof explicit === 'boolean') config[role][item.id] = explicit
    })
  })
  config.admin['platform-configs'] = true
  config.admin.users = true
  return config
}

export function readMenuPermissions(): MenuPermissionConfig {
  try {
    return normalizeMenuPermissions(JSON.parse(localStorage.getItem(MENU_PERMISSION_STORAGE_KEY) || 'null'))
  } catch {
    return cloneDefaultMenuPermissions()
  }
}

export function saveMenuPermissions(config: MenuPermissionConfig) {
  const normalized = normalizeMenuPermissions(config)
  localStorage.setItem(MENU_PERMISSION_STORAGE_KEY, JSON.stringify(normalized))
  window.dispatchEvent(new Event('menu-permissions-updated'))
}

export function resetMenuPermissions() {
  saveMenuPermissions(cloneDefaultMenuPermissions())
}

export function menuIdForPath(path: string) {
  return MENU_PERMISSION_ITEMS.find((item) => path === item.path || path.startsWith(`${item.path}/`))?.id || 'pricing'
}

export function isMenuAllowed(role: string | null | undefined, path: string) {
  const userRole = normalizeRole(role)
  const menuId = menuIdForPath(path)
  if (userRole === 'admin' && menuId === 'platform-configs') return true
  return readMenuPermissions()[userRole]?.[menuId] ?? false
}

export function firstAllowedPath(role: string | null | undefined) {
  const userRole = normalizeRole(role)
  const permissions = readMenuPermissions()[userRole]
  return MENU_PERMISSION_ITEMS.find((item) => permissions?.[item.id])?.path || '/pricing'
}

export function normalizeRole(role: string | null | undefined): UserRole {
  if (role === 'admin' || role === 'estimator' || role === 'reviewer' || role === 'viewer') return role
  return 'viewer'
}
