<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { User, Lock, Message } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const mode = ref<'login' | 'register'>('login')

const formRef = ref<FormInstance>()
const form = reactive({
  username: '',
  password: '',
  email: '',
})

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 64, message: '用户名长度 3-64 位', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码长度 6-128 位', trigger: 'blur' },
  ],
}

const loading = ref(false)
const errorMsg = ref('')

async function doLogin() {
  await auth.login(form.username, form.password)
  const redirect = (route.query.redirect as string | undefined) || '/chat'
  await router.push(redirect)
}

async function doRegister() {
  await auth.register({
    username: form.username,
    email: form.email,
    password: form.password,
  })
  await router.push('/chat')
}

async function submit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  errorMsg.value = ''
  try {
    if (mode.value === 'login') {
      await doLogin()
    } else {
      await doRegister()
    }
  } catch (err) {
    errorMsg.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

function switchMode(target: 'login' | 'register') {
  mode.value = target
  errorMsg.value = ''
  formRef.value?.clearValidate()
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <div class="brand-badge">法</div>
        <h1 class="brand-title">途律 · TruLex</h1>
        <p class="brand-sub">TRULEX · TRANSPORTATION & LEGAL INTELLIGENCE</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="mode === 'login' ? loginRules : registerRules"
        class="login-form"
        @submit.prevent="submit"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            size="large"
            placeholder="用户名"
            :prefix-icon="User"
            @keydown.enter="submit"
          />
        </el-form-item>

        <el-form-item v-if="mode === 'register'" prop="email">
          <el-input
            v-model="form.email"
            size="large"
            placeholder="邮箱"
            :prefix-icon="Message"
            @keydown.enter="submit"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            size="large"
            type="password"
            placeholder="密码"
            show-password
            :prefix-icon="Lock"
            @keydown.enter="submit"
          />
        </el-form-item>

        <el-alert v-if="errorMsg" :title="errorMsg" type="error" :closable="false" show-icon class="error" />

        <el-button
          type="primary"
          size="large"
          class="submit-btn"
          :loading="loading"
          @click="submit"
        >
          {{ mode === 'login' ? '登 录' : '注 册' }}
        </el-button>
      </el-form>

      <p class="tip">
        {{ mode === 'login' ? '请输入账号密码进入法律智能体工作台' : '创建一个新账号，注册后自动登录' }}
      </p>

      <p class="switch">
        <template v-if="mode === 'login'">
          没有账号？<a class="switch-link" @click="switchMode('register')">立即注册</a>
        </template>
        <template v-else>
          已有账号？<a class="switch-link" @click="switchMode('login')">返回登录</a>
        </template>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.login-card {
  width: 400px;
  padding: 44px 40px 36px;
  background: linear-gradient(160deg, #131a30, #0d1220);
  border: 1px solid rgba(148, 172, 255, 0.16);
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  position: relative;
  overflow: hidden;
}

.login-card::before {
  content: '';
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, #4f7dff, #22d3ee);
}

.brand {
  text-align: center;
  margin-bottom: 30px;
}

.brand-badge {
  width: 60px;
  height: 60px;
  margin: 0 auto 16px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 800;
  color: #06121f;
  background: linear-gradient(135deg, #4f7dff, #22d3ee);
  box-shadow: 0 0 28px rgba(79, 125, 255, 0.55);
}

.brand-title {
  margin: 0;
  font-size: 22px;
  letter-spacing: 2px;
  color: #fff;
}

.brand-sub {
  margin: 8px 0 0;
  font-size: 11px;
  letter-spacing: 3px;
  color: #6b7892;
}

.error {
  margin-bottom: 16px;
}

.submit-btn {
  width: 100%;
  height: 46px;
  font-size: 16px;
  letter-spacing: 6px;
  background: linear-gradient(90deg, #4f7dff, #22d3ee);
  border: none;
}

.tip {
  margin: 18px 0 0;
  text-align: center;
  font-size: 12px;
  color: #6b7892;
}

.switch {
  margin: 14px 0 0;
  text-align: center;
  font-size: 13px;
  color: #6b7892;
}

.switch-link {
  color: #4f7dff;
  cursor: pointer;
  text-decoration: none;
}

.switch-link:hover {
  color: #22d3ee;
}
</style>