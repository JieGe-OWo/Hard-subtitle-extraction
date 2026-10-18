<template>
  <el-card shadow="never">
    <template #header><span>全部提取任务</span></template>
    <el-table :data="rows" size="small" v-loading="loading">
      <el-table-column prop="id" label="任务ID" width="200">
        <template #default="{ row }"><span class="id">{{ row.id }}</span></template>
      </el-table-column>
      <el-table-column prop="email" label="用户" />
      <el-table-column prop="video_name" label="视频" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="taskType(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="帧/OCR/后处理" width="190">
        <template #default="{ row }">{{ Math.round(row.progress_frame) }}% / {{ Math.round(row.progress_ocr) }}% / {{ Math.round(row.progress_post) }}%</template>
      </el-table-column>
      <el-table-column prop="error" label="错误" />
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="p => { page = p; load() }"
      />
    </div>
  </el-card>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { adminApi } from '@/api/admin'

const rows = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(15)
const total = ref(0)

function taskType(s) {
  return { completed: 'success', running: 'warning', failed: 'danger', cancelled: 'info', pending: 'info' }[s] || 'info'
}
function formatTime(t) {
  return t ? new Date(t * 1000).toLocaleString() : '-'
}

async function load() {
  loading.value = true
  try {
    const res = await adminApi.tasks({ page: page.value, page_size: pageSize.value })
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.id { font-family: Consolas, monospace; font-size: 12px; color: #606266; }
.pager { margin-top: 14px; display: flex; justify-content: flex-end; }
</style>
