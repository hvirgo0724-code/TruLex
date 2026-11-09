<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'
import type { AuditItem, AuditResponse } from '../types'

const items = ref<AuditItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const errorMsg = ref('')

function formatTime(value: unknown): string {
  if (!value) return '-'
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const { data } = await http.get<AuditResponse>('/admin/audit', {
      params: { page: page.value, size: size.value },
    })
    items.value = data.items ?? []
    total.value = data.total ?? 0
  } catch (err) {
    errorMsg.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

function onPageChange(p: number) {
  page.value = p
  void load()
}

function onSizeChange(s: number) {
  size.value = s
  page.value = 1
  void load()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">审计日志</div>
        <div class="page-subtitle">系统操作留痕 · 合规审计追溯</div>
      </div>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <div class="tech-card table-wrap">
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" :closable="false" show-icon class="error" />

      <el-table
        v-loading="loading"
        :data="items"
        style="width: 100%"
        :header-cell-style="{
          background: 'transparent',
          color: '#9aa6c0',
          fontWeight: 600,
        }"
      >
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column label="用户" min-width="120">
          <template #default="{ row }">
            {{ row.username || row.user || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="140">
          <template #default="{ row }">
            <el-tag size="small" effect="dark">{{ row.action || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource" label="资源" min-width="160" />
        <el-table-column prop="detail" label="详情" min-width="240" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP" width="140" />
        <el-table-column label="时间" width="190">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :current-page="page"
          :page-size="size"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.error {
  margin-bottom: 14px;
}

.table-wrap {
  padding: 8px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 8px 4px;
}
</style>