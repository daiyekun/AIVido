<template>
  <div>
    <!-- 页面标题 -->
    <div class="page-title">
      <h1>我的任务</h1>
      <p>查看生成任务状态，下载产出图片</p>
    </div>

    <!-- 任务面板 -->
    <div class="panel">
      <div class="panel-head">
        <span class="tt">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
          </svg>
          生成记录
        </span>
        <span class="total-badge" v-if="total">共 {{ total }} 条</span>
      </div>

      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column label="任务" width="240">
          <template #default="{ row }">
            <div class="task-id">{{ row.task_id.slice(0, 8) }}</div>
            <div class="task-type">{{ taskTypeName(row.task_type) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="模型" prop="model_id" width="90" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="STATUS_MAP[row.status]?.type" effect="dark" round>
              {{ STATUS_MAP[row.status]?.text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预估积分" prop="expect_credit" width="90" />
        <el-table-column label="产物" min-width="160">
          <template #default="{ row }">
            <div v-if="row.output_asset_urls?.length">
              <el-image
                v-for="(url, i) in row.output_asset_urls"
                :key="i"
                :src="row.output_thumb_urls?.[i] || url"
                :preview-src-list="row.output_asset_urls"
                fit="cover"
                class="thumb"
              />
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            <div class="muted">{{ formatTime(row.create_time) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.output_asset_urls?.length"
              text
              type="primary"
              @click="download(row)"
            >
              下载
            </el-button>
            <el-button
              v-if="['pending', 'queued'].includes(row.status)"
              text
              type="warning"
              @click="cancel(row)"
            >
              取消
            </el-button>
            <el-button text @click="copyTrace(row)">TraceID</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="size"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetch"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const STATUS_MAP = {
  pending: { text: '排队中', type: 'info' },
  queued: { text: '排队中', type: 'info' },
  running: { text: '生成中', type: 'primary' },
  success: { text: '已完成', type: 'success' },
  failed: { text: '已失败', type: 'danger' },
  canceled: { text: '已取消', type: 'warning' },
}

const items = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
let timer = null

onMounted(() => {
  fetch()
  timer = setInterval(() => {
    if (items.value.some((t) => ['pending', 'queued', 'running'].includes(t.status))) {
      fetch(true)
    }
  }, 3000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function fetch(silent = false) {
  if (!silent) loading.value = true
  try {
    const data = await api.get('/task/list', { params: { page: page.value, size: size.value } })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    if (!silent) ElMessage.error(e.message)
  } finally {
    if (!silent) loading.value = false
  }
}

function taskTypeName(type) {
  const map = {
    txt2img: '图片生成',
    img2img: '图片生成',
    txt2vid: '视频生成',
    img2vid: '视频生成',
    vid2vid: '视频生成',
    vid_edit: '视频生成',
  }
  return map[type] || type
}

function formatTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

function download(row) {
  row.output_asset_urls.forEach((url) => window.open(url, '_blank'))
}

async function cancel(row) {
  try {
    await api.post(`/task/${row.task_id}/cancel`)
    ElMessage.success('已取消')
    fetch(true)
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function copyTrace(row) {
  try {
    await navigator.clipboard.writeText(row.trace_id)
    ElMessage.success('TraceID 已复制')
  } catch (e) {
    ElMessage.error('复制失败')
  }
}
</script>

<style scoped>
.page-title {
  margin-bottom: 24px;
}
.page-title h1 {
  font-size: 24px;
  font-weight: 900;
  letter-spacing: -0.4px;
  margin: 0;
  color: var(--dj-text);
}
.page-title p {
  font-size: 14px;
  color: var(--dj-dim);
  margin: 6px 0 0;
}

.panel {
  background: var(--dj-card);
  border: 1px solid var(--dj-line);
  border-radius: var(--dj-r-lg);
  padding: 22px 24px;
  transition: var(--dj-t);
}
.panel:hover {
  border-color: var(--dj-line2);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}
.panel-head .tt {
  font-size: 14.5px;
  font-weight: 800;
  color: var(--dj-sub);
  display: flex;
  align-items: center;
  gap: 10px;
}
.panel-head .tt svg {
  width: 17px;
  height: 17px;
  stroke: var(--brand-cyan);
}
.total-badge {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--brand-cyan);
  background: var(--brand-cyan-dim);
  border: 1px solid rgba(16, 185, 225, 0.35);
  padding: 4px 12px;
  border-radius: var(--dj-r-full);
}

.task-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 600;
  color: var(--dj-text);
}
.task-type {
  color: var(--dj-dim);
  font-size: 12px;
}
.thumb {
  width: 48px;
  height: 48px;
  border-radius: 6px;
  margin-right: 4px;
  border: 1px solid var(--dj-line);
}
.muted {
  color: var(--dj-dim);
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
