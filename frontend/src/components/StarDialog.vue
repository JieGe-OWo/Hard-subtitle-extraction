<template>
  <el-dialog
    v-model="visible"
    width="520px"
    align-center
    :close-on-click-modal="true"
    :show-close="true"
    class="star-dialog"
  >
    <div class="box">
      <div class="icon">⭐</div>
      <div class="title">用着还行？帮点个 Star 吧</div>
      <div class="desc">
        这个工具是个人业余开发的，纯本地离线、免费使用。<br />
        点个 Star 就是最大的支持，后续更新也会第一时间发布在这两个仓库。
      </div>

      <div class="repos">
        <button
          v-for="r in REPOS"
          :key="r.key"
          class="repo-btn"
          :style="{ '--brand': r.color }"
          @click="goStar(r)"
        >
          <span class="repo-name">{{ r.name }}</span>
          <span class="repo-star">Star ⭐</span>
        </button>
      </div>

      <div class="foot">
        <el-button text size="small" @click="onNever">不再提示</el-button>
        <span class="spacer"></span>
        <el-button size="small" @click="onSnooze">稍后再说</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { REPOS } from '@/config/repos'
import { starVisible, snoozeStar, neverStar } from '@/composables/useStarDialog'

const visible = computed({
  get: () => starVisible.value,
  set: v => { starVisible.value = v }
})

function goStar(repo) {
  window.open(repo.starUrl, '_blank', 'noopener')
  ElMessage.success(`已打开 ${repo.name}，点右上角 Star ⭐ 就行`)
}

function onSnooze() {
  snoozeStar()
}

function onNever() {
  neverStar()
  ElMessage.info('好的，之后不再自动提醒（顶栏 ⭐ 仍可随时打开）')
}
</script>

<style scoped>
.box { text-align: center; }
.icon { font-size: 40px; line-height: 1.1; }
.title { font-size: 18px; font-weight: 700; color: var(--zm-text); margin-top: 6px; }
.desc {
  font-size: 13px; color: var(--zm-text-dim); line-height: 1.8;
  margin: 10px 6px 16px;
}

.repos { display: flex; gap: 10px; }
.repo-btn {
  flex: 1;
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--zm-line);
  background: linear-gradient(180deg, #fffdf7, #fdf4e2);
  cursor: pointer;
  transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
}
.repo-btn:hover {
  transform: translateY(-1px);
  border-color: var(--brand);
  box-shadow: 0 6px 18px rgba(120, 96, 40, 0.18);
}
.repo-name { font-size: 14px; font-weight: 700; color: var(--brand); }
.repo-star { font-size: 12px; color: var(--zm-text-dim); }

.foot { display: flex; align-items: center; margin-top: 16px; }
.spacer { flex: 1; }
</style>

<style>
.star-dialog.el-dialog {
  max-width: calc(100vw - 24px);
  border-radius: 16px;
}
.star-dialog .el-dialog__header { padding: 10px 16px 0; }
.star-dialog .el-dialog__body { padding: 6px 22px 18px; }
</style>
