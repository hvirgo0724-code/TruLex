import http from './http'
import type { ContractIssue } from '../types'

interface ContractReviewResponse {
  items: ContractIssue[]
  summary?: string
}

/**
 * 运单审查：POST /contract/review（后端路由沿用 contract 命名）
 * 后端接口为 multipart/form-data，返回 {items, summary}
 */
export async function reviewContractText(text: string): Promise<ContractIssue[]> {
  const formData = new FormData()
  formData.append('text', text)
  const { data } = await http.post<ContractReviewResponse>('/contract/review', formData)
  return data?.items ?? []
}

export async function reviewContractFile(file: File): Promise<ContractIssue[]> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post<ContractReviewResponse>('/contract/review', formData, {
    timeout: 300000,
  })
  return data?.items ?? []
}
