<script setup lang="ts">
import { computed } from 'vue'
import type { Message } from '../types'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps<{ message: Message }>()

const html = computed(() => renderMarkdown(props.message.content))
</script>

<template>
  <div class="chat-message" :class="message.role">
    <div class="avatar" :class="message.role">
      {{ message.role === 'user' ? '我' : '法' }}
    </div>

    <div class="body">
      <div class="bubble">
        <div
          v-if="message.content"
          class="markdown-body content"
          v-html="html"
        />
        <div v-else-if="message.streaming" class="typing">
          <span class="dot" />
          <span class="dot" />
          <span class="dot" />
        </div>
        <span v-if="message.streaming" class="caret" />

        <!-- 引用脚注 -->
        <div v-if="message.citations && message.citations.length" class="citations">
          <div class="citations-title">📚 引用来源</div>
          <div
            v-for="(c, i) in message.citations"
            :key="i"
            class="citation"
          >
            <span class="idx">[{{ i + 1 }}]</span>
            <span class="title">{{ c.title }}</span>
            <span v-if="c.article_no" class="article">{{ c.article_no }}</span>
            <p v-if="c.snippet" class="snippet">{{ c.snippet }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.avatar {
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 700;
  user-select: none;
}

.avatar.user {
  background: linear-gradient(135deg, #4f7dff, #22d3ee);
  color: #06121f;
}

.avatar.assistant {
  background: linear-gradient(135deg, #1d2946, #2a3a66);
  border: 1px solid rgba(148, 172, 255, 0.3);
  color: #aecbff;
}

.body {
  max-width: 78%;
  display: flex;
  flex-direction: column;
}

.chat-message.user .body {
  align-items: flex-end;
}

.bubble {
  padding: 12px 16px;
  border-radius: 14px;
  background: #131a30;
  border: 1px solid rgba(148, 172, 255, 0.12);
  color: #e6ebf7;
  position: relative;
  line-height: 1.7;
}

.chat-message.user .bubble {
  background: linear-gradient(135deg, rgba(79, 125, 255, 0.22), rgba(34, 211, 238, 0.1));
  border-color: rgba(79, 125, 255, 0.35);
}

.caret {
  display: inline-block;
  width: 8px;
  height: 18px;
  margin-left: 2px;
  background: #22d3ee;
  vertical-align: text-bottom;
  animation: blink 1s steps(2, start) infinite;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}

.typing {
  display: inline-flex;
  gap: 5px;
  align-items: center;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22d3ee;
  animation: bounce 1.2s infinite;
}

.dot:nth-child(2) {
  animation-delay: 0.15s;
}
.dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

.citations {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed rgba(148, 172, 255, 0.2);
}

.citations-title {
  font-size: 12px;
  color: #9aa6c0;
  margin-bottom: 6px;
}

.citation {
  margin-bottom: 8px;
  font-size: 13px;
}

.citation .idx {
  color: #22d3ee;
  font-weight: 600;
  margin-right: 6px;
}

.citation .title {
  color: #d6e2ff;
  font-weight: 500;
}

.citation .article {
  color: #9aa6c0;
  font-size: 12px;
  margin-left: 8px;
}

.citation .snippet {
  margin: 3px 0 0 20px;
  color: #6b7892;
  font-size: 12px;
}
</style>