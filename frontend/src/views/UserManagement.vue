<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h2>用户管理</h2>
        <p>统一维护平台账号、角色、状态和密码策略，删除采用停用方式保留审计链路。</p>
      </div>
      <div class="header-actions">
        <button class="secondary" @click="loadUsers">刷新</button>
        <button class="primary" @click="startCreate">新增用户</button>
      </div>
    </div>

    <section class="metric-grid">
      <article class="metric-card"><span>用户总数</span><strong>{{ page.total }}</strong></article>
      <article class="metric-card"><span>当前页启用</span><strong>{{ activeCount }}</strong></article>
      <article class="metric-card"><span>管理员</span><strong>{{ roleCount('admin') }}</strong></article>
      <article class="metric-card"><span>只读用户</span><strong>{{ roleCount('viewer') }}</strong></article>
    </section>

    <section class="panel">
      <div class="user-toolbar">
        <input v-model="filters.keyword" class="compact-search" placeholder="搜索用户名或姓名" @input="reloadFirstPage" />
        <select v-model="filters.role" class="compact-select" @change="reloadFirstPage">
          <option value="">全部角色</option>
          <option v-for="role in roleOptions" :key="role.role" :value="role.role">{{ role.label }}</option>
        </select>
        <select v-model="filters.active" class="compact-select" @change="reloadFirstPage">
          <option value="">全部状态</option>
          <option value="active">启用</option>
          <option value="inactive">停用</option>
        </select>
        <select v-model.number="filters.pageSize" class="compact-select" @change="reloadFirstPage">
          <option :value="10">10 条/页</option>
          <option :value="20">20 条/页</option>
          <option :value="50">50 条/页</option>
        </select>
      </div>

      <div class="table-wrap">
        <table class="user-table">
          <thead>
            <tr>
              <th>账号</th>
              <th>姓名</th>
              <th>角色</th>
              <th>状态</th>
              <th>最近登录</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in page.items" :key="item.username">
              <td><strong>{{ item.username }}</strong></td>
              <td>{{ item.display_name || '-' }}</td>
              <td><span class="status-badge" :data-status="item.role">{{ roleLabel(item.role) }}</span></td>
              <td>
                <span class="status-badge" :data-status="item.active && item.role_active ? 'active' : 'inactive'">
                  {{ item.active && item.role_active ? '启用' : '停用' }}
                </span>
              </td>
              <td>{{ item.last_login_at || '-' }}</td>
              <td>{{ item.updated_at || '-' }}</td>
              <td>
                <div class="table-actions">
                  <button class="small-action" @click="startEdit(item)">编辑</button>
                  <button class="small-action" @click="startPasswordReset(item)">重置密码</button>
                  <button class="small-action" @click="toggleUserActive(item)">
                    {{ item.active && item.role_active ? '停用' : '启用' }}
                  </button>
                  <button class="small-action danger" :disabled="item.username === currentUsername" @click="removeUser(item)">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="!page.items.length">
              <td colspan="7" class="muted-cell">暂无用户数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pagination-bar">
        <span>共 {{ page.total }} 条，第 {{ filters.page }} / {{ pageCount }} 页</span>
        <div class="header-actions">
          <button class="secondary" :disabled="filters.page <= 1" @click="changePage(filters.page - 1)">上一页</button>
          <button class="secondary" :disabled="filters.page >= pageCount" @click="changePage(filters.page + 1)">下一页</button>
        </div>
      </div>
    </section>

    <section v-if="editing" class="panel user-edit-panel">
      <div class="section-head">
        <div>
          <h3>{{ formMode === 'create' ? '新增用户' : '编辑用户' }}</h3>
          <p class="field-hint">用户名创建后不建议修改；角色会影响菜单权限和接口操作权限。</p>
        </div>
        <button class="secondary" @click="editing = false">关闭</button>
      </div>
      <div class="form-grid">
        <label>用户名<input v-model="form.username" :readonly="formMode === 'edit'" /></label>
        <label>姓名<input v-model="form.displayName" /></label>
        <label>角色
          <select v-model="form.role">
            <option v-for="role in roleOptions" :key="role.role" :value="role.role">{{ role.label }}</option>
          </select>
        </label>
        <label class="switch">
          <input v-model="form.active" type="checkbox" />
          启用账号
        </label>
        <label v-if="formMode === 'create'">初始密码<input v-model="form.password" type="password" /></label>
      </div>
      <div class="form-actions">
        <span>{{ formMode === 'create' ? '创建后用户可使用初始密码登录。' : '保存后角色和状态立即生效。' }}</span>
        <button class="primary" :disabled="saving" @click="saveUser">{{ saving ? '保存中' : '保存用户' }}</button>
      </div>
    </section>

    <section v-if="passwordTarget" class="panel user-edit-panel">
      <div class="section-head">
        <div>
          <h3>重置密码</h3>
          <p class="field-hint">为 {{ passwordTarget.username }} 设置新密码，保存后旧密码立即失效。</p>
        </div>
        <button class="secondary" @click="passwordTarget = null">关闭</button>
      </div>
      <div class="form-grid">
        <label>新密码<input v-model="passwordValue" type="password" /></label>
      </div>
      <div class="form-actions">
        <span>建议至少 8 位，并包含数字和字母。</span>
        <button class="primary" :disabled="saving" @click="savePassword">确认重置</button>
      </div>
    </section>

    <p v-if="message" class="success">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  createManagedUser,
  deleteManagedUser,
  fetchUserPage,
  resetManagedUserPassword,
  updateManagedUser,
  type ManagedUser,
  type ManagedUserPage
} from '../api/client'
import { currentUserState } from '../authState'
import { ROLE_OPTIONS } from '../menuPermissions'

const roleOptions = ROLE_OPTIONS
const page = reactive<ManagedUserPage>({ items: [], total: 0, page: 1, page_size: 20 })
const filters = reactive({ keyword: '', role: '', active: '', page: 1, pageSize: 20 })
const editing = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const saving = ref(false)
const message = ref('')
const error = ref('')
const passwordTarget = ref<ManagedUser | null>(null)
const passwordValue = ref('')
const currentUsername = computed(() => currentUserState.value?.username || '')
const form = reactive({
  username: '',
  displayName: '',
  role: 'estimator',
  active: true,
  password: ''
})
const pageCount = computed(() => Math.max(1, Math.ceil(page.total / filters.pageSize)))
const activeCount = computed(() => page.items.filter((item) => item.active && item.role_active).length)

onMounted(loadUsers)

async function loadUsers() {
  error.value = ''
  try {
    const data = await fetchUserPage({
      keyword: filters.keyword,
      role: filters.role,
      active: filters.active,
      page: filters.page,
      page_size: filters.pageSize
    })
    Object.assign(page, data)
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '用户列表加载失败'
  }
}

function reloadFirstPage() {
  filters.page = 1
  void loadUsers()
}

function changePage(nextPage: number) {
  filters.page = nextPage
  void loadUsers()
}

function roleLabel(role: string) {
  return roleOptions.find((item) => item.role === role)?.label || role
}

function roleCount(role: string) {
  return page.items.filter((item) => item.role === role).length
}

function startCreate() {
  formMode.value = 'create'
  Object.assign(form, { username: '', displayName: '', role: 'estimator', active: true, password: '' })
  editing.value = true
}

function startEdit(item: ManagedUser) {
  formMode.value = 'edit'
  Object.assign(form, {
    username: item.username,
    displayName: item.display_name || '',
    role: item.role,
    active: item.active && item.role_active,
    password: ''
  })
  editing.value = true
}

async function saveUser() {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    if (formMode.value === 'create') {
      await createManagedUser({
        username: form.username,
        display_name: form.displayName || null,
        password: form.password,
        role: form.role,
        active: form.active
      })
      message.value = `用户 ${form.username} 已创建`
    } else {
      await updateManagedUser(form.username, {
        display_name: form.displayName || null,
        role: form.role,
        active: form.active
      })
      message.value = `用户 ${form.username} 已更新`
    }
    editing.value = false
    await loadUsers()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '用户保存失败'
  } finally {
    saving.value = false
  }
}

function startPasswordReset(item: ManagedUser) {
  passwordTarget.value = item
  passwordValue.value = ''
}

async function savePassword() {
  if (!passwordTarget.value) return
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    await resetManagedUserPassword(passwordTarget.value.username, passwordValue.value)
    message.value = `用户 ${passwordTarget.value.username} 密码已重置`
    passwordTarget.value = null
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '密码重置失败'
  } finally {
    saving.value = false
  }
}

async function toggleUserActive(item: ManagedUser) {
  error.value = ''
  message.value = ''
  try {
    const nextActive = !(item.active && item.role_active)
    await updateManagedUser(item.username, {
      display_name: item.display_name,
      role: item.role,
      active: nextActive
    })
    message.value = `用户 ${item.username} 已${nextActive ? '启用' : '停用'}`
    await loadUsers()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '状态更新失败'
  }
}

async function removeUser(item: ManagedUser) {
  if (!window.confirm(`确认删除用户 ${item.username}？系统将停用账号并保留审计记录。`)) return
  error.value = ''
  message.value = ''
  try {
    await deleteManagedUser(item.username)
    message.value = `用户 ${item.username} 已删除`
    await loadUsers()
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : '用户删除失败'
  }
}
</script>
