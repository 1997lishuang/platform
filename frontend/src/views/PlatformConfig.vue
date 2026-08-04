<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h2>平台配置</h2>
        <p>维护市场询价模型渠道和本地大模型连接参数，API Key 保存后不回显明文。</p>
      </div>
      <button class="secondary" @click="loadConfigs">
        <RefreshCw :size="17" />
        刷新
      </button>
    </div>

    <section class="platform-grid">
      <div v-for="item in configs" :key="item.provider" class="panel platform-panel">
        <div class="platform-head">
          <div>
            <h3>{{ item.display_name }}</h3>
            <span>{{ providerLabel(item.provider) }}</span>
          </div>
          <label class="switch">
            <input v-model="item.active" type="checkbox" />
            启用
          </label>
        </div>

        <div class="form-grid">
          <label>平台显示名称<input v-model="item.display_name" /></label>
          <label>模型名称<input v-model="item.model" /></label>
          <label>Base URL<input v-model="item.base_url" /></label>
          <label>
            接口类型
            <select v-model="item.endpoint_type">
              <option value="chat_completions">Chat Completions</option>
              <option value="responses">Responses API</option>
            </select>
          </label>
          <label>超时时间(秒)<input v-model.number="item.timeout_seconds" type="number" min="10" /></label>
          <label class="switch">
            <input v-model="item.enable_web_search" type="checkbox" />
            联网搜索增强
          </label>
          <label>
            搜索工具类型
            <select v-model="item.search_tool_type" :disabled="!item.enable_web_search">
              <option value="web_search">web_search</option>
              <option value="web_search_preview">web_search_preview</option>
            </select>
          </label>
          <label>
            API Key
            <input v-model="item.api_key" type="password" :placeholder="item.api_key_configured ? '已配置，留空不修改' : '请输入 API Key'" />
          </label>
          <label>备注<input v-model="item.remark" /></label>
        </div>

        <div class="form-actions">
          <span>{{ item.api_key_configured ? '密钥已配置' : '密钥未配置' }}</span>
          <button class="primary" :disabled="savingProvider === item.provider" @click="saveConfig(item)">
            <Save :size="17" />
            {{ savingProvider === item.provider ? '保存中' : '保存配置' }}
          </button>
        </div>
      </div>
    </section>

    <section class="panel permission-panel">
      <div class="section-head">
        <div>
          <h3>菜单权限管理</h3>
          <p class="field-hint">按角色控制左侧菜单可见性和路由访问范围；管理员默认保留平台配置权限，避免权限配置失控。</p>
        </div>
        <div class="header-actions">
          <button class="secondary" @click="resetPermissionMatrix">恢复默认</button>
          <button class="primary" @click="savePermissionMatrix">
            <Save :size="17" />
            保存权限
          </button>
        </div>
      </div>
      <div class="permission-role-cards">
        <article v-for="role in roleOptions" :key="role.role">
          <strong>{{ role.label }}</strong>
          <span>{{ role.description }}</span>
        </article>
      </div>
      <div class="permission-table-wrap">
        <table class="permission-table">
          <thead>
            <tr>
              <th>菜单</th>
              <th>说明</th>
              <th v-for="role in roleOptions" :key="role.role">{{ role.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="menu in menuItems" :key="menu.id">
              <td><strong>{{ menu.label }}</strong></td>
              <td>{{ menu.description }}</td>
              <td v-for="role in roleOptions" :key="role.role">
                <input
                  v-model="permissionMatrix[role.role][menu.id]"
                  type="checkbox"
                  :disabled="role.role === 'admin' && menu.id === 'platform-configs'"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p v-if="message" class="success">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { RefreshCw, Save } from '@lucide/vue'
import { onMounted, reactive, ref } from 'vue'
import { fetchPlatformConfigs, savePlatformConfig, type PlatformConfigSummary } from '../api/client'
import {
  MENU_PERMISSION_ITEMS,
  ROLE_OPTIONS,
  cloneDefaultMenuPermissions,
  readMenuPermissions,
  saveMenuPermissions,
  type MenuPermissionConfig
} from '../menuPermissions'

type EditablePlatformConfig = PlatformConfigSummary & { api_key: string }

const defaults: EditablePlatformConfig[] = [
  {
    provider: 'doubao',
    display_name: '豆包/火山方舟',
    base_url: 'https://ark.cn-beijing.volces.com/api/v3',
    model: 'doubao-seed-1-6',
    api_key: '',
    api_key_configured: false,
    endpoint_type: 'chat_completions',
    enable_web_search: true,
    search_tool_type: 'web_search',
    timeout_seconds: 180,
    active: true,
    remark: '用于公开市场参考价检索',
    updated_by: null,
    updated_at: ''
  },
  {
    provider: 'closeai',
    display_name: 'CloseAI',
    base_url: 'https://www.closeai-asia.com/v1',
    model: 'gpt-4o-mini',
    api_key: '',
    api_key_configured: false,
    endpoint_type: 'chat_completions',
    enable_web_search: false,
    search_tool_type: 'web_search_preview',
    timeout_seconds: 60,
    active: true,
    remark: 'OpenAI 兼容接口代理渠道',
    updated_by: null,
    updated_at: ''
  },
  {
    provider: 'local',
    display_name: '本地大模型',
    base_url: 'http://127.0.0.1:8001/v1',
    model: 'local-model',
    api_key: '',
    api_key_configured: false,
    endpoint_type: 'chat_completions',
    enable_web_search: false,
    search_tool_type: 'web_search_preview',
    timeout_seconds: 120,
    active: true,
    remark: '本地部署的 OpenAI 兼容服务',
    updated_by: null,
    updated_at: ''
  }
]

const configs = reactive<EditablePlatformConfig[]>([])
const menuItems = MENU_PERMISSION_ITEMS
const roleOptions = ROLE_OPTIONS
const permissionMatrix = reactive<MenuPermissionConfig>(readMenuPermissions())
const savingProvider = ref('')
const message = ref('')
const error = ref('')

onMounted(loadConfigs)

async function loadConfigs() {
  error.value = ''
  message.value = ''
  try {
    const saved = await fetchPlatformConfigs()
    const savedByProvider = new Map(saved.map((item) => [item.provider, item]))
    configs.splice(
      0,
      configs.length,
      ...defaults.map((item) => ({
        ...item,
        ...(savedByProvider.get(item.provider) || {}),
        api_key: ''
      }))
    )
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '平台配置加载失败'
    configs.splice(0, configs.length, ...defaults.map((item) => ({ ...item })))
  }
}

async function saveConfig(item: EditablePlatformConfig) {
  savingProvider.value = item.provider
  error.value = ''
  message.value = ''
  try {
    const saved = await savePlatformConfig(item.provider, {
      provider: item.provider,
      display_name: item.display_name,
      base_url: item.base_url,
      model: item.model,
      api_key: item.api_key || undefined,
      endpoint_type: item.endpoint_type,
      enable_web_search: item.enable_web_search,
      search_tool_type: item.enable_web_search ? item.search_tool_type : undefined,
      timeout_seconds: item.timeout_seconds,
      active: item.active,
      remark: item.remark || undefined
    })
    Object.assign(item, saved, { api_key: '' })
    message.value = `${item.display_name} 配置已保存`
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '平台配置保存失败'
  } finally {
    savingProvider.value = ''
  }
}

function providerLabel(provider: string) {
  if (provider === 'doubao') return 'provider: doubao'
  if (provider === 'closeai') return 'provider: closeai'
  return 'provider: local'
}

function replacePermissionMatrix(next: MenuPermissionConfig) {
  roleOptions.forEach(({ role }) => {
    Object.assign(permissionMatrix[role], next[role])
  })
}

function savePermissionMatrix() {
  permissionMatrix.admin['platform-configs'] = true
  saveMenuPermissions(permissionMatrix)
  message.value = '菜单权限已保存，左侧菜单和页面访问范围已按角色生效。'
  error.value = ''
}

function resetPermissionMatrix() {
  replacePermissionMatrix(cloneDefaultMenuPermissions())
  savePermissionMatrix()
}
</script>
