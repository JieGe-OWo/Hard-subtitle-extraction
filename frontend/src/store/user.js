import { defineStore } from 'pinia'
import { authApi } from '@/api/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('zimu_token') || '',
    user: null,
    // 桌面版标记：由启动引导写入，决定是否免登录、隐藏账号相关入口
    desktop: localStorage.getItem('zimu_desktop') === '1'
  }),
  getters: {
    isAdmin: state => state.user?.role === 'admin',
    isActive: state => state.user?.status === 'active',
    isLoggedIn: state => !!state.token,
    isDesktop: state => state.desktop
  },
  actions: {
    setToken(token) {
      this.token = token
      localStorage.setItem('zimu_token', token)
    },
    setDesktop(flag) {
      this.desktop = !!flag
      localStorage.setItem('zimu_desktop', flag ? '1' : '0')
    },
    /** 桌面版免登录：静默换一个本地令牌 */
    async desktopLogin() {
      const res = await authApi.desktopLogin()
      this.setToken(res.access_token)
      await this.fetchMe()
      return this.user
    },
    async login(email, password) {
      const res = await authApi.login(email, password)
      this.setToken(res.access_token)
      await this.fetchMe()
    },
    async register(email, code, password) {
      const res = await authApi.register(email, code, password)
      this.setToken(res.access_token)
      await this.fetchMe()
    },
    async fetchMe() {
      this.user = await authApi.me()
      return this.user
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('zimu_token')
    }
  }
})
