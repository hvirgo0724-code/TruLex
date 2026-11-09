<script setup lang="ts">
import { computed, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { searchKnowledge } from '../api/knowledge'
import type { SearchHit } from '../types'

const query = ref('')
const topK = ref(10)
const loading = ref(false)
const searched = ref(false)
const errorMsg = ref('')
const hits = ref<SearchHit[]>([])

// 来源类型筛选
type SourceFilter = 'all' | 'statute' | 'case' | 'knowledge'
const sourceFilter = ref<SourceFilter>('all')

const SOURCE_META: Record<string, { label: string; type: 'primary' | 'success' | 'warning' }> = {
  statute: { label: '法规', type: 'primary' },
  case: { label: '判例', type: 'success' },
  knowledge: { label: '概念', type: 'warning' },
}

const filteredHits = computed(() => {
  if (sourceFilter.value === 'all') return hits.value
  return hits.value.filter((h) => h.source === sourceFilter.value)
})

// 各来源命中计数
const sourceCounts = computed(() => {
  const c: Record<string, number> = { statute: 0, case: 0, knowledge: 0 }
  for (const h of hits.value) {
    if (c[h.source] !== undefined) c[h.source] += 1
  }
  return c
})

function scorePercent(score: number): string {
  return `${Math.round(Math.min(Math.max(score, 0), 1) * 100)}%`
}

async function doSearch() {
  const q = query.value.trim()
  if (!q) return
  loading.value = true
  errorMsg.value = ''
  try {
    hits.value = await searchKnowledge(q, topK.value)
    sourceFilter.value = 'all'
    searched.value = true
  } catch (err) {
    errorMsg.value = (err as Error).message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">物流法规 / 判例检索</div>
        <div class="page-subtitle">基于向量相似 + 全文检索的企业级法律知识库</div>
      </div>
    </div>

    <div class="tech-card search-box">
      <div class="search-row">
        <el-input
          v-model="query"
          size="large"
          :prefix-icon="Search"
          placeholder="输入检索关键词，例如：货物毁损赔偿责任、快递丢件赔偿、危险货物运输资质…"
          clearable
          @keydown.enter="doSearch"
        />
        <el-select v-model="topK" size="large" class="topk" aria-label="返回条数">
          <el-option :value="5" label="Top 5" />
          <el-option :value="10" label="Top 10" />
          <el-option :value="20" label="Top 20" />
        </el-select>
        <el-button type="primary" size="large" :icon="Search" :loading="loading" @click="doSearch">
          检索
        </el-button>
      </div>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" :closable="false" show-icon class="error" />
    </div>

    <div v-if="loading" class="tech-card loading" v-loading="loading" />

    <template v-else-if="searched">
      <div v-if="hits.length === 0" class="tech-card empty">
        <p>未检索到相关内容，请尝试更换关键词。</p>
      </div>

      <template v-else>
        <!-- 来源筛选 -->
        <div class="filter-bar">
          <el-radio-group v-model="sourceFilter" size="default">
            <el-radio-button value="all">全部 ({{ hits.length }})</el-radio-button>
            <el-radio-button value="statute">法规 ({{ sourceCounts.statute }})</el-radio-button>
            <el-radio-button value="case">判例 ({{ sourceCounts.case }})</el-radio-button>
            <el-radio-button value="knowledge">概念 ({{ sourceCounts.knowledge }})</el-radio-button>
          </el-radio-group>
        </div>

        <div v-if="filteredHits.length === 0" class="tech-card empty">
          <p>该分类下暂无结果，请切换其他来源类型。</p>
        </div>

        <div v-else class="hit-list">
          <div v-for="(hit, i) in filteredHits" :key="i" class="tech-card hit">
            <div class="hit-head">
              <span class="rank">#{{ i + 1 }}</span>
              <el-tag
                v-if="SOURCE_META[hit.source]"
                size="small"
                effect="dark"
                :type="SOURCE_META[hit.source].type"
                class="source"
              >
                {{ SOURCE_META[hit.source].label }}
              </el-tag>
              <el-tag v-else size="small" effect="plain" class="source-raw">{{ hit.source }}</el-tag>
              <span v-if="hit.title" class="hit-title">{{ hit.title }}</span>
              <span class="score">
                <span class="score-bar">
                  <span class="score-fill" :style="{ width: scorePercent(hit.score) }" />
                </span>
                相关度 {{ hit.score.toFixed(3) }}
              </span>
            </div>
            <p class="hit-text">{{ hit.text }}</p>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.search-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-row .el-input {
  flex: 1;
}

.topk {
  width: 120px;
}

.error {
  margin-top: 12px;
}

.loading {
  height: 160px;
}

.empty {
  text-align: center;
  color: var(--brand-text-secondary);
  padding: 40px;
}

.filter-bar {
  margin-top: 18px;
  display: flex;
  align-items: center;
}

.hit-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 16px;
}

.hit-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.rank {
  font-weight: 700;
  color: #22d3ee;
}

.source-raw {
  background: rgba(148, 172, 255, 0.14);
  border-color: rgba(148, 172, 255, 0.3);
  color: #b8c3dc;
}

.hit-title {
  font-size: 13px;
  font-weight: 600;
  color: #e6ebf7;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60%;
}

.score {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #9aa6c0;
  flex: 0 0 auto;
}

.score-bar {
  width: 90px;
  height: 6px;
  border-radius: 6px;
  background: rgba(148, 172, 255, 0.14);
  overflow: hidden;
}

.score-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #4f7dff, #22d3ee);
  border-radius: 6px;
}

.hit-text {
  margin: 0;
  color: #cdd7ee;
  line-height: 1.8;
  word-break: break-word;
}
</style>
