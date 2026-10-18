<template>
  <div class="admin-layout">
    <aside class="sidebar">
      <div class="brand">
        <span class="logo">杰</span>
        <span class="brand-text">杰哥硬字幕提取<small>管理后台</small></span>
      </div>
      <el-menu :default-active="route.name" router class="menu">
        <el-menu-item index="admin-dashboard" :route="{ name: 'admin-dashboard' }">
          <el-icon><DataAnalysis /></el-icon><span>概览</span>
        </el-menu-item>
        <el-menu-item index="admin-codes" :route="{ name: 'admin-codes' }">
          <el-icon><Ticket /></el-icon><span>激活码管理</span>
        </el-menu-item>
        <el-menu-item index="admin-users" :route="{ name: 'admin-users' }">
          <el-icon><User /></el-icon><span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="admin-tasks" :route="{ name: 'admin-tasks' }">
          <el-icon><Files /></el-icon><span>提取任务</span>
        </el-menu-item>
      </el-menu>
      <div class="back">
        <el-button text type="primary" @click="$router.push('/')">返回用户端</el-button>
      </div>
    </aside>
    <main class="content">
      <div class="top-bar">
        <div class="title">{{ currentTitle }}</div>
        <el-dropdown>
          <span class="admin">{{ userStore.user?.email }}</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="logout">退出</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <div class="page">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const titles = {
  'admin-dashboard': '数据概览',
  'admin-codes': '激活码管理',
  'admin-users': '用户管理',
  'admin-tasks': '提取任务'
}
const currentTitle = computed(() => titles[String(route.name)] || '管理后台')

function logout() {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-layout { display: flex; height: 100vh; background: var(--zm-bg); }
.sidebar {
  width: 210px; display: flex; flex-direction: column;
  background: var(--zm-bg-soft);
  border-right: 1px solid var(--zm-line);
}
.brand {
  display: flex; align-items: center; gap: 9px;
  padding: 16px 14px;
  border-bottom: 1px solid var(--zm-line);
}
.brand .logo {
  width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
  background: linear-gradient(135deg, #e6b455 0%, #d2952a 100%);
  color: #fff; font-size: 16px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(210, 149, 42, 0.26);
}
.brand-text { font-size: 13px; font-weight: 700; color: var(--zm-text); line-height: 1.25; }
.brand-text small { display: block; font-size: 11px; font-weight: 400; color: var(--zm-text-dim); }
.menu { flex: 1; border-right: none; background: transparent; padding-top: 6px; }
.menu :deep(.el-menu-item) {
  color: var(--zm-text-dim); border-radius: 8px; margin: 2px 8px; height: 42px;
}
.menu :deep(.el-menu-item:hover) { background: var(--zm-accent-soft); color: var(--zm-accent-strong); }
.menu :deep(.el-menu-item.is-active) { background: var(--zm-accent); color: #fff; }
.menu :deep(.el-menu-item.is-active:hover) { background: var(--zm-accent); color: #fff; }
.back { padding: 12px; border-top: 1px solid var(--zm-line); text-align: center; }
.content { flex: 1; overflow: auto; }
.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 24px; background: #fff; border-bottom: 1px solid var(--zm-line);
}
.top-bar .title { font-size: 16px; font-weight: 600; color: var(--zm-text); }
.admin { font-size: 13px; color: var(--zm-text-dim); cursor: pointer; }
.admin:hover { color: var(--zm-accent); }
.page { padding: 20px 24px; }
</style>
