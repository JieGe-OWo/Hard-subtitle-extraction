import request from './client'

export const adminApi = {
  dashboard() {
    return request.get('/api/admin/dashboard')
  },
  codes(params) {
    return request.get('/api/admin/codes', { params })
  },
  generateCodes(data) {
    return request.post('/api/admin/codes', data)
  },
  addCustomCode(data) {
    return request.post('/api/admin/codes/custom', data)
  },
  updateCode(id, data) {
    return request.patch(`/api/admin/codes/${id}`, data)
  },
  deleteCode(id) {
    return request.delete(`/api/admin/codes/${id}`)
  },
  users(params) {
    return request.get('/api/admin/users', { params })
  },
  updateUser(id, data) {
    return request.patch(`/api/admin/users/${id}`, data)
  },
  tasks(params) {
    return request.get('/api/admin/tasks', { params })
  }
}
