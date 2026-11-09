<script setup lang="ts">
import { ref } from 'vue'
import { Promotion, VideoPause } from '@element-plus/icons-vue'

const props = defineProps<{
  streaming: boolean
  disabled?: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'send', text: string): void
  (e: 'stop'): void
}>()

const text = ref('')

function submit() {
  const value = text.value.trim()
  if (!value || props.streaming) return
  emit('send', value)
  text.value = ''
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="chat-input">
    <div v-if="streaming" class="generating">
      <span class="pulse" />
      正在生成…
    </div>

    <el-input
      v-model="text"
      type="textarea"
      :rows="3"
      resize="none"
      :disabled="disabled"
      :placeholder="placeholder || '请输入您的法律问题…'"
      class="input"
      @keydown="onKeydown"
    />

    <div class="actions">
      <span class="hint">Enter 发送 · Shift+Enter 换行</span>
      <el-button
        v-if="streaming"
        type="danger"
        plain
        :icon="VideoPause"
        @click="emit('stop')"
      >
        停止
      </el-button>
      <el-button
        v-else
        type="primary"
        :icon="Promotion"
        :disabled="!text.trim() || disabled"
        @click="submit"
      >
        发送
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.chat-input {
  background: #10162a;
  border: 1px solid rgba(148, 172, 255, 0.14);
  border-radius: 14px;
  padding: 14px;
}

.generating {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #22d3ee;
  margin-bottom: 10px;
}

.pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22d3ee;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.5);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(34, 211, 238, 0);
  }
}

.input :deep(.el-textarea__inner) {
  background: #0b1020;
  border: 1px solid rgba(148, 172, 255, 0.12);
  color: #e6ebf7;
}

.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}

.hint {
  font-size: 12px;
  color: #6b7892;
}
</style>