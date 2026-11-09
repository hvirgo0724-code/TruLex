import axios, { type AxiosError } from 'axios'

export const ACCESS_TOKEN_KEY = 'access_token'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：注入 JWT；FormData 时不强制 JSON Content-Type
http.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // FormData 交由 axios 自动设置 multipart 边界，避免被默认 JSON header 干扰
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  return config
})

// 响应拦截器：统一错误处理 + 401 跳登录
http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string; error?: string }>) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(ACCESS_TOKEN_KEY)
      localStorage.removeItem('user')
      if (window.location.pathname !== '/login') {
        const redirect = encodeURIComponent(
          window.location.pathname + window.location.search,
        )
        window.location.href = `/login?redirect=${redirect}`
      }
    }
    const detail =
      error.response?.data?.detail ?? error.response?.data?.error ?? error.message
    return Promise.reject(new Error(typeof detail === 'string' ? detail : '请求失败'))
  },
)

export default http