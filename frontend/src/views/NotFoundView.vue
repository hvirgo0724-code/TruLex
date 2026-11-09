<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome() {
  router.push('/')
}
</script>

<template>
  <div class="notfound">
    <div class="code">404</div>
    <div class="msg">页面走丢了，它可能已被删除或不在管辖范围内</div>
    <el-button type="primary" @click="goHome">返回首页</el-button>
  </div>
</template>

<style scoped>
.notfound {
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.code {
  font-size: 96px;
  font-weight: 800;
  background: linear-gradient(135deg, #4f7dff, #22d3ee);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: 6px;
}

.msg {
  color: #9aa6c0;
  margin-bottom: 12px;
}
</style>