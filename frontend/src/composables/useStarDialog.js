import { ref } from 'vue'

/** Star 弹窗的可见状态（模块级单例，任何地方都能打开它） */
export const starVisible = ref(false)

export function openStarDialog() {
  starVisible.value = true
}

export function closeStarDialog() {
  starVisible.value = false
}

/**
 * 每次进入页面都弹一次（不做本地记忆）。
 * 软件重启后打开页面会再弹；页面刷新也会再弹。
 * 顶栏的「⭐ Star」按钮可以随时手动打开同一个弹窗。
 */
export function maybeAutoShowStar() {
  window.setTimeout(() => {
    starVisible.value = true
  }, 800)
}
