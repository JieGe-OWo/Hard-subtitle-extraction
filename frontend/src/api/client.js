import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 10 * 60 * 1000
})

/**
 * 桌面版免登录：令牌失效时自动换一个新的（并只发一次请求，避免并发重复换取）
 * 旧逻辑是「401 就删令牌跳登录页」——桌面版没有账号体系，一跳就把用户踢出当前页面，
 * 表现就是「校对页视频不播放 / 打不开」。
 */
let reloginPromise = null
function desktopRelogin() {
  if (!window.__ZIMU_DESKTOP__) return Promise.resolve(false)
  if (!reloginPromise) {
    reloginPromise = import('@/api/auth')
      .then(({ authApi }) => authApi.desktopLogin())
      .then(res => {
        if (res?.access_token) {
          localStorage.setItem('zimu_token', res.access_token)
          return true
        }
        return false
      })
      .catch(() => false)
      .finally(() => { reloginPromise = null })
  }
  return reloginPromise
}

service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('zimu_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  error => Promise.reject(error)
)

service.interceptors.response.use(
  response => {
    if (response.data && typeof response.data === 'object' && 'dev' in response.data) {
      if (response.data.dev && response.data.code) {
        ElMessage.warning({
          message: `SMTP 未配置（开发模式），验证码：${response.data.code}`,
          duration: 20000
        })
      }
    }
    return response.data
  },
  async error => {
    let data = error.response?.data
    // responseType: 'blob' 的请求失败时，后端返回的 JSON 错误体也是 Blob
    if (data instanceof Blob) {
      try {
        data = JSON.parse(await data.text())
      } catch {
        data = null
      }
    }
    let msg = data?.detail || error.message || '请求失败'
    if (Array.isArray(msg)) msg = msg.map(d => d.msg).join('；')

    if (error.response?.status === 401) {
      const config = error.config || {}
      // 桌面版：静默换令牌后重放这一次请求（只重试一次，避免死循环）
      if (window.__ZIMU_DESKTOP__) {
        if (!config.__retried && await desktopRelogin()) {
          config.__retried = true
          config.headers = config.headers || {}
          config.headers.Authorization = `Bearer ${localStorage.getItem('zimu_token')}`
          return service(config)
        }
        ElMessage.error('本地授权失效，请刷新页面重试')
        return Promise.reject(new Error(msg))
      }
      const isLoginPage = router.currentRoute.value.path === '/login'
      localStorage.removeItem('zimu_token')
      if (!isLoginPage) {
        if (typeof msg === 'string' && msg !== '未登录') ElMessage.error(msg)
        router.push('/login')
      }
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(new Error(msg))
  }
)

export default service
