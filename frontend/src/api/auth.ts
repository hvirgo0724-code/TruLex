import http from './http'
import type { LoginResponse, RegisterRequest, User } from '../types'

/** 登录：POST /auth/login {username, password} */
export async function login(username: string, password: string): Promise<LoginResponse> {
  const { data } = await http.post<LoginResponse>('/auth/login', { username, password })
  return data
}

/** 注册：POST /auth/register {username, email, password, full_name?} */
export async function register(payload: RegisterRequest): Promise<LoginResponse> {
  const { data } = await http.post<LoginResponse>('/auth/register', payload)
  return data
}

/** 获取当前用户：GET /auth/me */
export async function getMe(): Promise<User> {
  const { data } = await http.get<User>('/auth/me')
  return data
}