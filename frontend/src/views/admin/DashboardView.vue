<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="6" v-for="s in statCards" :key="s.label">
        <el-card shadow="hover">
          <div class="stat">
            <div class="label">{{ s.label }}</div>
            <div class="value" :style="{ color: s.color }">{{ s.value }}</div>
            <div class="desc">{{ s.desc }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>最近注册用户</span></template>
          <el-table :data="data.recent_users" size="small">
            <el-table-column prop="email" label="邮箱" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="注册时间" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>最近提取任务</span></template>
          <el-table :data="data.recent_tasks" size="small">
            <el-table-column prop="video_name" label="视频" />
            <el-table-column prop="email" label="用户" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="taskType(row.status)">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { adminApi } from '@/api/admin'

const data = reactive({ users: {}, codes: {}, tasks: {}, recent_users: [], recent_tasks: [] })
const cards = ref([])

const statCards = [
  { label: '注册用户', key: 'users', value: 0, color: '#d2952a' },
  { label: '已激活', key: 'active', value: 0, color: '#7fa650' },
  { label: '待激活', key: 'pending', value: 0, color: '#e0a02a' },
  { label: '激活码剩余', key: 'unused', value: 0, color: '#d1604a' }
]

function statusText(s) {
  return { active: '已激活', pending: '待激活', disabled: '已禁用' }[s] || s
}
function statusType(s) {
  return { active: 'success', pending: 'warning', disabled: 'info' }[s] || 'info'
}
function taskType(s) {
  return { completed: 'success', running: 'warning', failed: 'danger', cancelled: 'info', pending: 'info' }[s] || 'info'
}
function formatTime(t) {
  return t ? new Date(t * 1000).toLocaleString() : '-'
}

onMounted(async () => {
  const res = await adminApi.dashboard()
  Object.assign(data, res)
  statCards[0].value = res.users.total
  statCards[1].value = res.users.active
  statCards[2].value = res.users.pending
  statCards[3].value = res.codes.unused
})
</script>

<style scoped>
.stat { text-align: center; padding: 8px 0; }
.stat .label { font-size: 12px; color: #909399; }
.stat .value { font-size: 28px; font-weight: 600; margin: 6px 0 2px; }
.stat .desc { font-size: 12px; color: #c0c4cc; }
</style>
