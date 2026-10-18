import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/user'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { public: true } },
  { path: '/activate', name: 'activate', component: () => import('@/views/ActivateView.vue') },
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
  { path: '/review/:taskId', name: 'review', component: () => import('@/views/ReviewView.vue') },
  {
    path: '/admin',
    component: () => import('@/views/admin/AdminLayout.vue'),
    meta: { admin: true },
    children: [
      { path: '', redirect: { name: 'admin-dashboard' } },
      { path: 'dashboard', name: 'admin-dashboard', component: () => import('@/views/admin/DashboardView.vue') },
      { path: 'codes', name: 'admin-codes', component: () => import('@/views/admin/CodesView.vue') },
      { path: 'users', name: 'admin-users', component: () => import('@/views/admin/UsersView.vue') },
      { path: 'tasks', name: 'admin-tasks', component: () => import('@/views/admin/TasksView.vue') }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async to => {
  const userStore = useUserStore()
  const isDesktop = window.__ZIMU_DESKTOP__ === true ||
    localStorage.getItem('zimu_desktop') === '1'

  // 桌面版没有账号体系：登录/注册/激活页直接回首页
  if (isDesktop && ['login', 'register', 'activate'].includes(String(to.name))) {
    return { name: 'home' }
  }
  if (to.meta.public) return true

  if (!userStore.token) {
    if (isDesktop) {
      // 桌面版免登录：静默补一个本地令牌，失败也放行（接口自己会兜底）
      try {
        await userStore.desktopLogin()
      } catch {
        return true
      }
    } else {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }
  if (!userStore.user) {
    try {
      await userStore.fetchMe()
    } catch {
      return isDesktop ? true : { name: 'login' }
    }
  }
  if (to.meta.admin && userStore.user?.role !== 'admin') {
    ElMessage.error('需要管理员权限')
    return { name: 'home' }
  }
  return true
})

export default router
