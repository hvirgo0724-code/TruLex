<script setup lang="ts">
import { computed, ref } from 'vue'
import { UploadFilled, DocumentChecked } from '@element-plus/icons-vue'
import type { ContractIssue, RiskLevel } from '../types'
import { reviewContractFile, reviewContractText } from '../api/contract'
import ContractHighlight from '../components/ContractHighlight.vue'

type RiskTag = 'danger' | 'warning' | 'success'

const RISK_META: Record<RiskLevel, { label: string; tag: RiskTag }> = {
  high: { label: '高风险', tag: 'danger' },
  medium: { label: '中风险', tag: 'warning' },
  low: { label: '低风险', tag: 'success' },
}

const textInput = ref('')
const fileName = ref('')
const originalText = ref('')
const issues = ref<ContractIssue[]>([])
const activeIndex = ref<number | null>(null)
const reviewing = ref(false)
const errorMsg = ref('')

const fileInputRef = ref<HTMLInputElement | null>(null)

const hasOriginal = computed(() => originalText.value.length > 0)

function setActive(i: number | null) {
  activeIndex.value = i
}

async function doReviewText() {
  const t = textInput.value.trim()
  if (!t) return
  reviewing.value = true
  errorMsg.value = ''
  issues.value = []
  try {
    issues.value = await reviewContractText(t)
    originalText.value = t
  } catch (err) {
    errorMsg.value = (err as Error).message
  } finally {
    reviewing.value = false
  }
}

function triggerFile() {
  fileInputRef.value?.click()
}

async function doReviewFile(file: File) {
  reviewing.value = true
  errorMsg.value = ''
  issues.value = []
  originalText.value = ''
  try {
    issues.value = await reviewContractFile(file)
  } catch (err) {
    errorMsg.value = (err as Error).message
  } finally {
    reviewing.value = false
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    fileName.value = file.name
    void doReviewFile(file)
  }
  input.value = ''
}

function resetAll() {
  textInput.value = ''
  fileName.value = ''
  originalText.value = ''
  issues.value = []
  activeIndex.value = null
  errorMsg.value = ''
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">运单审查</div>
        <div class="page-subtitle">上传或粘贴运输合同 / 运单文本，自动识别并标注法律风险条款</div>
      </div>
      <el-button v-if="issues.length || originalText.length" @click="resetAll">清空重来</el-button>
    </div>

    <!-- 输入区 -->
    <div class="tech-card input-box">
      <div class="input-row">
        <div class="text-input">
          <el-input
            v-model="textInput"
            type="textarea"
            :rows="5"
            resize="none"
            placeholder="在此粘贴运输合同 / 运单条款文本…"
          />
        </div>
        <div class="divider"><span>或</span></div>
        <div class="file-input">
          <input
            ref="fileInputRef"
            type="file"
            accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            class="hidden-input"
            @change="onFileChange"
          />
          <el-button :icon="UploadFilled" size="large" class="upload-btn" @click="triggerFile">
            上传 docx / pdf
          </el-button>
          <p v-if="fileName" class="filename">已选择：{{ fileName }}</p>
        </div>
      </div>

      <div class="input-actions">
        <el-button type="primary" size="large" :icon="DocumentChecked" :loading="reviewing" @click="doReviewText">
          {{ reviewing ? '审查中…' : '开始审查' }}
        </el-button>
      </div>

      <el-alert v-if="errorMsg" :title="errorMsg" type="error" :closable="false" show-icon class="error" />
    </div>

    <!-- 结果区 -->
    <div v-if="issues.length" class="result">
      <!-- 左侧原文 -->
      <div class="tech-card origin-panel">
        <div class="panel-head">
          <span class="panel-title">运单原文</span>
          <span class="panel-hint">悬停高亮联动右侧风险点</span>
        </div>
        <div class="origin-body">
          <ContractHighlight
            v-if="hasOriginal"
            :text="originalText"
            :issues="issues"
            :active-index="activeIndex"
            @hover="setActive"
          />
          <!-- 文件模式：无全文，退化为条款摘录 -->
          <div v-else class="clauses">
            <p v-if="fileName" class="filename">文件：{{ fileName }}</p>
            <div
              v-for="(issue, i) in issues"
              :key="i"
              class="clause"
              :class="[`risk-${issue.risk_level}`, { active: activeIndex === i }]"
              @mouseenter="setActive(i)"
              @mouseleave="setActive(null)"
            >
              {{ issue.highlight || issue.clause }}
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧风险清单 -->
      <div class="tech-card risk-panel">
        <div class="panel-head">
          <span class="panel-title">风险清单</span>
          <el-tag size="small" effect="dark">{{ issues.length }} 项</el-tag>
        </div>

        <div class="risk-list">
          <div
            v-for="(issue, i) in issues"
            :key="i"
            class="risk-item"
            :class="{ active: activeIndex === i }"
            @mouseenter="setActive(i)"
            @mouseleave="setActive(null)"
          >
            <div class="risk-head">
              <el-tag :type="RISK_META[issue.risk_level].tag" size="small" effect="dark">
                {{ RISK_META[issue.risk_level].label }}
              </el-tag>
              <span class="risk-idx">#{{ i + 1 }}</span>
            </div>
            <p class="clause-text">{{ issue.clause || issue.highlight }}</p>
            <div class="suggestion">
              <span class="sug-label">审查建议</span>
              <p>{{ issue.suggestion }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hidden-input {
  display: none;
}

.input-row {
  display: flex;
  gap: 20px;
  align-items: stretch;
}

.text-input {
  flex: 1;
}

.text-input :deep(.el-textarea__inner) {
  background: #0b1020;
  border-color: rgba(148, 172, 255, 0.12);
  color: #e6ebf7;
  font-family: inherit;
  line-height: 1.8;
}

.divider {
  display: flex;
  align-items: center;
  color: #6b7892;
  font-size: 13px;
}

.file-input {
  width: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px dashed rgba(148, 172, 255, 0.3);
  border-radius: 12px;
  padding: 16px;
}

.upload-btn {
  width: 100%;
}

.filename {
  font-size: 12px;
  color: #9aa6c0;
  margin: 0;
  text-align: center;
  word-break: break-all;
}

.input-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.error {
  margin-top: 12px;
}

/* ---------- 结果区 ---------- */
.result {
  display: flex;
  gap: 20px;
  margin-top: 20px;
  align-items: flex-start;
}

.origin-panel {
  flex: 1;
  min-width: 0;
  align-self: stretch;
}

.risk-panel {
  width: 400px;
  flex: 0 0 auto;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--brand-border);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}

.panel-hint {
  font-size: 11px;
  color: #6b7892;
}

.origin-body {
  max-height: 62vh;
  overflow-y: auto;
}

.clauses {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.clause {
  padding: 12px 14px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1.8;
  border-left: 3px solid transparent;
  transition: box-shadow 0.15s ease;
}

.clause.risk-high {
  background: rgba(248, 113, 113, 0.1);
  border-left-color: #f87171;
  color: #ffd7d7;
}

.clause.risk-medium {
  background: rgba(251, 191, 36, 0.08);
  border-left-color: #fbbf24;
  color: #ffe4a3;
}

.clause.risk-low {
  background: rgba(52, 211, 153, 0.08);
  border-left-color: #34d399;
  color: #b6f6df;
}

.clause.active {
  box-shadow: 0 0 14px rgba(34, 211, 238, 0.35);
}

.risk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 62vh;
  overflow-y: auto;
}

.risk-item {
  padding: 14px;
  border-radius: 12px;
  background: #0f1528;
  border: 1px solid rgba(148, 172, 255, 0.1);
  transition: all 0.15s ease;
}

.risk-item.active {
  border-color: rgba(34, 211, 238, 0.5);
  box-shadow: 0 0 16px rgba(34, 211, 238, 0.2);
}

.risk-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.risk-idx {
  color: #6b7892;
  font-size: 12px;
}

.clause-text {
  margin: 0 0 10px;
  color: #d6e2ff;
  font-size: 13px;
  line-height: 1.7;
}

.suggestion {
  background: rgba(79, 125, 255, 0.08);
  border-radius: 8px;
  padding: 8px 10px;
}

.sug-label {
  font-size: 11px;
  color: #22d3ee;
  letter-spacing: 1px;
}

.suggestion p {
  margin: 4px 0 0;
  color: #b8c3dc;
  font-size: 13px;
  line-height: 1.7;
}
</style>