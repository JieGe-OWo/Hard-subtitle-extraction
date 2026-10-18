<template>
  <el-dialog
    v-model="visible"
    title="框选字幕区域"
    :width="dialogWidth + 'px'"
    align-center
    destroy-on-close
    :close-on-click-modal="false"
    class="area-dialog"
    @opened="layout"
  >
    <div class="body">
      <div class="stage" :style="{ width: stageW + 'px', height: stageH + 'px' }">
        <div class="frame" :style="{ width: imgW + 'px', height: imgH + 'px' }">
          <img
            v-if="imageUrl"
            ref="imgRef"
            :src="imageUrl"
            alt="预览帧"
            draggable="false"
            @load="onLoad"
          />
          <div
            v-if="rect.visible"
            class="sel"
            :style="selStyle"
          >
            <span class="sel-size">{{ selectionSize }}</span>
          </div>
          <div v-if="!imageUrl" class="loading">预览帧加载中…</div>
        </div>

        <!-- 鼠标操作层，盖在画面上，保证拖拽不被图片影响 -->
        <div
          class="overlay"
          @mousedown="onDown"
          @mousemove="onMove"
          @mouseup="onUp"
          @mouseleave="onUp"
        ></div>
      </div>

      <div class="footer-tips">
        <span class="coord">
          {{ draft ? `已选：x ${draft.xmin} ~ ${draft.xmax} ｜ y ${draft.ymin} ~ ${draft.ymax}（视频像素）` : '在画面上按住左键拖拽，框出字幕所在区域' }}
        </span>
        <span class="hint">提示：上下留一点余量，别贴着文字边缘，否则 OCR 容易读不完整</span>
      </div>
    </div>

    <template #footer>
      <div class="actions">
        <el-button text :disabled="!draft" @click="reset">清除选区</el-button>
        <span class="spacer"></span>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :disabled="!draft" @click="confirm">确定，用它识别</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  imageUrl: { type: String, default: '' },
  frameWidth: { type: Number, default: 0 },
  frameHeight: { type: Number, default: 0 },
  initial: { type: Object, default: null }
})
const emit = defineEmits(['update:modelValue', 'confirm'])

const visible = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v)
})

const imgRef = ref()
const stageW = ref(880)
const stageH = ref(500)
const imgW = ref(880)
const imgH = ref(500)
const dialogWidth = computed(() => stageW.value + 44)

const rect = reactive({ visible: false, left: 0, top: 0, width: 0, height: 0 })
const draft = ref(null)
const drawing = ref(false)
const start = { x: 0, y: 0 }
let scale = 1

const selStyle = computed(() => ({
  left: `${rect.left}px`,
  top: `${rect.top}px`,
  width: `${rect.width}px`,
  height: `${rect.height}px`
}))
const selectionSize = computed(() =>
  draft.value ? `${draft.value.xmax - draft.value.xmin}×${draft.value.ymax - draft.value.ymin}` : ''
)

/** 弹窗尺寸只跟窗口大小有关，不随视频分辨率变化；视频按比例缩放到画布内 */
function layout() {
  const vw = window.innerWidth
  const vh = window.innerHeight
  stageW.value = Math.max(360, Math.min(900, vw - 160))
  stageH.value = Math.max(240, Math.min(520, vh - 300))
  const nw = props.frameWidth || 16
  const nh = props.frameHeight || 9
  scale = Math.min(stageW.value / nw, stageH.value / nh)
  imgW.value = Math.max(1, Math.round(nw * scale))
  imgH.value = Math.max(1, Math.round(nh * scale))
  rect.visible = false
  draft.value = null
  if (props.initial) {
    const a = props.initial
    draft.value = { ...a }
    rect.visible = true
    rect.left = a.xmin * scale
    rect.top = a.ymin * scale
    rect.width = (a.xmax - a.xmin) * scale
    rect.height = (a.ymax - a.ymin) * scale
  }
}

function onLoad() {
  if (props.frameWidth && props.frameHeight) return
  // 后端没给分辨率时用图片原始尺寸兜底
  const el = imgRef.value
  if (el && el.naturalWidth) {
    const nw = el.naturalWidth
    const nh = el.naturalHeight
    scale = Math.min(stageW.value / nw, stageH.value / nh)
    imgW.value = Math.round(nw * scale)
    imgH.value = Math.round(nh * scale)
  }
}

function localPoint(e) {
  const box = imgRef.value ? imgRef.value.getBoundingClientRect() : null
  if (!box) return { x: 0, y: 0 }
  return {
    x: Math.min(Math.max(e.clientX - box.left, 0), box.width),
    y: Math.min(Math.max(e.clientY - box.top, 0), box.height)
  }
}

function onDown(e) {
  if (e.button !== 0 || !imgRef.value) return
  e.preventDefault()
  const p = localPoint(e)
  start.x = p.x
  start.y = p.y
  drawing.value = true
  rect.visible = true
  rect.left = p.x
  rect.top = p.y
  rect.width = 0
  rect.height = 0
  draft.value = null
}

function onMove(e) {
  if (!drawing.value) return
  const p = localPoint(e)
  rect.left = Math.min(start.x, p.x)
  rect.top = Math.min(start.y, p.y)
  rect.width = Math.abs(p.x - start.x)
  rect.height = Math.abs(p.y - start.y)
}

function onUp() {
  if (!drawing.value) return
  drawing.value = false
  if (rect.width < 6 || rect.height < 6) {
    rect.visible = false
    draft.value = null
    return
  }
  // CSS 像素 -> 视频像素
  draft.value = {
    xmin: Math.round(rect.left / scale),
    xmax: Math.round((rect.left + rect.width) / scale),
    ymin: Math.round(rect.top / scale),
    ymax: Math.round((rect.top + rect.height) / scale)
  }
}

function reset() {
  rect.visible = false
  rect.width = 0
  rect.height = 0
  draft.value = null
}

function confirm() {
  if (!draft.value) return
  emit('confirm', { ...draft.value })
  visible.value = false
}

watch(
  () => props.modelValue,
  v => {
    if (v) requestAnimationFrame(layout)
  }
)
</script>

<style scoped>
.body { display: flex; flex-direction: column; gap: 10px; }

/* 画布：淡色格纹底，尺寸固定（由 layout 按窗口大小算），内部不滚动 */
.stage {
  position: relative;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
  border-radius: 10px;
  border: 1px solid var(--zm-line);
  background:
    linear-gradient(45deg, #f6efdc 25%, transparent 25%) -8px 0/16px 16px,
    linear-gradient(-45deg, #f6efdc 25%, transparent 25%) -8px 0/16px 16px,
    linear-gradient(45deg, transparent 75%, #f6efdc 75%) 0 0/16px 16px,
    linear-gradient(-45deg, transparent 75%, #f6efdc 75%) 0 0/16px 16px,
    #fffdf7;
}
.frame { position: relative; line-height: 0; box-shadow: 0 8px 24px rgba(120, 96, 40, 0.22); }
.frame img { width: 100%; height: 100%; display: block; user-select: none; -webkit-user-drag: none; }

.overlay { position: absolute; inset: 0; cursor: crosshair; }

.sel {
  position: absolute; pointer-events: none; box-sizing: border-box;
  border: 2px dashed #ff7a45;
  background: rgba(255, 122, 69, 0.18);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.65), 0 0 14px rgba(255, 122, 69, 0.4);
}
.sel-size {
  position: absolute; right: 4px; bottom: 2px;
  font-size: 11px; color: #fff; background: rgba(255, 122, 69, 0.9);
  padding: 0 4px; border-radius: 3px; line-height: 16px;
}
.loading { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: var(--zm-text-dim); }

.footer-tips { display: flex; flex-direction: column; gap: 2px; }
.coord { font-size: 12px; color: var(--zm-text); }
.hint { font-size: 12px; color: var(--zm-text-dim); }

.actions { display: flex; align-items: center; }
.spacer { flex: 1; }
</style>

<style>
/* 弹窗本体：固定尺寸、居中，绝不超出视口 */
.area-dialog.el-dialog {
  margin: 0 auto !important;
  max-width: calc(100vw - 24px);
  max-height: calc(100vh - 24px);
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  overflow: hidden;
}
.area-dialog .el-dialog__body {
  padding: 12px 22px 6px;
  overflow: hidden;
}
.area-dialog .el-dialog__header { padding: 14px 22px 6px; }
.area-dialog .el-dialog__footer { padding: 6px 22px 14px; }
</style>
