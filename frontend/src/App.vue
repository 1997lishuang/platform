<template>
  <RouterView v-if="isLoginPage" />
  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">BQ</div>
        <div>
          <h1>清单计价平台</h1>
          <span>BOQ Pricing</span>
        </div>
      </div>
      <nav>
        <RouterLink v-for="item in visibleMenuItems" :key="item.id" :to="item.path">
          <component :is="item.icon" :size="18" />{{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="main-pane">
      <header class="topbar">
        <div>
          <strong>{{ pageTitle }}</strong>
          <span>{{ pageSubtitle }}</span>
        </div>
        <div class="user-menu">
          <div class="user-avatar">{{ userInitial }}</div>
          <div class="user-meta">
            <strong>{{ currentUser?.display_name || currentUser?.username || '-' }}</strong>
            <span>{{ roleLabel(currentUser?.role) }}</span>
          </div>
          <button class="logout-button" title="退出登录" @click="signOut">
            <LogOut :size="18" />
          </button>
        </div>
      </header>
      <div class="content-pane">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { Activity, Calculator, Database, GitBranch, History, LogOut, Search, Settings, ShieldCheck, Swords, TableProperties, TrendingUp, Users } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { logout } from './api/client'
import { currentUserState } from './authState'
import { MENU_PERMISSION_ITEMS, firstAllowedPath, isMenuAllowed, readMenuPermissions, type MenuPermissionConfig } from './menuPermissions'

const route = useRoute()
const router = useRouter()
const isLoginPage = computed(() => route.path === '/login')
const currentUser = currentUserState
const menuPermissionVersion = ref(0)
const menuPermissions = ref<MenuPermissionConfig>(readMenuPermissions())
const userInitial = computed(() => (currentUser.value?.display_name || currentUser.value?.username || 'U').slice(0, 1).toUpperCase())
const menuIcons = {
  pricing: Calculator,
  rules: Database,
  'item-mappings': GitBranch,
  'market-quotes': Search,
  'bid-strategy': TrendingUp,
  'dynamic-game': Swords,
  'bid-reverse-pricing': TableProperties,
  'platform-configs': Settings,
  users: Users,
  'model-call-logs': Activity,
  approvals: ShieldCheck,
  runs: History
}
const visibleMenuItems = computed(() => {
  void menuPermissionVersion.value
  return MENU_PERMISSION_ITEMS
    .filter((item) => isMenuAllowed(currentUser.value?.role, item.path))
    .map((item) => ({ ...item, icon: menuIcons[item.id as keyof typeof menuIcons] }))
})

onMounted(() => {
  window.addEventListener('menu-permissions-updated', refreshMenuPermissions)
  window.addEventListener('storage', refreshMenuPermissions)
})

onBeforeUnmount(() => {
  window.removeEventListener('menu-permissions-updated', refreshMenuPermissions)
  window.removeEventListener('storage', refreshMenuPermissions)
})

function refreshMenuPermissions() {
  menuPermissions.value = readMenuPermissions()
  menuPermissionVersion.value += 1
  if (!isLoginPage.value && !isMenuAllowed(currentUser.value?.role, route.path)) {
    void router.replace(firstAllowedPath(currentUser.value?.role))
  }
}

const pageTitle = computed(() => {
  if (route.path.startsWith('/rules')) return '价格规则库'
  if (route.path.startsWith('/item-mappings')) return '映射校准'
  if (route.path.startsWith('/market-quotes')) return '市场询价'
  if (route.path.startsWith('/bid-strategy')) return '投标报价策略'
  if (route.path.startsWith('/dynamic-game')) return '投标报价决策中心'
  if (route.path.startsWith('/bid-reverse-pricing')) return '单项报价反推'
  if (route.path.startsWith('/platform-configs')) return '平台配置'
  if (route.path.startsWith('/users')) return '用户管理'
  if (route.path.startsWith('/model-call-logs')) return '模型调用监控'
  if (route.path.startsWith('/approvals')) return '规则审批'
  if (route.path.startsWith('/runs')) return '计价批次'
  return '计价工作台'
})

const pageSubtitle = computed(() => {
  if (route.path.startsWith('/rules')) return '维护综合单价规则和审批流入口'
  if (route.path.startsWith('/item-mappings')) return '处理低置信度自动映射产生的人工校准任务'
  if (route.path.startsWith('/market-quotes')) return '联网询价、证据复核和价格沉淀'
  if (route.path.startsWith('/bid-strategy')) return '评标规则模拟、稳健报价区间和开标回测'
  if (route.path.startsWith('/dynamic-game')) return '竞争推演、报价区间和利润优先推荐'
  if (route.path.startsWith('/bid-reverse-pricing')) return '从目标总价反推清单单价，支持固定项和人工重平衡'
  if (route.path.startsWith('/platform-configs')) return '维护模型平台和本地模型连接'
  if (route.path.startsWith('/users')) return '维护平台账号、角色、状态和密码'
  if (route.path.startsWith('/model-call-logs')) return '查看询价接口状态、耗时和 Token 用量'
  if (route.path.startsWith('/approvals')) return '审核待发布的计价规则'
  if (route.path.startsWith('/runs')) return '查看历史计价任务和命中情况'
  return '上传清单并生成综合单价结果'
})

function roleLabel(role?: string | null) {
  if (role === 'admin') return '管理员'
  if (role === 'estimator') return '造价人员'
  if (role === 'reviewer') return '审核人员'
  if (role === 'viewer') return '只读用户'
  return '未识别角色'
}

function signOut() {
  logout()
  router.replace('/login')
}
</script>
