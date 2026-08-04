import { ref } from 'vue'
import type { LoginResponse } from './api/client'

const STORAGE_KEY = 'boq_current_user'

export const currentUserState = ref<LoginResponse | null>(readStoredUser())

export function setCurrentUser(user: LoginResponse | null) {
  currentUserState.value = user
  if (user) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}

export function readStoredUser(): LoginResponse | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as LoginResponse
  } catch {
    return null
  }
}
