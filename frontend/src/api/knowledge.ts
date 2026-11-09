import http from './http'
import type { SearchHit } from '../types'

/** 知识检索：POST /knowledge/search {query, top_k}，返回 {hits: SearchHit[]} */
export async function searchKnowledge(query: string, topK = 5): Promise<SearchHit[]> {
  const { data } = await http.post<{ hits: SearchHit[] }>('/knowledge/search', {
    query,
    top_k: topK,
  })
  return data?.hits ?? []
}