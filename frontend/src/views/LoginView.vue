<template>
  <section class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <div class="brand-mark">BQ</div>
        <div>
          <h1>清单计价平台</h1>
          <span>BOQ Pricing</span>
        </div>
      </div>
      <label>
        企业编码
        <input v-model="form.tenant_code" autocomplete="organization" />
      </label>
      <label>
        用户名
        <input v-model="form.username" autocomplete="username" @keyup.enter="submit" />
      </label>
      <label>
        密码
        <input v-model="form.password" type="password" autocomplete="current-password" @keyup.enter="submit" />
      </label>
      <button class="primary login-button" :disabled="loading" @click="submit">
        <LogIn :size="17" />{{ loading ? '登录中' : '登录' }}
      </button>
      <p v-if="error" class="error">{{ error }}</p>
      <p class="muted">初始管理员账号：admin / admin123，首次使用后请尽快修改。</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { LogIn } from '@lucide/vue'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../api/client'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const form = reactive({
  tenant_code: 'default',
  username: 'admin',
  password: ''
})

async function submit() {
  error.value = ''
  if (!form.username || !form.password) {
    error.value = '用户名和密码不能为空'
    return
  }
  loading.value = true
  try {
    await login(form)
    await router.replace('/pricing')
  } catch (exc) {
    error.value = exc instanceof Error ? exc.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>
