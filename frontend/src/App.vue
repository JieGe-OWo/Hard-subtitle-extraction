<template>
  <router-view />
  <star-dialog />
</template>

<script setup>
import { onMounted } from 'vue'
import { useUserStore } from './store/user'
import StarDialog from '@/components/StarDialog.vue'
import { maybeAutoShowStar } from '@/composables/useStarDialog'

const userStore = useUserStore()
onMounted(() => {
  if (userStore.token && !userStore.user) {
    userStore.fetchMe().catch(() => userStore.logout())
  }
  // 打开页面时（首次访问）弹一次「点个 Star」提示
  maybeAutoShowStar()
})
</script>

<style>
/* 基础样式在 styles/theme.css 里统一维护（淡黄简约主题），这里只兜底字体与盒模型 */
html,
body,
#app {
  margin: 0;
  height: 100%;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
  background: var(--zm-bg, #fffbef);
  color: var(--zm-text, #4a4034);
}
*{box-sizing:border-box}
</style>
