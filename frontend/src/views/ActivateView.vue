<template>
  <div class="activate-page">
    <div class="activate-box">
      <el-result icon="warning" title="账号待激活" :sub-title="`当前邮箱：${user?.email || ''}`">
        <template #extra>
          <p class="tip">请输入有效激活码以启用字幕提取功能（每个激活码仅可使用一次）</p>
          <div class="row">
            <el-input v-model="code" placeholder="请输入激活码" size="large" clearable style="max-width: 320px" />
            <el-button type="primary" size="large" :loading="loading" @click="handleActivate">激 活</el-button>
          </div>
          <div class="row" style="margin-top: 16px">
            <el-button text @click="loadStatus">刷新状态</el-button>
            <el-button text type="danger" @click="logout">退出登录</el-button>
          </div>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/auth'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()
const user = ref(null)
const code = ref('')
const loading = ref(false)

async function loadStatus() {
  try {
    await userStore.fetchMe()
    user.value = userStore.user
    if (userStore.user?.status === 'active') {
      ElMessage.success('账号已激活')
      router.replace('/')
    }
  } catch {
    router.push('/login')
  }
}

async function handleActivate() {
  if (!code.value.trim()) {
    ElMessage.warning('请输入激活码')
    return
  }
  loading.value = true
  try {
    await authApi.activate(code.value.trim())
    ElMessage.success('激活成功')
    router.replace('/')
  } finally {
    loading.value = false
  }
}

function logout() {
  userStore.logout()
  router.push('/login')
}

onMounted(loadStatus)
</script>

<style scoped>
.activate-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: radial-gradient(1200px 600px at 50% -10%, #fff6dd 0%, #fffbef 55%, #fdf6e4 100%);
}
.activate-box {
  background: #fff; border: 1px solid var(--zm-line);
  border-radius: 16px; padding: 32px 48px; box-shadow: var(--zm-shadow-hover);
}
.tip { color: var(--zm-text-dim); font-size: 13px; }
.row { display: flex; gap: 12px; justify-content: center; align-items: center; }
</style>
