<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatDotRound,
  DocumentChecked,
  ScaleToOriginal,
  Search,
  DataAnalysis,
  SwitchButton,
  UserFilled,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activePath = computed(() => route.path)

const displayName = computed(
  () => auth.user?.full_name || auth.user?.username || '未登录',
)

function handleLogout() {
  auth.logout()
  router.push({ name: 'login' })
}

function handleCommand(command: string) {
  if (command === 'logout') handleLogout()
}
</script>

<template>
  <div class="app-layout">
    <!-- 侧边导航 -->
    <aside class="sidebar">
      <div class="logo">
        <div class="logo-badge">运</div>
        <div class="logo-text">
          <div class="logo-title">途律 · TruLex</div>
          <div class="logo-sub">TRULEX</div>
        </div>
      </div>

      <el-menu
        :default-active="activePath"
        router
        class="side-menu"
      >
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能对话</span>
        </el-menu-item>
        <el-menu-item index="/contract">
          <el-icon><DocumentChecked /></el-icon>
          <span>运单审查</span>
        </el-menu-item>
        <el-menu-item index="/liability">
          <el-icon><ScaleToOriginal /></el-icon>
          <span>货损责任认定</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Search /></el-icon>
          <span>知识检索</span>
        </el-menu-item>
        <el-menu-item index="/admin">
          <el-icon><DataAnalysis /></el-icon>
          <span>审计日志</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        深色科技 · 正义蓝
      </div>
    </aside>

    <!-- 主区域 -->
    <div class="main">
      <header class="topbar">
        <div class="crumb">
          <span class="crumb-title">{{ (route.meta.title as string) || '' }}</span>
        </div>

        <el-dropdown trigger="click" @command="handleCommand">
          <div class="user-chip">
            <el-icon><UserFilled /></el-icon>
            <span>{{ displayName }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--brand-bg);
}

/* ---------- 侧边栏 ---------- */
.sidebar {
  width: 224px;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #0c1122, #0a0e1a);
  border-right: 1px solid var(--brand-border);
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 22px 18px;
}

.logo-badge {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 800;
  color: #06121f;
  background: linear-gradient(135deg, #4f7dff, #22d3ee);
  box-shadow: 0 0 18px rgba(79, 125, 255, 0.5);
}

.logo-title {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 1px;
}

.logo-sub {
  font-size: 10px;
  color: #6b7892;
  letter-spacing: 2px;
}

.side-menu {
  flex: 1;
  border-right: none;
  background: transparent;
  padding: 8px 10px;
}

.side-menu :deep(.el-menu-item) {
  height: 46px;
  border-radius: 10px;
  margin-bottom: 6px;
  color: #9aa6c0;
}

.side-menu :deep(.el-menu-item:hover) {
  background: rgba(79, 125, 255, 0.1);
  color: #e6ebf7;
}

.side-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(79, 125, 255, 0.24), rgba(34, 211, 238, 0.08));
  color: #fff;
  box-shadow: inset 3px 0 0 #4f7dff;
}

.sidebar-footer {
  padding: 16px;
  font-size: 11px;
  color: #4a5572;
  text-align: center;
  border-top: 1px solid var(--brand-border);
}

/* ---------- 主区域 ---------- */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: 60px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(16, 22, 42, 0.7);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--brand-border);
}

.crumb-title {
  font-size: 15px;
  font-weight: 600;
  color: #e6ebf7;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  border-radius: 20px;
  border: 1px solid var(--brand-border);
  cursor: pointer;
  color: #b8c3dc;
  font-size: 13px;
  transition: all 0.15s ease;
}

.user-chip:hover {
  border-color: rgba(79, 125, 255, 0.5);
  color: #fff;
}

.content {
  flex: 1;
  overflow: auto;
}
</style>