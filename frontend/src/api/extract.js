import request from './client'

export const extractApi = {
  meta() {
    return request.get('/api/extract/meta')
  },
  upload(file, onProgress) {
    const form = new FormData()
    form.append('file', file)
    return request.post('/api/extract/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: e => onProgress && onProgress(e)
    })
  },
  start(taskId, payload) {
    return request.post(`/api/extract/${taskId}/start`, payload)
  },
  status(taskId) {
    return request.get(`/api/extract/${taskId}/status`)
  },
  files(taskId) {
    return request.get(`/api/extract/${taskId}/files`)
  },
  content(taskId, filename) {
    return request.get(`/api/extract/${taskId}/content/${encodeURIComponent(filename)}`)
  },
  cancel(taskId) {
    return request.post(`/api/extract/${taskId}/cancel`)
  },
  // 预览图和下载都必须带上 Authorization 头，所以走 axios 取二进制，
  // 不能用 <img src> / window.open（那样不会带 token，后端会返 401）。
  preview(taskId, t = 0) {
    return request.get(`/api/extract/${taskId}/preview`, {
      params: { t },
      responseType: 'blob'
    })
  },
  download(taskId, filename) {
    return request.get(`/api/extract/${taskId}/download/${encodeURIComponent(filename)}`, {
      responseType: 'blob'
    })
  },
  history() {
    return request.get('/api/extract/history')
  },
  // 校对页：<video> 直链带不了请求头，token 走查询参数（后端已支持 ?token=）
  videoUrl(taskId) {
    const token = localStorage.getItem('zimu_token') || ''
    return `/api/extract/${taskId}/video?token=${encodeURIComponent(token)}`
  },
  // 直链播放失败时的兜底：用 axios 带着鉴权头把整段视频取成 blob
  videoBlob(taskId) {
    return request.get(`/api/extract/${taskId}/video`, { responseType: 'blob' })
  },
  subtitles(taskId) {
    return request.get(`/api/extract/${taskId}/subtitles`)
  },
  saveSubtitles(taskId, subtitles) {
    return request.post(`/api/extract/${taskId}/subtitles`, { subtitles })
  }
}
