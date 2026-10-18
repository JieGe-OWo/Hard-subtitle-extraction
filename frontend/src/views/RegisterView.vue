<template>
  <div class="auth-page">
    <div class="auth-box">
      <div class="brand">
        <div class="logo">注</div>
        <h1>注册账号</h1>
        <p>注册后需要输入激活码才能使用</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="邮箱" prop="email">
          <div style="display: flex; gap: 8px; width: 100%">
            <el-input v-model="form.email" placeholder="请输入邮箱" :prefix-icon="Message" />
            <el-button :disabled="codeSending || cooldown > 0" :loading="codeSending" @click="sendCode">
              {{ cooldown > 0 ? `${cooldown}s` : '获取验证码' }}
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="邮箱验证码" prop="code">
          <el-input v-model="form.code" maxlength="6" placeholder="6 位数字验证码" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位" :prefix-icon="Lock" />
        </el-form-item>
        <el-form-item label="确认密码" prop="password2">
          <el-input v-model="form.password2" type="password" show-password placeholder="再次输入密码" />
        </el-form-item>
        <el-button type="primary" size="large" class="submit" :loading="loading" @click="handleRegister">注 册</el-button>
      </el-form>
      <div class="foot">
        <span>已有账号？</span>
        <router-link to="/login">直接登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Message, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/auth'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)
const codeSending = ref(false)
const cooldown = ref(0)

const form = reactive({ email: '', code: '', password: '', password2: '' })
const rules = {
  email: [{ required: true, type: 'email', message: '请输入正确的邮箱', trigger: 'blur' }],
  code: [{ required: true, len: 6, message: '请输入 6 位验证码', trigger: 'blur' }],
  password: [{ required: true, min: 6, message: '密码至少 6 位', trigger: 'blur' }],
  password2: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_, value, cb) => (value === form.password ? cb() : cb(new Error('两次密码不一致'))),
      trigger: 'blur'
    }
  ]
}

async function sendCode() {
  if (!/^\S+@\S+\.\S+$/.test(form.email)) {
    ElMessage.warning('请输入正确的邮箱')
    return
  }
  codeSending.value = true
  try {
    await authApi.sendRegisterCode(form.email)
    ElMessage.success('验证码已发送')
    cooldown.value = 60
    const timer = setInterval(() => {
      cooldown.value--
      if (cooldown.value <= 0) clearInterval(timer)
    }, 1000)
  } finally {
    codeSending.value = false
  }
}

async function handleRegister() {
  await formRef.value.validate()
  loading.value = true
  try {
    await userStore.register(form.email, form.code, form.password)
    ElMessage.success('注册成功，请输入激活码')
    router.push('/activate')
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
.brand { text-align: center; margin-bottom: 24px; }
.logo {
  width: 56px; height: 56px; border-radius: 14px;
  background: linear-gradient(135deg, #e6b455 0%, #d2952a 100%);
  color: #fff; font-size: 28px; line-height: 56px; margin: 0 auto 12px; font-weight: 600;
  box-shadow: 0 6px 16px rgba(210, 149, 42, 0.28);
}
.brand h1 { font-size: 20px; margin: 0 0 4px; color: var(--zm-text); }
.brand p { font-size: 12px; color: var(--zm-text-dim); margin: 0; }
.submit { width: 100%; }
.foot { text-align: center; margin-top: 16px; font-size: 13px; color: var(--zm-text-dim); }
.foot a { color: var(--zm-accent); text-decoration: none; margin-left: 4px; font-weight: 500; }
.foot a:hover { color: var(--zm-accent-strong); }
</style>
