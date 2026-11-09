export type Role = 'user' | 'assistant'

export type RiskLevel = 'high' | 'medium' | 'low'

export interface User {
  id?: number | string
  username: string
  full_name?: string
  role?: string
  [key: string]: unknown
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  full_name?: string
}

export interface Citation {
  title: string
  article_no?: string
  snippet?: string
}

export interface Message {
  id: string
  role: Role
  content: string
  citations?: Citation[]
  created_at?: string
  streaming?: boolean
}

export interface Conversation {
  id: string
  title: string
  created_at?: string
  updated_at?: string
}

export interface ContractIssue {
  clause: string
  risk_level: RiskLevel
  suggestion: string
  highlight: string
}

export interface SearchHit {
  text: string
  source: string
  score: number
  title?: string
}

export interface AuditItem {
  id?: number | string
  username?: string
  user?: string
  action?: string
  resource?: string
  detail?: string
  ip?: string
  created_at?: string
  [key: string]: unknown
}

export interface AuditResponse {
  items: AuditItem[]
  total: number
}

export interface Pagination {
  page: number
  size: number
  total: number
}