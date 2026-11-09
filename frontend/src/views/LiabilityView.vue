<script setup lang="ts">
import { computed, ref } from 'vue'
import { Search, RefreshLeft, CircleCheck } from '@element-plus/icons-vue'
import { streamChat } from '../api/chat'
import type { Citation } from '../types'

// ---------- 表单要素 ----------
type TransportMode = '公路' | '铁路' | '航空' | '水运/海运' | '快递/寄递' | '多式联运'
type CargoStatus = '货物毁损' | '货物灭失/丢失' | '货物短少' | '运输延误'

const transportMode = ref<TransportMode>('公路')
const cargoStatus = ref<CargoStatus>('货物毁损')
const insured = ref<'是' | '否' | '未知'>('否')
const declaredValue = ref('') // 保价/声明价值
const lossAmount = ref('') // 损失金额（元）
const causeNote = ref('') // 事故经过/原因描述
const freightPaid = ref<'已付' | '未付' | '未知'>('已付')

// ---------- 结果状态 ----------
const analyzing = ref(false)
const answer = ref('')
const citations = ref<Citation[]>([])
const errorMsg = ref('')
const hasResult = ref(false)

const transportModes: TransportMode[] = ['公路', '铁路', '航空', '水运/海运', '快递/寄递', '多式联运']
const cargoStatuses: CargoStatus[] = ['货物毁损', '货物灭失/丢失', '货物短少', '运输延误']

const canAnalyze = computed(() => lossAmount.value.trim() !== '' || causeNote.value.trim() !== '')

// ---------- 拼装专业要素描述 ----------
function buildCaseDescription(): string {
  const parts: string[] = []
  parts.push(`运输方式：${transportMode.value}`)
  parts.push(`货损类型：${cargoStatus.value}`)
  parts.push(`是否保价：${insured.value}`)
  if (declaredValue.value.trim()) parts.push(`保价/声明价值：${declaredValue.value.trim()} 元`)
  if (lossAmount.value.trim()) parts.push(`货损金额：${lossAmount.value.trim()} 元`)
  parts.push(`运费支付情况：${freightPaid.value}`)
  if (causeNote.value.trim()) parts.push(`事故经过：${causeNote.value.trim()}`)

  return (
    `请对以下物流运输纠纷进行货损责任认定：\n` +
    parts.join('；') +
    `。\n请分析：1) 承运人是否承担赔偿责任；2) 有无免责或减轻责任事由；3) 赔偿金额如何计算（结合是否保价、赔偿限额）。`
  )
}

async function doAnalyze() {
  const desc = buildCaseDescription()
  analyzing.value = true
  errorMsg.value = ''
  answer.value = ''
  citations.value = []
  hasResult.value = false
  try {
    await streamChat(
      { message: desc },
      {
        onDelta: (text) => {
          answer.value += text
        },
        onCitations: (cites) => {
          citations.value = cites
        },
        onConversation: () => {
          /* 货损认定页不强制关联会话列表 */
        },
        onDone: () => {
          /* 由 finally 收尾 */
        },
      },
    )
    hasResult.value = true
  } catch (err) {
    errorMsg.value = (err as Error).message
  } finally {
    analyzing.value = false
  }
}

function resetAll() {
  lossAmount.value = ''
  declaredValue.value = ''
  causeNote.value = ''
  answer.value = ''
  citations.value = []
  errorMsg.value = ''
  hasResult.value = false
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">货损责任认定</div>
        <div class="page-subtitle">结构化录入纠纷要素，智能分析承运人责任归属与赔偿计算</div>
      </div>
      <el-button v-if="hasResult" :icon="RefreshLeft" @click="resetAll">重新认定</el-button>
    </div>

    <!-- 要素录入表单 -->
    <div class="tech-card form-card">
      <div class="form-grid">
        <div class="field">
          <label class="field-label">运输方式</label>
          <el-select v-model="transportMode" size="large" class="full">
            <el-option v-for="m in transportModes" :key="m" :value="m" :label="m" />
          </el-select>
        </div>
        <div class="field">
          <label class="field-label">货损类型</label>
          <el-select v-model="cargoStatus" size="large" class="full">
            <el-option v-for="s in cargoStatuses" :key="s" :value="s" :label="s" />
          </el-select>
        </div>
        <div class="field">
          <label class="field-label">是否保价</label>
          <el-radio-group v-model="insured" size="large" class="full">
            <el-radio-button value="是">保价</el-radio-button>
            <el-radio-button value="否">未保价</el-radio-button>
            <el-radio-button value="未知">未知</el-radio-button>
          </el-radio-group>
        </div>
        <div class="field">
          <label class="field-label">运费支付</label>
          <el-radio-group v-model="freightPaid" size="large" class="full">
            <el-radio-button value="已付">已付</el-radio-button>
            <el-radio-button value="未付">未付</el-radio-button>
            <el-radio-button value="未知">未知</el-radio-button>
          </el-radio-group>
        </div>
        <div class="field">
          <label class="field-label">保价/声明价值（元）</label>
          <el-input v-model="declaredValue" size="large" placeholder="如未保价可留空" clearable />
        </div>
        <div class="field">
          <label class="field-label">货损金额（元）</label>
          <el-input v-model="lossAmount" size="large" placeholder="如：5000" clearable />
        </div>
      </div>

      <div class="field" style="margin-top: 4px">
        <label class="field-label">事故经过 / 原因描述（可选）</label>
        <el-input
          v-model="causeNote"
          type="textarea"
          :rows="3"
          resize="none"
          placeholder="如：运输途中因车辆侧翻导致货物毁损；或快递网点因保管不善丢失包裹…"
        />
      </div>

      <div class="form-actions">
        <el-button
          type="primary"
          size="large"
          :icon="Search"
          :loading="analyzing"
          :disabled="!canAnalyze"
          @click="doAnalyze"
        >
          {{ analyzing ? '分析中…' : '开始责任认定' }}
        </el-button>
        <span v-if="!canAnalyze" class="hint">请至少填写货损金额或事故经过</span>
      </div>

      <el-alert v-if="errorMsg" :title="errorMsg" type="error" :closable="false" show-icon class="error" />
    </div>

    <!-- 分析结果 -->
    <div v-if="hasResult || analyzing" class="tech-card result-card">
      <div class="result-head">
        <span class="result-title">
          <el-icon v-if="hasResult"><CircleCheck /></el-icon>
          责任认定分析
        </span>
        <span v-if="citations.length" class="cite-count">援引 {{ citations.length }} 项法规/判例</span>
      </div>

      <div v-if="analyzing && !answer" class="analyzing" v-loading="analyzing">
        正在检索相关法规与判例，分析责任归属…
      </div>

      <div v-else class="answer-body">{{ answer }}</div>

      <div v-if="citations.length" class="citations">
        <div class="cite-title">法律依据引用</div>
        <div v-for="(c, i) in citations" :key="i" class="cite-item">
          <span class="cite-idx">[{{ i + 1 }}]</span>
          <span class="cite-name">{{ c.title }}</span>
          <span v-if="c.snippet" class="cite-snippet">{{ c.snippet }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.form-card {
  padding: 24px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}

.field {
  min-width: 0;
}

.field-label {
  display: block;
  font-size: 13px;
  color: #b8c3dc;
  margin-bottom: 8px;
}

.full {
  width: 100%;
}

.form-actions {
  margin-top: 20px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.hint {
  font-size: 12px;
  color: #6b7892;
}

.error {
  margin-top: 14px;
}

.result-card {
  margin-top: 20px;
  padding: 24px;
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--brand-border);
}

.result-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}

.result-title .el-icon {
  color: #34d399;
}

.cite-count {
  font-size: 12px;
  color: #9aa6c0;
}

.analyzing {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9aa6c0;
  font-size: 13px;
}

.answer-body {
  color: #d6e2ff;
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
}

.citations {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px dashed var(--brand-border);
}

.cite-title {
  font-size: 13px;
  color: #22d3ee;
  margin-bottom: 10px;
  letter-spacing: 1px;
}

.cite-item {
  display: flex;
  gap: 8px;
  align-items: baseline;
  padding: 6px 0;
  font-size: 13px;
}

.cite-idx {
  color: #4f7dff;
  flex: 0 0 auto;
}

.cite-name {
  color: #e6ebf7;
  flex: 0 0 auto;
  font-weight: 500;
}

.cite-snippet {
  color: #9aa6c0;
  word-break: break-word;
}

@media (max-width: 1100px) {
  .form-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
