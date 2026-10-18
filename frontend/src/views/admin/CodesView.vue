<template>
  <div>
    <el-card shadow="never">
      <template #header>
        <div class="head">
          <span>激活码管理</span>
          <div class="btns">
            <el-button type="primary" @click="genVisible = true">批量生成</el-button>
            <el-button @click="customVisible = true">手动添加</el-button>
          </div>
        </div>
      </template>

      <div class="filters">
        <el-radio-group v-model="filterStatus" size="small" @change="load">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="unused">未使用</el-radio-button>
          <el-radio-button value="used">已使用</el-radio-button>
          <el-radio-button value="expired">已过期</el-radio-button>
          <el-radio-button value="disabled">已停用</el-radio-button>
        </el-radio-group>
        <el-input v-model="keyword" placeholder="搜索激活码 / 备注" size="small" clearable style="width: 220px" @input="load" @clear="load">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>

      <el-table :data="rows" size="small" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="code" label="激活码">
          <template #default="{ row }">
            <span class="code">{{ row.code }}</span>
            <el-button text type="primary" size="small" @click="copy(row.code)">复制</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="备注" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="rowTag(row)">{{ rowText(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="被谁使用" width="170">
          <template #default="{ row }">{{ row.used_email || '-' }}</template>
        </el-table-column>
        <el-table-column label="使用/过期时间" width="180">
          <template #default="{ row }">
            {{ row.used_at ? '使用: ' + formatTime(row.used_at) : row.expires_at ? '过期: ' + formatTime(row.expires_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text :type="row.enabled ? 'warning' : 'success'" @click="toggle(row)">
              {{ row.enabled ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" text type="primary" @click="extend(row)">续期</el-button>
            <el-button size="small" text type="danger" :disabled="!!row.used_by" @click="remove(row)">删除</el-button>
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

    <el-dialog v-model="genVisible" title="批量生成激活码" width="440px">
      <el-form label-width="110px">
        <el-form-item label="生成数量">
          <el-input-number v-model="genForm.count" :min="1" :max="500" />
        </el-form-item>
        <el-form-item label="有效天数">
          <el-input-number v-model="genForm.expires_in_days" :min="1" :max="3650" />
        </el-form-item>
        <el-form-item label="前缀">
          <el-input v-model="genForm.prefix" placeholder="可选，如 ZM-" clearable />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="genForm.note" placeholder="可选，如 2026 年第一批" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="genLoading" @click="doGenerate">生成</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="customVisible" title="手动添加激活码" width="440px">
      <el-form label-width="110px">
        <el-form-item label="激活码">
          <el-input v-model="customForm.code" placeholder="直接写入，4-64 位" />
        </el-form-item>
        <el-form-item label="有效天数">
          <el-input-number v-model="customForm.expires_in_days" :min="1" :max="3650" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="customForm.note" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="customVisible = false">取消</el-button>
        <el-button type="primary" @click="doCustom">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '@/api/admin'

const rows = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(15)
const total = ref(0)
const keyword = ref('')
const filterStatus = ref('unused')

const genVisible = ref(false)
const genLoading = ref(false)
const genForm = reactive({ count: 10, note: '', expires_in_days: 30, prefix: '' })

const customVisible = ref(false)
const customForm = reactive({ code: '', note: '', expires_in_days: 30 })

function rowTag(r) {
  if (!r.enabled) return 'info'
  if (r.used_by) return 'success'
  if (r.expires_at && r.expires_at * 1000 < Date.now()) return 'danger'
  return 'primary'
}
function rowText(r) {
  if (!r.enabled) return '已停用'
  if (r.used_by) return '已使用'
  if (r.expires_at && r.expires_at * 1000 < Date.now()) return '已过期'
  return '可用'
}
function formatTime(t) {
  return t ? new Date(t * 1000).toLocaleString() : '-'
}
async function copy(code) {
  try {
    await navigator.clipboard.writeText(code)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选中')
  }
}

async function load() {
  loading.value = true
  try {
    const res = await adminApi.codes({
      status: filterStatus.value,
      keyword: keyword.value,
      page: page.value,
      page_size: pageSize.value
    })
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function doGenerate() {
  genLoading.value = true
  try {
    await adminApi.generateCodes(genForm)
    ElMessage.success('生成成功')
    genVisible.value = false
    await load()
  } finally {
    genLoading.value = false
  }
}

async function doCustom() {
  if (!customForm.code.trim()) {
    ElMessage.warning('请填写激活码')
    return
  }
  await adminApi.addCustomCode(customForm)
  ElMessage.success('添加成功')
  customVisible.value = false
  customForm.code = ''
  await load()
}

async function toggle(row) {
  await adminApi.updateCode(row.id, { enabled: !row.enabled })
  ElMessage.success('已更新')
  await load()
}
async function extend(row) {
  await adminApi.updateCode(row.id, { expires_at: 30 })
  ElMessage.success('已延期 30 天')
  await load()
}
async function remove(row) {
  await adminApi.deleteCode(row.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<style scoped>
.head, .filters { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.filters { margin-bottom: 14px; }
.code { font-family: Consolas, monospace; margin-right: 8px; letter-spacing: .5px; }
.pager { margin-top: 14px; display: flex; justify-content: flex-end; }
</style>
