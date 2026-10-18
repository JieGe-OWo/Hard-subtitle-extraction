<template>
  <div>
    <el-card shadow="never">
      <template #header>
        <div class="head">
          <span>用户管理</span>
          <div class="filters">
            <el-radio-group v-model="filterStatus" size="small" @change="load">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button value="active">已激活</el-radio-button>
              <el-radio-button value="pending">待激活</el-radio-button>
              <el-radio-button value="disabled">已禁用</el-radio-button>
            </el-radio-group>
            <el-input v-model="keyword" placeholder="搜索邮箱" size="small" clearable style="width: 200px" @input="load">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </div>
        </div>
      </template>

      <el-table :data="rows" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="激活时间" width="170">
          <template #default="{ row }">{{ row.activated_at ? formatTime(row.activated_at) : '-' }}</template>
        </el-table-column>
        <el-table-column label="最近登录" width="170">
          <template #default="{ row }">{{ row.last_login_at ? formatTime(row.last_login_at) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status !== 'active'" size="small" text type="success" @click="setStatus(row, 'active')">激活</el-button>
            <el-button v-if="row.status !== 'disabled'" size="small" text type="danger" @click="setStatus(row, 'disabled')">禁用</el-button>
            <el-button v-if="row.status === 'disabled'" size="small" text type="warning" @click="setStatus(row, 'pending')">恢复</el-button>
          </template>
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
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '@/api/admin'

const rows = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(15)
const total = ref(0)
const keyword = ref('')
const filterStatus = ref('all')

function statusText(s) {
  return { active: '已激活', pending: '待激活', disabled: '已禁用' }[s] || s
}
function statusType(s) {
  return { active: 'success', pending: 'warning', disabled: 'info' }[s] || 'info'
}
function formatTime(t) {
  return t ? new Date(t * 1000).toLocaleString() : '-'
}

async function load() {
  loading.value = true
  try {
    const res = await adminApi.users({
      keyword: keyword.value,
      status: filterStatus.value,
      page: page.value,
      page_size: pageSize.value
    })
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function setStatus(row, status) {
  await adminApi.updateUser(row.id, { status })
  ElMessage.success('已更新')
  await load()
}

onMounted(load)
</script>

<style scoped>
.head { display: flex; align-items: center; justify-content: space-between; }
.filters { display: flex; align-items: center; gap: 12px; }
.pager { margin-top: 14px; display: flex; justify-content: flex-end; }
</style>
