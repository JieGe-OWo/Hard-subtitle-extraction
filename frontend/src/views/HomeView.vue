<template>
  <div class="home">
    <header class="header">
      <div class="brand">
        <span class="logo">杰</span>
        <span class="title">杰哥硬字幕提取</span>
      </div>
      <div class="actions">
        <el-tag size="small" type="info">{{ userStore.isDesktop ? '桌面版 · 免登录' : 'CPU 部署版' }}</el-tag>
        <el-button v-if="userStore.isAdmin && !userStore.isDesktop" size="small" @click="$router.push('/admin/dashboard')">管理后台</el-button>
        <el-dropdown v-if="!userStore.isDesktop">
          <span class="user">{{ userStore.user?.email }}</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="goActivate" v-if="!userStore.isActive">去激活</el-dropdown-item>
              <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <el-alert v-if="!userStore.isDesktop && !userStore.isActive" type="error" :closable="false" title="账号尚未激活" description="请先输入有效激活码后才能使用字幕提取功能">
      <el-button type="primary" size="small" @click="goActivate">去激活</el-button>
    </el-alert>

    <el-row :gutter="16" class="main">
      <el-col :span="15">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>1. 上传视频 & 框选字幕区域</span>
              <span class="tips">支持 mp4 / mkv / flv / avi / mov 等常见格式，路径请勿包含中文和空格</span>
            </div>
          </template>

          <div class="upload-area">
            <el-upload
              :auto-upload="true"
              :show-file-list="false"
              :http-request="handleUploadFile"
              accept="video/*"
              drag
            >
              <div class="upload-inner">
                <div class="upload-badge"><el-icon :size="26"><UploadFilled /></el-icon></div>
                <div class="upload-main">点击或拖拽视频到此处上传</div>
                <div class="sub">支持 mp4 / mkv / flv / avi / mov（最大 2GB）</div>
              </div>
            </el-upload>
          </div>

          <div v-if="videoInfo" class="video-meta">
            <el-descriptions :column="3" size="small" border>
              <el-descriptions-item label="文件名">{{ videoName }}</el-descriptions-item>
              <el-descriptions-item label="分辨率">{{ videoInfo.width }} × {{ videoInfo.height }}</el-descriptions-item>
              <el-descriptions-item label="帧率">{{ videoInfo.fps.toFixed(2) }} fps</el-descriptions-item>
              <el-descriptions-item label="总帧数">{{ Math.round(videoInfo.frame_count) }}</el-descriptions-item>
              <el-descriptions-item label="时长">
                {{ formatDuration(durationMs) }}
              </el-descriptions-item>
              <el-descriptions-item label="预览帧">
                <el-slider size="small" v-model="previewTime" :min="0" :max="Math.max(durationMs, 1000)" :step="500" @change="reloadPreview" />
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <el-progress v-if="uploadProgress > 0 && uploadProgress < 100" :percentage="uploadProgress" status="success" />
        </el-card>

        <el-card shadow="never" class="area-card" style="margin-top: 16px">
          <template #header>
            <div class="card-head">
              <span>2. 字幕区域</span>
              <el-tag v-if="area" size="small" type="success" effect="light">已选区</el-tag>
              <el-tag v-else size="small" type="info" effect="plain">全屏检测</el-tag>
            </div>
          </template>
          <div class="area-row">
            <div class="area-info">
              <template v-if="area">
                <div class="area-main">x {{ area.xmin }} ~ {{ area.xmax }} ｜ y {{ area.ymin }} ~ {{ area.ymax }}</div>
                <div class="area-sub">识别只在这个范围内进行，速度更快、也不受水印干扰</div>
              </template>
              <template v-else>
                <div class="area-main">还没有框选区域</div>
                <div class="area-sub">建议先框选：框选后识别更快更准（不框选则全屏检测，较慢）</div>
              </template>
            </div>
            <div class="area-btns">
              <el-button type="primary" plain :disabled="!previewUrl" @click="areaDialog = true">
                {{ area ? '重新框选' : '框选字幕区域' }}
              </el-button>
              <el-button v-if="area" text @click="clearArea">清除</el-button>
            </div>
          </div>
        </el-card>

        <subtitle-area-picker
          v-model="areaDialog"
          :image-url="previewUrl"
          :frame-width="videoInfo?.width || 0"
          :frame-height="videoInfo?.height || 0"
          :initial="area"
          @confirm="onAreaConfirm"
        />

        <el-card shadow="never" style="margin-top: 16px">
          <template #header>
            <span>运行日志</span>
          </template>
          <div class="logs" ref="logsRef">
            <div v-for="(line, i) in logs" :key="i">{{ line }}</div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="9">
        <el-card shadow="never" :class="['params-card', { flash: paramsFlash }]">
          <template #header>
            <span>3. 识别参数</span>
          </template>
          <el-form :model="options" label-width="100px" label-position="left" size="small">
            <el-form-item label="字幕语言">
              <el-select v-model="options.language" style="width: 100%">
                <el-option v-for="l in meta.languages" :key="l.code" :label="l.label" :value="l.code" />
              </el-select>
            </el-form-item>
            <el-form-item label="识别模式">
              <el-select v-model="options.mode" style="width: 100%">
                <el-option v-for="m in meta.modes" :key="m.code" :label="m.label" :value="m.code" />
              </el-select>
              <div class="hint">{{ currentMode?.desc }}</div>
            </el-form-item>
            <el-form-item label="字幕位置">
              <el-select v-model="options.subtitleArea" style="width: 100%">
                <el-option v-for="a in meta.subtitle_areas" :key="a.code" :label="a.label" :value="a.code" />
              </el-select>
              <div class="hint">仅用于预处理裁剪；已在左侧框选区域时可保持「未知」</div>
            </el-form-item>
            <el-form-item label="抽帧频率">
              <el-input-number v-model="options.extractFrequency" :min="1" :max="30" />
              <span class="hint">每秒抽取帧数（仅「全屏检测」时生效；已框选区域时按变化检测，不受此影响）</span>
            </el-form-item>
            <el-form-item label="相似阈值%">
              <el-input-number v-model="options.thresholdTextSimilarity" :min="10" :max="100" />
              <div class="hint">去重判断，越高越严格</div>
            </el-form-item>
            <el-form-item label="置信度%">
              <el-input-number v-model="options.dropScore" :min="0" :max="100" />
              <div class="hint">低于该值的识别结果被丢弃</div>
            </el-form-item>
            <el-form-item label="水印过滤">
              <el-switch v-model="options.filterWatermark" />
              <div class="hint">自动移除固定位置文本，可能误删字幕，默认关闭</div>
            </el-form-item>
            <el-form-item label="非字幕过滤">
              <el-switch v-model="options.filterSceneText" />
              <div class="hint">未框选区域时，自动剔除场景文本</div>
            </el-form-item>
            <el-form-item label="生成 TXT">
              <el-switch v-model="options.generateTxt" />
            </el-form-item>
            <el-form-item label="英文分词">
              <el-switch v-model="options.wordSegmentation" />
            </el-form-item>
            <el-form-item label="错别字替换">
              <el-switch v-model="options.typoFix" :disabled="true" />
              <div class="hint">配置 backend/configs/typoMap.json 后自动生效</div>
            </el-form-item>
          </el-form>

          <div class="run-box">
            <el-button type="primary" size="large" :disabled="!taskId || (!userStore.isDesktop && !userStore.isActive)" :loading="running" @click="start">
              {{ taskId ? (status === 'running' ? '运行中...' : '开始提取') : '请先上传视频' }}
            </el-button>
            <el-button size="large" type="danger" plain :disabled="!running" @click="cancel">中止</el-button>
          </div>

          <div class="progress-box" v-if="taskId">
            <div class="p-item"><span>帧提取</span><el-progress :percentage="progress.frame_extract" /></div>
            <div class="p-item"><span>OCR 识别</span><el-progress :percentage="progress.ocr" /></div>
            <div class="p-item"><span>后处理</span><el-progress :percentage="progress.post" /></div>
            <div class="p-item total"><span>总进度</span><el-progress :percentage="progress.overall" :status="progressStatus" /></div>
          </div>
        </el-card>

        <el-card shadow="never" style="margin-top: 16px" v-if="taskId">
          <template #header>
            <span>3. 结果下载</span>
          </template>
          <el-empty v-if="!files.length" description="尚未生成字幕文件" :image-size="60" />
          <div v-else class="files">
            <div v-for="f in files" :key="f.name" class="file">
              <el-icon><Document /></el-icon>
              <span class="name">{{ f.name }}</span>
              <span class="size">{{ formatSize(f.size) }}</span>
              <el-button text type="primary" @click="preview(f)">预览</el-button>
              <el-button text type="primary" @click="download(f)">下载</el-button>
              <el-button
                v-if="status === 'completed' && f.name.toLowerCase().endsWith('.srt')"
                text type="warning"
                @click="goReview"
              >校对</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="previewVisible" title="字幕预览" width="640px" top="6vh">
      <pre class="preview">{{ previewContent }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document } from '@element-plus/icons-vue'
import SubtitleAreaPicker from '@/components/AreaPickerDialog.vue'
import { extractApi } from '@/api/extract'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()

const meta = reactive({ languages: [], modes: [], subtitle_areas: [] })
const options = reactive({
  language: 'ch',
  mode: 'fast',
  subtitleArea: 2,
  extractFrequency: 3,
  thresholdTextSimilarity: 80,
  dropScore: 75,
  filterWatermark: false,
  filterSceneText: true,
  generateTxt: true,
  wordSegmentation: true,
  typoFix: true
})

const taskId = ref('')
const previewUrl = ref('')
const previewTime = ref(0)
const videoInfo = ref(null)
const videoName = ref('')
const durationMs = ref(0)
const uploadProgress = ref(0)
const area = ref(null)
const areaDialog = ref(false)
const paramsFlash = ref(false)
const logs = ref([])
const progress = reactive({ frame_extract: 0, ocr: 0, post: 0, overall: 0 })
const status = ref('pending')
const files = ref([])
const pollTimer = ref(null)
const logsRef = ref(null)

const running = computed(() => status.value === 'running')
const progressStatus = computed(() => (status.value === 'completed' ? 'success' : status.value === 'failed' ? 'exception' : undefined))
const currentMode = computed(() => meta.modes.find(m => m.code === options.mode))

function formatDuration(ms) {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}分${s % 60}秒`
}
function formatSize(bytes) {
  if (!bytes) return '0B'
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(2) + 'MB'
}

onMounted(async () => {
  await reloadMeta()
})

async function reloadMeta() {
  try {
    const data = await extractApi.meta()
    Object.assign(meta, data)
  } catch {}
}

async function handleUploadFile({ file, onProgress: up }) {
  if (!userStore.isDesktop && !userStore.isActive) {
    ElMessage.warning('账号未激活，请先激活')
    return
  }
  uploadProgress.value = 0
  try {
    const res = await extractApi.upload(file, e => {
      if (e.total) uploadProgress.value = Math.round((e.loaded / e.total) * 100)
    })
    taskId.value = res.task_id
    videoInfo.value = res.video_info
    videoName.value = res.video_name
    durationMs.value = res.duration_ms
    previewTime.value = 0
    logs.value = ['视频上传完成']
    files.value = []
    status.value = 'pending'
    area.value = null
    await loadPreview()
    ElMessage.success('视频上传成功，可框选字幕区域')
  } catch (e) {
    uploadProgress.value = 0
  }
}

// 预览图必须带 Authorization 头请求，所以取回 Blob 再转成 object URL
let previewObjectUrl = ''

async function loadPreview() {
  if (!taskId.value) return
  try {
    const blob = await extractApi.preview(taskId.value, previewTime.value)
    if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl)
    previewObjectUrl = URL.createObjectURL(blob)
    previewUrl.value = previewObjectUrl
  } catch (e) {
    previewUrl.value = ''
    ElMessage.error('预览帧加载失败：' + (e?.message || ''))
  }
}

async function reloadPreview() {
  await loadPreview()
}

/** 弹窗里确认区域后：写入选区，关闭弹窗，并把右侧参数区高亮一下引导继续设置 */
function onAreaConfirm(v) {
  area.value = v
  areaDialog.value = false
  paramsFlash.value = true
  window.setTimeout(() => { paramsFlash.value = false }, 1600)
  ElMessage.success('字幕区域已确定，接着设置识别参数后点「开始提取」')
}

function clearArea() {
  area.value = null
  ElMessage.info('已清除选区，将按全屏检测')
}

async function start() {
  if (!taskId.value) return
  try {
    await extractApi.start(taskId.value, { sub_area: area.value, options })
    status.value = 'running'
    logs.value = ['任务已开始...']
    startPolling()
  } catch {}
}

function startPolling() {
  stopPolling()
  pollTimer.value = setInterval(poll, 1000)
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function poll() {
  try {
    const s = await extractApi.status(taskId.value)
    Object.assign(progress, s.progress)
    status.value = s.status
    if (s.video_info && !videoInfo.value) videoInfo.value = s.video_info
    if (s.logs?.length) logs.value = s.logs
    if (s.error) logs.value.push('[错误] ' + s.error)
    await nextTick()
    if (logsRef.value) logsRef.value.scrollTop = logsRef.value.scrollHeight
    if (s.status === 'completed') {
      stopPolling()
      await loadFiles()
      ElMessage.success('字幕提取完成')
    } else if (s.status === 'failed' || s.status === 'cancelled') {
      stopPolling()
      ElMessage.warning(s.status === 'cancelled' ? '任务已取消' : '任务失败：' + (s.error || ''))
    }
  } catch {}
}

async function loadFiles() {
  const res = await extractApi.files(taskId.value)
  files.value = res.files
}

async function download(f) {
  try {
    const blob = await extractApi.download(taskId.value, f.name)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = f.name
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  } catch (e) {
    ElMessage.error('下载失败：' + (e?.message || ''))
  }
}

function goReview() {
  if (taskId.value) router.push(`/review/${taskId.value}`)
}

const previewVisible = ref(false)
const previewContent = ref('')
async function preview(f) {
  try {
    const res = await extractApi.content(taskId.value, f.name)
    previewContent.value = res.content
    previewVisible.value = true
  } catch {}
}

async function cancel() {
  await extractApi.cancel(taskId.value)
  status.value = 'cancelled'
  stopPolling()
}

function goActivate() {
  router.push('/activate')
}
function logout() {
  userStore.logout()
  router.push('/login')
}

onBeforeUnmount(() => {
  stopPolling()
  if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl)
})
</script>

<style scoped>
.home { padding: 16px 24px; min-height: 100%; background: var(--zm-bg); }
.header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px; padding: 12px 18px;
  background: var(--zm-bg-soft);
  border: 1px solid var(--zm-line);
  border-radius: 14px;
  box-shadow: var(--zm-shadow);
}
.brand { display: flex; align-items: center; gap: 10px; }
.logo {
  width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0;
  background: linear-gradient(135deg, #e6b455 0%, #d2952a 100%);
  color: #fff; font-size: 18px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(210, 149, 42, 0.28);
}
.title { font-size: 19px; font-weight: 700; color: var(--zm-text); letter-spacing: 1px; }
.actions { display: flex; align-items: center; gap: 10px; }
.user { font-size: 13px; color: var(--zm-text-dim); cursor: pointer; }
.user:hover { color: var(--zm-accent); }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.card-header > span:first-child { font-weight: 600; }
.tips { font-size: 12px; color: var(--zm-text-dim); font-weight: 400; }

/* ---------- 上传区：虚线暖色拖拽框 ---------- */
.upload-area { margin-bottom: 14px; }
.upload-area :deep(.el-upload) { width: 100%; }
.upload-area :deep(.el-upload-dragger) {
  border: 1.5px dashed var(--zm-accent-line);
  background: linear-gradient(180deg, #fffdf7 0%, #fff8e8 100%);
  border-radius: 12px;
  padding: 0;
  transition: border-color .2s, background .2s, box-shadow .2s;
}
.upload-area :deep(.el-upload-dragger:hover) {
  border-color: var(--zm-accent);
  background: linear-gradient(180deg, #fffaee 0%, #fff3d8 100%);
  box-shadow: inset 0 0 0 3px rgba(210, 149, 42, 0.06);
}
.upload-area :deep(.el-upload-dragger.is-dragover) {
  border-color: var(--zm-accent-strong);
  background: #fff2d4;
}
.upload-inner { padding: 22px 16px; text-align: center; }
.upload-badge {
  width: 52px; height: 52px; margin: 0 auto 10px; border-radius: 14px;
  background: var(--zm-accent-soft); color: var(--zm-accent);
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--zm-accent-line);
}
.upload-main { font-size: 14px; font-weight: 600; color: var(--zm-text); }
.sub { font-size: 12px; color: var(--zm-text-dim); margin-top: 6px; }

.video-meta { margin-bottom: 12px; }
.selector { margin-top: 12px; }

/* 字幕区域卡片 */
.card-head { display: flex; align-items: center; gap: 8px; }
.card-head .el-tag { margin-left: auto; }
.area-row { display: flex; align-items: center; gap: 16px; }
.area-info { flex: 1; min-width: 0; }
.area-main { font-size: 13px; color: var(--zm-text); font-weight: 600; }
.area-sub { font-size: 12px; color: var(--zm-text-dim); margin-top: 3px; line-height: 1.5; }
.area-btns { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }

/* 选区确定后高亮参数面板，引导下一步 */
.params-card.flash {
  animation: params-flash 1.6s ease-out;
}
@keyframes params-flash {
  0% { box-shadow: 0 0 0 0 rgba(210, 149, 42, 0.55); }
  30% { box-shadow: 0 0 0 4px rgba(210, 149, 42, 0.35); }
  100% { box-shadow: 0 0 0 0 rgba(210, 149, 42, 0); }
}

.hint { font-size: 12px; color: var(--zm-text-dim); margin-top: 2px; line-height: 1.4; }
.run-box { display: flex; gap: 8px; margin: 16px 0 8px; }
.progress-box { margin-top: 8px; }
.p-item { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; font-size: 12px; color: var(--zm-text-dim); }
.p-item span { width: 70px; }
.p-item :deep(.el-progress) { flex: 1; }
.p-item.total { font-weight: 600; color: var(--zm-text); }

/* 日志面板改成浅色，贴合淡黄主题 */
.logs {
  height: 300px; overflow-y: auto;
  background: #fffdf7; color: #6b5f4c;
  border: 1px solid var(--zm-line); border-radius: 10px;
  font-family: Consolas, 'Courier New', monospace; font-size: 12px;
  padding: 12px; line-height: 1.7;
}

.files .file {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 4px; border-bottom: 1px dashed var(--zm-line); font-size: 13px;
}
.files .file:last-child { border-bottom: none; }
.files .name { flex: 1; color: var(--zm-text); }
.files .size { color: var(--zm-text-dim); font-size: 12px; }
.preview {
  max-height: 50vh; overflow: auto; background: #fffdf7;
  border: 1px solid var(--zm-line); border-radius: 10px;
  padding: 12px; font-size: 13px; line-height: 1.7; white-space: pre-wrap;
}
</style>
