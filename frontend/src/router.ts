import { createRouter, createWebHistory } from 'vue-router'
import PricingWorkbench from './views/PricingWorkbench.vue'
import RuleLibrary from './views/RuleLibrary.vue'
import RuleApproval from './views/RuleApproval.vue'
import MarketQuote from './views/MarketQuote.vue'
import PlatformConfig from './views/PlatformConfig.vue'
import ModelCallMonitor from './views/ModelCallMonitor.vue'
import RunHistory from './views/RunHistory.vue'
import LoginView from './views/LoginView.vue'
import ItemMapping from './views/ItemMapping.vue'
import BidStrategy from './views/BidStrategy.vue'
import DynamicGameStrategy from './views/DynamicGameStrategy.vue'
import BidReversePricing from './views/BidReversePricing.vue'
import UserManagement from './views/UserManagement.vue'
import { firstAllowedPath, isMenuAllowed } from './menuPermissions'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/pricing' },
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/pricing', component: PricingWorkbench },
    { path: '/bid-strategy', component: BidStrategy },
    { path: '/dynamic-game', component: DynamicGameStrategy },
    { path: '/bid-reverse-pricing', component: BidReversePricing },
    { path: '/rules', component: RuleLibrary },
    { path: '/item-mappings', component: ItemMapping },
    { path: '/market-quotes', component: MarketQuote },
    { path: '/platform-configs', component: PlatformConfig },
    { path: '/users', component: UserManagement },
    { path: '/model-call-logs', component: ModelCallMonitor },
    { path: '/approvals', component: RuleApproval },
    { path: '/runs', component: RunHistory }
  ]
})

router.beforeEach((to) => {
  const token = localStorage.getItem('boq_access_token')
  if (!to.meta.public && !token) {
    return '/login'
  }
  if (to.path === '/login' && token) {
    return '/pricing'
  }
  if (!to.meta.public && token) {
    const user = readStoredUser()
    if (!isMenuAllowed(user?.role, to.path)) {
      const fallback = firstAllowedPath(user?.role)
      return fallback === to.path ? true : fallback
    }
  }
  return true
})

function readStoredUser(): { role?: string } | null {
  try {
    return JSON.parse(localStorage.getItem('boq_current_user') || 'null') as { role?: string } | null
  } catch {
    return null
  }
}

export default router
