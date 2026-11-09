import http from './http'
import { ACCESS_TOKEN_KEY } from './http'
import type { Citation, Message } from '../types'

export interface ChatStreamCallbacks {
  /** 增量 token */
  onDelta: (text: string) => void
  /** 末尾事件携带的引用脚注 */
  onCitations: (citations: Citation[]) => void
  /** 后端返回的会话 ID */
  onConversation: (conversationId: string) => void
  /** 流结束 */
  onDone: () => void
}

export interface ChatStreamPayload {
  conversation_id?: string
  message: string
}

/**
 * 流式对话：POST /chat（SSE text/event-stream）
 * 使用 fetch + ReadableStream 分帧解析，支持 AbortSignal 停止。
 */
export async function streamChat(
  payload: ChatStreamPayload,
  callbacks: ChatStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/v1/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${localStorage.getItem(ACCESS_TOKEN_KEY) ?? ''}`,
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    let detail = `请求失败 (${response.status})`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* 忽略非 JSON 错误体 */
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('当前浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  const dispatchFrame = (frame: string) => {
    let event = 'message'
    const lines: string[] = []
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      if (line.startsWith('data:')) lines.push(line.slice(5).trimStart())
    }
    const data = lines.join('\n')
    if (!data) return
    if (data === '[DONE]') { callbacks.onDone(); return }
    let parsed: {
      content?: string; delta?: string; items?: Citation[]; citations?: Citation[]
      conversation_id?: string | number; done?: boolean; message?: string
    }
    try { parsed = JSON.parse(data) } catch {
      callbacks.onDelta(data)
      return
    }
    if (event === 'error') throw new Error(parsed.message || '对话处理失败')
    const text = event === 'token' ? parsed.content : parsed.delta
    if (typeof text === 'string') callbacks.onDelta(text)
    const citations = event === 'citations' ? parsed.items : parsed.citations
    if (Array.isArray(citations)) callbacks.onCitations(citations)
    if (parsed.conversation_id) callbacks.onConversation(String(parsed.conversation_id))
    if (event === 'done' || parsed.done) callbacks.onDone()
  }

  try {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n')
      let sep = buffer.indexOf('\n\n')
      while (sep !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        dispatchFrame(frame)
        sep = buffer.indexOf('\n\n')
      }
    }
    if (buffer.trim()) dispatchFrame(buffer)
  } finally {
    reader.releaseLock()
  }

  callbacks.onDone()
}

/** 历史消息：GET /chat/history?conversation_id= */
export async function getChatHistory(conversationId: string): Promise<Message[]> {
  const { data } = await http.get<{ messages: Message[] }>('/chat/history', {
    params: { conversation_id: conversationId },
  })
  return data.messages
}