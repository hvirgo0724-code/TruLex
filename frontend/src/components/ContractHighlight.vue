<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ContractIssue, RiskLevel } from '../types'
import { escapeHtml } from '../utils/markdown'

const props = defineProps<{
  text: string
  issues: ContractIssue[]
  activeIndex: number | null
}>()

const emit = defineEmits<{
  (e: 'hover', index: number | null): void
}>()

const RISK_LABEL: Record<RiskLevel, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
}

const rootRef = ref<HTMLElement | null>(null)

/** 构建高亮 HTML：用 escape 后的 highlight 做精确替换，包上 <mark> */
const highlightedHtml = computed(() => {
  let html = escapeHtml(props.text)
  props.issues.forEach((issue, idx) => {
    const target = escapeHtml(issue.highlight)
    if (!target || !html.includes(target)) return
    const mark =
      `<mark class="hl hl-${issue.risk_level}" data-idx="${idx}" ` +
      `title="${RISK_LABEL[issue.risk_level]}">${target}</mark>`
    html = html.split(target).join(mark)
  })
  return html
})

// 外部（右侧列表）联动：动态给对应 mark 加 active class，避免重建 DOM 导致悬停闪烁
watch(
  () => props.activeIndex,
  (idx) => {
    if (!rootRef.value) return
    rootRef.value.querySelectorAll('mark.hl.active').forEach((el) => el.classList.remove('active'))
    if (idx !== null) {
      const el = rootRef.value.querySelector(`mark[data-idx="${idx}"]`)
      el?.classList.add('active')
    }
  },
)

function onMouseover(event: Event) {
  const el = (event.target as HTMLElement).closest('mark') as HTMLElement | null
  if (el && el.dataset.idx !== undefined) {
    emit('hover', Number(el.dataset.idx))
  }
}

function onMouseleave() {
  emit('hover', null)
}
</script>

<template>
  <div
    ref="rootRef"
    class="contract-highlight"
    @mouseover="onMouseover"
    @mouseleave="onMouseleave"
  >
    <pre class="article-text" v-html="highlightedHtml" />
  </div>
</template>

<style scoped>
.contract-highlight {
  position: relative;
}

.article-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  line-height: 2;
  color: #cdd7ee;
  margin: 0;
  cursor: text;
}

.article-text :deep(mark.hl) {
  padding: 1px 2px;
  border-radius: 4px;
  cursor: pointer;
  transition: filter 0.15s ease, box-shadow 0.15s ease;
}

.article-text :deep(mark.hl-high) {
  background: rgba(248, 113, 113, 0.22);
  color: #ffd7d7;
  border-bottom: 2px solid #f87171;
}

.article-text :deep(mark.hl-medium) {
  background: rgba(251, 191, 36, 0.18);
  color: #ffe4a3;
  border-bottom: 2px solid #fbbf24;
}

.article-text :deep(mark.hl-low) {
  background: rgba(52, 211, 153, 0.16);
  color: #b6f6df;
  border-bottom: 2px solid #34d399;
}

.article-text :deep(mark.hl:hover),
.article-text :deep(mark.hl.active) {
  filter: brightness(1.4);
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.45);
  outline: 1px solid rgba(34, 211, 238, 0.5);
}
</style>