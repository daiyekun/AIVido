<template>
  <div>
    <div class="page-title">
      <h1>模型管理</h1>
      <p>配置可用的 AI 模型、支持档位与计价（仅管理员可见）</p>
    </div>

    <div class="panel">
      <div class="toolbar">
        <el-select v-model="query.model_type" placeholder="全部类型" clearable style="width: 140px" @change="load(1)">
          <el-option label="图片" value="image" />
          <el-option label="视频" value="video" />
        </el-select>
        <el-input
          v-model="query.keyword"
          placeholder="搜索模型名称"
          clearable
          style="width: 220px"
          @keyup.enter="load(1)"
          @clear="load(1)"
        />
        <button class="ghost-btn" @click="load(1)">查询</button>
        <div class="spacer"></div>
        <button class="primary-btn" @click="openDialog()">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
          新建模型
        </button>
      </div>

      <el-table :data="items" v-loading="loading" class="dark-table" row-key="model_id">
        <el-table-column prop="model_id" label="ID" width="70" />
        <el-table-column prop="model_name" label="模型名称" min-width="140" show-overflow-tooltip />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.model_type === 'image' ? 'primary' : 'warning'" round size="small">
              {{ row.model_type === 'image' ? '图片' : '视频' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="adapter_key" label="适配器" min-width="120" show-overflow-tooltip />
        <el-table-column label="支持档位" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="tier">{{ (row.support_resolution || []).join(' / ') || '—' }}</span>
            <span v-if="row.support_duration?.length" class="tier">{{ row.support_duration.map(d => d + 's').join(' / ') }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="price_tip" label="计价" min-width="140" show-overflow-tooltip />
        <el-table-column prop="sort" label="排序" width="70" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_enable"
              @change="(v) => toggleStatus(row, v)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <button class="link-btn" @click="openDialog(row)">编辑</button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="query.size"
          :current-page="query.page"
          @current-change="(p) => load(p)"
        />
      </div>
    </div>

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑模型' : '新建模型'"
      width="640px"
      destroy-on-close
      class="dark-dialog"
    >
      <el-form :model="form" label-width="96px" label-position="left">
        <el-form-item label="模型名称" required>
          <el-input v-model="form.model_name" maxlength="128" placeholder="不含空格，如：通义万相文生图" />
        </el-form-item>
        <el-form-item label="模型类型" required>
          <el-radio-group v-model="form.model_type">
            <el-radio value="image">图片</el-radio>
            <el-radio value="video">视频</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="适配器" required>
          <el-input v-model="form.adapter_key" maxlength="64" placeholder="字母/数字/_-. 如：wanxiang_image" />
        </el-form-item>
        <el-form-item label="排序值">
          <el-input-number v-model="form.sort" :min="0" :max="1000000" />
        </el-form-item>

        <el-form-item v-if="form.model_type === 'image'" label="分辨率档位" required>
          <div class="chip-list">
            <span v-for="(r, i) in form.support_resolution" :key="i" class="chip">
              {{ r }}
              <button type="button" class="chip-x" @click="form.support_resolution.splice(i, 1)">×</button>
            </span>
            <el-input
              v-if="resolutionInputVisible"
              ref="resolutionInputRef"
              v-model="resolutionInput"
              size="small"
              style="width: 130px"
              @keyup.enter="addResolution"
              @blur="addResolution"
            />
            <button v-else type="button" class="chip-add" @click="showResolutionInput">+ 添加</button>
          </div>
        </el-form-item>

        <el-form-item v-else label="时长档位(s)" required>
          <div class="chip-list">
            <span v-for="(d, i) in form.support_duration" :key="i" class="chip">
              {{ d }}s
              <button type="button" class="chip-x" @click="form.support_duration.splice(i, 1)">×</button>
            </span>
            <el-input-number
              v-model="durationInput"
              :min="1"
              :max="600"
              size="small"
              style="width: 120px"
              @keyup.enter="addDuration"
            />
            <button type="button" class="chip-add" @click="addDuration">+ 添加</button>
          </div>
        </el-form-item>

        <el-form-item label="计价配置">
          <el-input
            v-model="form.price_config_json"
            type="textarea"
            :rows="3"
            placeholder='JSON，如：{"1024*1024": 1, "2K": 1.5}'
          />
        </el-form-item>
        <el-form-item label="适配配置">
          <el-input
            v-model="form.config_json"
            type="textarea"
            :rows="3"
            placeholder='JSON。密钥字段只允许填环境变量名，如：{"api_key_env": "WANXIANG_API_KEY"}'
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" maxlength="512" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_enable" />
        </el-form-item>
      </el-form>

      <template #footer>
        <button class="ghost-btn" @click="dialogVisible = false">取消</button>
        <button class="primary-btn" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const loading = ref(false)
const saving = ref(false)
const items = ref([])
const total = ref(0)
const query = reactive({ page: 1, size: 20, model_type: '', keyword: '' })

const dialogVisible = ref(false)
const editingId = ref(null)
const emptyForm = () => ({
  model_name: '',
  model_type: 'image',
  adapter_key: '',
  sort: 0,
  support_resolution: [],
  support_duration: [],
  price_config_json: '',
  config_json: '',
  remark: '',
  is_enable: true,
})
const form = reactive(emptyForm())

const resolutionInputVisible = ref(false)
const resolutionInput = ref('')
const resolutionInputRef = ref()
const durationInput = ref(5)

onMounted(() => load(1))

async function load(page) {
  query.page = page || 1
  loading.value = true
  try {
    const params = { page: query.page, size: query.size }
    if (query.model_type) params.model_type = query.model_type
    if (query.keyword) params.keyword = query.keyword
    const data = await api.get('/admin/model/list', { params })
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function toggleStatus(row, value) {
  try {
    await api.put(`/admin/model/${row.model_id}/status`, { is_enable: value })
    row.is_enable = value
    ElMessage.success(value ? '已启用' : '已禁用')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function openDialog(row) {
  Object.assign(form, emptyForm())
  editingId.value = null
  if (row) {
    editingId.value = row.model_id
    form.model_name = row.model_name
    form.model_type = row.model_type
    form.adapter_key = row.adapter_key
    form.sort = row.sort
    form.support_resolution = [...(row.support_resolution || [])]
    form.support_duration = [...(row.support_duration || [])]
    form.price_config_json = JSON.stringify(row.price_config_json || {}, null, 2)
    form.config_json = JSON.stringify(row.config_json || {}, null, 2)
    form.remark = row.remark || ''
    form.is_enable = row.is_enable
  }
  dialogVisible.value = true
}

async function showResolutionInput() {
  resolutionInputVisible.value = true
  await nextTick()
  resolutionInputRef.value?.focus()
}

function addResolution() {
  const v = resolutionInput.value.trim()
  if (v && !form.support_resolution.includes(v)) {
    form.support_resolution.push(v)
  }
  resolutionInput.value = ''
  resolutionInputVisible.value = false
}

function addDuration() {
  const v = Number(durationInput.value)
  if (v > 0 && v <= 600 && !form.support_duration.includes(v)) {
    form.support_duration.push(v)
  }
}

function parseJson(text, label) {
  const t = (text || '').trim()
  if (!t) return {}
  try {
    const obj = JSON.parse(t)
    if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
      throw new Error('not object')
    }
    return obj
  } catch (e) {
    throw new Error(`${label} 不是合法的 JSON 对象`)
  }
}

async function save() {
  if (!form.model_name.trim()) {
    ElMessage.warning('请输入模型名称')
    return
  }
  if (!form.adapter_key.trim()) {
    ElMessage.warning('请输入适配器标识')
    return
  }
  if (form.model_type === 'image' && !form.support_resolution.length) {
    ElMessage.warning('图片模型至少配置一个分辨率档位')
    return
  }
  if (form.model_type === 'video' && !form.support_duration.length) {
    ElMessage.warning('视频模型至少配置一个时长档位')
    return
  }
  let priceConfig
  let configJson
  try {
    priceConfig = parseJson(form.price_config_json, '计价配置')
    configJson = parseJson(form.config_json, '适配配置')
  } catch (e) {
    ElMessage.warning(e.message)
    return
  }
  const body = {
    model_name: form.model_name.trim(),
    model_type: form.model_type,
    adapter_key: form.adapter_key.trim(),
    sort: form.sort,
    support_resolution: form.model_type === 'image' ? form.support_resolution : [],
    support_duration: form.model_type === 'video' ? form.support_duration : [],
    config_json: configJson,
    price_config_json: priceConfig,
    remark: form.remark,
    is_enable: form.is_enable,
  }
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/admin/model/${editingId.value}`, body)
      ElMessage.success('已保存')
    } else {
      await api.post('/admin/model/create', body)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load(query.page)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
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
  padding: 20px 22px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.spacer {
  flex: 1;
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: none;
  cursor: pointer;
  font-size: 13.5px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--brand-cyan), #0891b2);
  color: #fff;
  padding: 9px 18px;
  border-radius: var(--dj-r);
  box-shadow: 0 4px 14px rgba(16, 185, 225, 0.3);
  transition: var(--dj-t);
  font-family: inherit;
}
.primary-btn svg {
  width: 14px;
  height: 14px;
}
.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}
.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ghost-btn {
  background: var(--dj-card2);
  border: 1px solid var(--dj-line2);
  color: var(--dj-sub);
  font-size: 13.5px;
  font-weight: 600;
  padding: 9px 18px;
  border-radius: var(--dj-r);
  cursor: pointer;
  font-family: inherit;
  transition: var(--dj-t);
}
.ghost-btn:hover {
  color: var(--dj-text);
  border-color: var(--brand-cyan);
}

.link-btn {
  background: none;
  border: none;
  color: var(--brand-cyan);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  padding: 2px 0;
}
.link-btn:hover {
  text-decoration: underline;
}

.tier {
  font-size: 12.5px;
  color: var(--dj-sub);
  margin-right: 8px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.chip-list {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  width: 100%;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--dj-card2);
  border: 1px solid var(--dj-line2);
  color: var(--dj-sub);
  font-size: 12.5px;
  padding: 4px 10px;
  border-radius: var(--dj-r-sm);
}
.chip-x {
  background: none;
  border: none;
  color: var(--dj-dim);
  cursor: pointer;
  font-size: 14px;
  padding: 0;
  line-height: 1;
}
.chip-x:hover {
  color: #f43f5e;
}
.chip-add {
  background: none;
  border: 1px dashed var(--dj-line2);
  color: var(--dj-dim);
  font-size: 12.5px;
  padding: 4px 12px;
  border-radius: var(--dj-r-sm);
  cursor: pointer;
  font-family: inherit;
  transition: var(--dj-t);
}
.chip-add:hover {
  border-color: var(--brand-cyan);
  color: var(--brand-cyan);
}
</style>
