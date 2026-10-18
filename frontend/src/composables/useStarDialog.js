import { ref } from 'vue'

/** Star 弹窗的可见状态（模块级单例，任何地方都能打开它） */
export const starVisible = ref(false)

const STORAGE_KEY = 'zimu_star_state'
const ONE_DAY = 24 * 60 * 60 * 1000

function readState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') || {}
  } catch {
    return {}
  }
}

function writeState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    /* 隐私模式下存不了，忽略即可 */
  }
}

export function openStarDialog() {
  starVisible.value = true
}

export function closeStarDialog() {
  starVisible.value = false
}

/** 点「稍后再说」：一天内不再自动弹 */
export function snoozeStar() {
  const s = readState()
  writeState({ ...s, nextAt: Date.now() + ONE_DAY })
  closeStarDialog()
}

/** 点「不再提示」：永久不再自动弹（顶部 ⭐ 仍可手动打开） */
export function neverStar() {
  const s = readState()
  writeState({ ...s, never: true })
  closeStarDialog()
}

/**
 * 页面打开时调用：首次访问自动弹一次；
 * 「稍后再说」后隔一天再提醒；「不再提示」后不再自动出现。
 */
export function maybeAutoShowStar() {
  const s = readState()
  if (s.never) return
  if (s.nextAt && Date.now() < s.nextAt) return
  window.setTimeout(() => {
    starVisible.value = true
  }, 1200)
}
