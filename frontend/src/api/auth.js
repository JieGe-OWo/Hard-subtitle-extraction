import request from './client'

export const authApi = {
  sendRegisterCode(email) {
    return request.post('/api/auth/send-register-code', { email })
  },
  register(email, code, password) {
    return request.post('/api/auth/register', { email, code, password })
  },
  login(email, password) {
    return request.post('/api/auth/login', { email, password })
  },
  me() {
    return request.get('/api/auth/me')
  },
  activate(code) {
    return request.post('/api/auth/activate', { code })
  },
  activationStatus() {
    return request.get('/api/auth/activation/status')
  },
  // 桌面版（免账号）：读取运行模式、直接换本地令牌
  appInfo() {
    return request.get('/api/app-info')
  },
  desktopLogin() {
    return request.post('/api/auth/desktop-login')
  }
}
