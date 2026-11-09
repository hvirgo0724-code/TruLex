import { reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import type { Conversation, Message } from '../types'
import { getChatHistory, streamChat } from '../api/chat'

const CONVERSATIONS_KEY = 'conversations'

export function genId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function loadStoredConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(CONVERSATIONS_KEY)
    return raw ? (JSON.parse(raw) as Conversation[]) : []
  } catch {
    return []
  }
}

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>(loadStoredConversations())
  const currentConversationId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const streaming = ref(false)

  let controller: AbortController | null = null

  function persistConversations() {
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations.value))
  }

  function upsertConversation(id: string, title: string) {
    const existing = conversations.value.find((c) => c.id === id)
    if (existing) {
      existing.updated_at = new Date().toISOString()
    } else {
      conversations.value.unshift({
        id,
        title,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    }
    persistConversations()
  }

  function selectConversation(id: string | null) {
    currentConversationId.value = id
  }

  function clearMessages() {
    messages.value = []
    currentConversationId.value = null
  }

  function startNewConversation() {
    clearMessages()
  }

  /** 加载历史消息 */
  async function loadHistory(conversationId: string) {
    const history = await getChatHistory(conversationId)
    messages.value = history.map((m) => ({
      ...m,
      id: m.id || genId(),
      content: m.content ?? '',
      role: m.role,
      streaming: false,
    }))
    currentConversationId.value = conversationId
  }

  /** 发送消息并流式接收 */
  async function sendMessage(content: string) {
    if (!content.trim() || streaming.value) return

    const userMsg: Message = {
      id: genId(),
      role: 'user',
      content: content.trim(),
      created_at: new Date().toISOString(),
    }
    const assistantMsg = reactive<Message>({
      id: genId(),
      role: 'assistant',
      content: '',
      citations: [],
      streaming: true,
    })
    messages.value.push(userMsg, assistantMsg)

    controller = new AbortController()
    streaming.value = true

    // 若尚无会话，先以首条消息为标题创建一个临时会话
    let pendingConversationId = currentConversationId.value

    try {
      await streamChat(
        {
          conversation_id: pendingConversationId ?? undefined,
          message: userMsg.content,
        },
        {
          onDelta: (chunk) => {
            assistantMsg.content += chunk
          },
          onCitations: (citations) => {
            assistantMsg.citations = citations
          },
          onConversation: (conversationId) => {
            pendingConversationId = conversationId
            currentConversationId.value = conversationId
            upsertConversation(conversationId, userMsg.content.slice(0, 30))
          },
          onDone: () => {
            assistantMsg.streaming = false
          },
        },
        controller.signal,
      )
    } catch (err) {
      const aborted = err instanceof DOMException && err.name === 'AbortError'
      if (!aborted) {
        assistantMsg.content = `⚠️ 请求失败：${(err as Error).message}`
      }
      assistantMsg.streaming = false
    } finally {
      assistantMsg.streaming = false
      streaming.value = false
      controller = null
    }
  }

  /** 停止当前流式生成 */
  function stopStreaming() {
    controller?.abort()
    streaming.value = false
    controller = null
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant') {
      last.streaming = false
    }
  }

  return {
    conversations,
    currentConversationId,
    messages,
    streaming,
    selectConversation,
    clearMessages,
    startNewConversation,
    loadHistory,
    sendMessage,
    stopStreaming,
  }
})
