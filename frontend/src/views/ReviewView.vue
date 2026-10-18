<template>
  <div class="review">
    <header class="top">
      <el-button size="small" @click="back">← 返回</el-button>
      <span class="title">字幕校对 · {{ videoName }}</span>
      <div class="actions">
        <el-button type="primary" size="small" :loading="saving" @click="save">保存修改</el-button>
        <el-button size="small" @click="exportFile('.srt')">导出 SRT</el-button>
        <el-button size="small" @click="exportFile('.txt')">导出 TXT</el-button>
      </div>
    </header>

    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon style="margin-bottom: 12px" />

    <div class="main">
      <div class="player">
        <video
          ref="videoRef"
          controls
          preload="auto"
          playsinline
          :src="videoSrc"
          :poster="posterUrl"
          @timeupdate="onTimeUpdate"
          @seeked="onTimeUpdate"
          @error="onVideoError"
          @loadeddata="videoLoading = false"
        ></video>

        <!-- 视频下方的字幕条：跟着播放时间实时显示当前这句 -->
        <div class="caption" :class="{ empty: !activeSub }">
          <div class="cap-text">{{ activeSub ? (activeSub.text || '（这句是空的）') : '（当前时间没有字幕）' }}</div>
          <div class="cap-time">
            <template v-if="activeSub">{{ activeSub.start }} → {{ activeSub.end }}</template>
            <template v-else>{{ currentTimeText }}</template>
          </div>
        </div>

        <el-alert v-if="videoError" :title="videoError" type="warning" :closable="false" show-icon style="margin-top: 8px" />
        <div class="hint">
          边播边看：拖动视频进度条，上方字幕条和右侧列表会同步高亮；点任意一行可跳转到对应时间；
          <b>双击某行文字即可直接修改</b>（回车或点空白处结束编辑），全部改完点「保存修改」，再导出 SRT/TXT。
        </div>
      </div>

      <div class="list" ref="listRef">
        <div
          v-for="(s, i) in subs"
          :key="i"
          class="row"
          :class="{ active: i === activeIdx, dirty: dirtySet.has(i) }"
          :title="editingIdx === i ? '' : '单击跳转 · 双击编辑'"
          @click="seekTo(i)"
          @dblclick="startEdit(i)"
        >
          <span class="time">{{ s.start }} → {{ s.end }}</span>
          <el-input
            v-if="editingIdx === i"
            :ref="el => setEditRef(el, i)"
            v-model="s.text"
            size="small"
            @keyup.enter="stopEdit(i)"
            @blur="stopEdit(i)"
            @click.stop
            @dblclick.stop
          />
          <template v-else>
            <span class="text">{{ s.text || '（空）' }}</span>
            <el-button text size="small" class="edit-btn" @click.stop="startEdit(i)">编辑</el-button>
          </template>
        </div>
        <el-empty v-if="!subs.length && !error" description="暂无可校对的字幕" :image-size="60" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { extractApi } from '@/api/extract'
import { timeToSec } from '@/utils/srt'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId

const videoName = ref('')
const videoSrc = ref('')
const posterUrl = ref('')
const videoError = ref('')
const videoLoading = ref(true)
let videoObjectUrl = ''
let posterObjectUrl = ''
let usedBlobFallback = false
const videoRef = ref()
const listRef = ref()
const subs = ref([]) // {index,start,end,text,_startSec,_endSec,_original}
const activeIdx = ref(-1)
const editingIdx = ref(-1)
const dirtySet = ref(new Set())
const saving = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    const data = await extractApi.subtitles(taskId)
    videoName.value = data.video_name || ''
    videoSrc.value = extractApi.videoUrl(taskId)
    subs.value = (data.subtitles || []).map(s => ({
      ...s,
      _startSec: timeToSec(s.start),
      _endSec: timeToSec(s.end),
      _original: s.text
    }))
    // 首帧封面：没有它，播放器在按下播放前是一块黑，看起来像"视频没出来"
    loadPoster()
  } catch (e) {
    error.value = '加载失败：' + (e?.message || '任务不存在（服务重启后任务会失效，请重新提取）')
  }
})

async function loadPoster() {
  try {
    const blob = await extractApi.preview(taskId, 0)
    if (posterObjectUrl) URL.revokeObjectURL(posterObjectUrl)
    posterObjectUrl = URL.createObjectURL(blob)
    posterUrl.value = posterObjectUrl
  } catch (e) {
    // 封面失败不影响播放
  }
}

/** 直链播放失败（鉴权/编码/范围请求等原因）时，退回"带鉴权头取整段视频再播" */
async function onVideoError() {
  if (usedBlobFallback) {
    videoError.value = '视频加载失败：可能是文件已被清理或格式不受浏览器支持。可到「我的任务」重新提取后校对。'
    return
  }
  usedBlobFallback = true
  videoLoading.value = true
  try {
    const blob = await extractApi.videoBlob(taskId)
    if (videoObjectUrl) URL.revokeObjectURL(videoObjectUrl)
    videoObjectUrl = URL.createObjectURL(blob)
    videoSrc.value = videoObjectUrl
    videoError.value = ''
    await nextTick()
    videoRef.value?.load()
  } catch (e) {
    videoError.value = '视频加载失败：' + (e?.message || '未知原因')
  } finally {
    videoLoading.value = false
  }
}

const activeSub = computed(() => subs.value[activeIdx.value] || null)
const currentTimeText = computed(() => {
  const t = videoRef.value?.currentTime ?? 0
  const m = Math.floor(t / 60)
  const s = Math.floor(t % 60)
  return `播放到 ${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

onBeforeUnmount(() => {
  if (videoObjectUrl) URL.revokeObjectURL(videoObjectUrl)
  if (posterObjectUrl) URL.revokeObjectURL(posterObjectUrl)
})

function onTimeUpdate() {
  const t = videoRef.value?.currentTime ?? 0
  let idx = -1
  for (let i = 0; i < subs.value.length; i++) {
    const s = subs.value[i]
    if (t >= s._startSec && t < s._endSec) {
      idx = i
      break
    }
  }
  if (idx !== activeIdx.value) {
    activeIdx.value = idx
    scrollActive()
  }
}

function scrollActive() {
  const idx = activeIdx.value
  if (idx < 0) return
  const el = listRef.value?.children[idx]
  if (el?.scrollIntoView) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
}

function seekTo(i) {
  const v = videoRef.value
  if (!v) return
  v.currentTime = subs.value[i]._startSec + 0.01
  v.play().catch(() => {})
}

// 正在编辑的输入框引用，用于进入编辑后自动聚焦
let editRef = null

function setEditRef(el, i) {
  if (i === editingIdx.value && el) editRef = el
}

function startEdit(i) {
  if (editingIdx.value === i) return
  editingIdx.value = i
  // 双击进入编辑后自动聚焦并全选，方便直接改字
  nextTick(() => {
    editRef?.focus?.()
    editRef?.select?.()
  })
}

function stopEdit(i) {
  if (editingIdx.value !== i) return
  editingIdx.value = -1
  const s = subs.value[i]
  if ((s.text || '') !== (s._original || '')) {
    const next = new Set(dirtySet.value)
    next.add(i)
    dirtySet.value = next
  }
}

async function save() {
  saving.value = true
  try {
    const payload = subs.value.map((s, i) => ({
      index: i + 1,
      start: s.start,
      end: s.end,
      text: s.text
    }))
    await extractApi.saveSubtitles(taskId, payload)
    subs.value.forEach(s => { s._original = s.text })
    dirtySet.value = new Set()
    ElMessage.success('修改已写回 SRT/TXT')
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || ''))
  } finally {
    saving.value = false
  }
}

function triggerDownload(blob, name) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

async function exportFile(suffix) {
  try {
    const res = await extractApi.files(taskId)
    const f = res.files.find(x => x.name.toLowerCase().endsWith(suffix))
    if (!f) {
      ElMessage.warning(suffix === '.txt'
        ? '还没有 TXT 文件：点一次「保存修改」会自动生成'
        : '还没有 SRT 文件')
      return
    }
    const blob = await extractApi.download(taskId, f.name)
    triggerDownload(blob, f.name)
  } catch (e) {
    ElMessage.error('导出失败：' + (e?.message || ''))
  }
}

function back() {
  router.push('/')
}
</script>

<style scoped>
.review { padding: 16px 24px; min-height: 100%; background: var(--zm-bg); }
.top {
  display: flex; align-items: center; gap: 12px; margin-bottom: 12px;
  padding: 10px 16px;
  background: var(--zm-bg-soft);
  border: 1px solid var(--zm-line); border-radius: 14px;
  box-shadow: var(--zm-shadow);
}
.top .title { font-size: 16px; font-weight: 700; flex: 1; color: var(--zm-text); }
.main { display: flex; gap: 16px; align-items: flex-start; }
.player { flex: 1.2; min-width: 0; }
.player video {
  width: 100%; height: auto; max-height: 56vh;
  object-fit: contain;
  background: #1f1a13; border-radius: 12px;
  box-shadow: var(--zm-shadow);
}
.hint { font-size: 12px; color: var(--zm-text-dim); margin-top: 8px; line-height: 1.7; }
.hint b { color: var(--zm-accent-strong); }

/* 视频下方的字幕条：跟着播放时间走，用来和画面里的硬字幕对照 */
.caption {
  margin-top: 10px;
  min-height: 78px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 12px;
  border: 1px solid var(--zm-line);
  background: linear-gradient(180deg, #fffdf7, #fdf5e3);
  box-shadow: var(--zm-shadow);
  text-align: center;
}
.caption.empty { background: #fffdf7; }
.cap-text {
  font-size: 20px; line-height: 1.5; font-weight: 700;
  color: #3d3428;
  letter-spacing: .5px;
  text-shadow: 0 1px 0 #fff;
}
.caption.empty .cap-text { font-size: 14px; font-weight: 400; color: var(--zm-text-dim); }
.cap-time { font-size: 12px; color: var(--zm-text-dim); font-family: Consolas, monospace; }

.list {
  flex: 1; max-height: 560px; overflow-y: auto;
  border: 1px solid var(--zm-line); border-radius: 12px;
  background: var(--zm-card); box-shadow: var(--zm-shadow);
}
.row {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 12px;
  border-bottom: 1px dashed var(--zm-line);
  cursor: pointer; transition: background .15s;
}
.row:last-child { border-bottom: none; }
.row:hover { background: #fffaf0; }
.row.active { background: var(--zm-accent-soft); box-shadow: inset 3px 0 0 var(--zm-accent); }
.row.dirty .text { color: var(--zm-accent-strong); font-weight: 600; }
.time { font-size: 11px; color: var(--zm-text-dim); white-space: nowrap; font-family: Consolas, monospace; }
.text { flex: 1; font-size: 13px; color: var(--zm-text); }
.edit-btn { flex-shrink: 0; }
</style>
