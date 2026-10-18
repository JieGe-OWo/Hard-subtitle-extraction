<template>
  <div class="auth-page">
    <div class="auth-box">
      <div class="brand">
        <div class="logo">杰</div>
        <h1>杰哥硬字幕提取</h1>
        <p>视频硬字幕提取 · CPU 部署 · 激活码激活</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="handleLogin">
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" :prefix-icon="Message" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" :prefix-icon="Lock" />
        </el-form-item>
        <el-button type="primary" size="large" class="submit" :loading="loading" @click="handleLogin">登 录</el-button>
      </el-form>
      <div class="foot">
        <span>还没有账号？</span>
        <router-link to="/register">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)
const form = reactive({ email: '', password: '' })
const rules = {
  email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function handleLogin() {
  await formRef.value.validate()
  loading.value = true
  try {
    await userStore.login(form.email, form.password)
    router.replace(userStore.user?.role === 'admin' ? '/admin/dashboard' : '/')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(1200px 600px at 50% -10%, #fff6dd 0%, #fffbef 55%, #fdf6e4 100%);
}
.auth-box {
  width: 400px;
  background: #fff;
  border: 1px solid var(--zm-line);
  border-radius: 16px;
  padding: 36px 32px;
  box-shadow: var(--zm-shadow-hover);
}
.brand {
  text-align: center;
  margin-bottom: 24px;
}
.logo {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, #e6b455 0%, #d2952a 100%);
  color: #fff;
  font-size: 28px;
  line-height: 56px;
  margin: 0 auto 12px;
  font-weight: 600;
  box-shadow: 0 6px 16px rgba(210, 149, 42, 0.28);
}
.brand h1 { font-size: 20px; margin: 0 0 4px; color: var(--zm-text); letter-spacing: 1px; }
.brand p { font-size: 12px; color: var(--zm-text-dim); margin: 0; }
.submit { width: 100%; }
.foot {
  text-align: center;
  margin-top: 16px;
  font-size: 13px;
  color: var(--zm-text-dim);
}
.foot a { color: var(--zm-accent); text-decoration: none; margin-left: 4px; font-weight: 500; }
.foot a:hover { color: var(--zm-accent-strong); }
</style>
