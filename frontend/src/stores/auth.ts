import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { RegisterRequest, User } from '../types'
import { login as loginRequest, register as registerRequest, getMe } from '../api/auth'
import { ACCESS_TOKEN_KEY } from '../api/http'

const USER_KEY = 'user'

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(ACCESS_TOKEN_KEY))
  const user = ref<User | null>(readStoredUser())

  const isAuthenticated = computed(() => !!token.value)

  function setToken(value: string | null) {
    token.value = value
    if (value) localStorage.setItem(ACCESS_TOKEN_KEY, value)
    else localStorage.removeItem(ACCESS_TOKEN_KEY)
  }

  function setUser(value: User | null) {
    user.value = value
    if (value) localStorage.setItem(USER_KEY, JSON.stringify(value))
    else localStorage.removeItem(USER_KEY)
  }

  async function login(username: string, password: string) {
    const res = await loginRequest(username, password)
    setToken(res.access_token)
    try {
      const me = await getMe()
      setUser(me)
    } catch {
      setUser({ username })
    }
    return res
  }

  async function register(payload: RegisterRequest) {
    const res = await registerRequest(payload)
    setToken(res.access_token)
    try {
      const me = await getMe()
      setUser(me)
    } catch {
      setUser({ username: payload.username })
    }
    return res
  }

  async function fetchMe() {
    if (!token.value) return null
    try {
      const me = await getMe()
      setUser(me)
      return me
    } catch {
      return null
    }
  }

  function logout() {
    setToken(null)
    setUser(null)
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    register,
    logout,
    fetchMe,
    setToken,
    setUser,
  }
})