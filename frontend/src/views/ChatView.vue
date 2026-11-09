<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { Plus, ChatLineRound } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import ChatMessage from '../components/ChatMessage.vue'
import ChatInput from '../components/ChatInput.vue'

const chat = useChatStore()
const scrollRef = ref<HTMLElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  if (scrollRef.value) {
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
}

// 每次内容或消息数量变化时滚动到底部（覆盖流式增量）
watch(
  () => chat.messages.map((m) => m.content).join(''),
  () => void scrollToBottom(),
)
watch(
  () => chat.messages.length,
  () => void scrollToBottom(),
)

function handleSend(text: string) {
  void chat.sendMessage(text)
}

function handleStop() {
  chat.stopStreaming()
}

function newConversation() {
  chat.startNewConversation()
}

function selectConversation(id: string) {
  if (chat.streaming) chat.stopStreaming()
  chat.selectConversation(id)
  void chat.loadHistory(id).then(() => void scrollToBottom())
}

function formatTitle(title: string): string {
  return title.length > 18 ? `${title.slice(0, 18)}…` : title
}
</script>

<template>
  <div class="chat-page">
    <!-- 会话列表 -->
    <aside class="conv-panel">
      <div class="conv-head">
        <span class="conv-title">会话记录</span>
        <el-button
          :icon="Plus"
          type="primary"
          size="small"
          plain
          @click="newConversation"
        >
          新会话
        </el-button>
      </div>

      <div class="conv-list">
        <div v-if="chat.conversations.length === 0" class="conv-empty">
          暂无历史会话
        </div>
        <div
          v-for="conv in chat.conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === chat.currentConversationId }"
          @click="selectConversation(conv.id)"
        >
          <el-icon class="conv-icon"><ChatLineRound /></el-icon>
          <div class="conv-meta">
            <div class="conv-name">{{ formatTitle(conv.title) }}</div>
            <div class="conv-time">{{
              conv.updated_at ? new Date(conv.updated_at).toLocaleString('zh-CN', { hour12: false }) : ''
            }}</div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 对话区 -->
    <section class="dialog-panel">
      <div ref="scrollRef" class="message-scroll">
        <div v-if="chat.messages.length === 0" class="welcome">
          <div class="welcome-badge">运</div>
          <h2>您好，我是物流法律智能助手</h2>
          <p>我可以为您提供物流交通法律咨询、运单审查、法规/判例检索、货损责任认定等服务。</p>
          <div class="suggestions">
            <el-tag
              v-for="s in ['货物运输途中毁损，承运人要赔偿吗？', '快递丢件未保价怎么赔？', '危险货物运输需要什么资质？']"
              :key="s"
              class="sug"
              effect="plain"
              @click="handleSend(s)"
            >
              {{ s }}
            </el-tag>
          </div>
        </div>

        <ChatMessage
          v-for="msg in chat.messages"
          :key="msg.id"
          :message="msg"
        />
      </div>

      <div class="input-wrap">
        <ChatInput
          :streaming="chat.streaming"
          @send="handleSend"
          @stop="handleStop"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
}

/* ---------- 会话列表 ---------- */
.conv-panel {
  width: 268px;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--brand-border);
  background: rgba(12, 17, 34, 0.5);
}

.conv-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 16px;
  border-bottom: 1px solid var(--brand-border);
}

.conv-title {
  font-size: 14px;
  font-weight: 600;
  color: #e6ebf7;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.conv-empty {
  text-align: center;
  color: #6b7892;
  padding: 40px 0;
  font-size: 13px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  transition: all 0.15s ease;
}

.conv-item:hover {
  background: rgba(79, 125, 255, 0.08);
}

.conv-item.active {
  background: rgba(79, 125, 255, 0.14);
  border-color: rgba(79, 125, 255, 0.35);
}

.conv-icon {
  color: #6b7892;
  flex: 0 0 auto;
}

.conv-item.active .conv-icon {
  color: #22d3ee;
}

.conv-meta {
  min-width: 0;
}

.conv-name {
  color: #d6e2ff;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-time {
  color: #5a6580;
  font-size: 11px;
  margin-top: 3px;
}

/* ---------- 对话区 ---------- */
.dialog-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.message-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
}

.welcome {
  text-align: center;
  padding: 80px 20px;
}

.welcome-badge {
  width: 64px;
  height: 64px;
  margin: 0 auto 20px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  font-weight: 800;
  color: #06121f;
  background: linear-gradient(135deg, #4f7dff, #22d3ee);
  box-shadow: 0 0 30px rgba(79, 125, 255, 0.5);
}

.welcome h2 {
  color: #fff;
  margin: 0 0 8px;
}

.welcome p {
  color: #9aa6c0;
  margin: 0 0 24px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.sug {
  cursor: pointer;
  background: rgba(79, 125, 255, 0.06);
  border-color: rgba(148, 172, 255, 0.25);
  color: #b8c3dc;
}

.sug:hover {
  background: rgba(79, 125, 255, 0.14);
  color: #fff;
}

.input-wrap {
  padding: 12px 28px 20px;
}
</style>