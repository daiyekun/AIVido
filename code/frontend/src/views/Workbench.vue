<template>
  <div>
    <!-- 页面标题 -->
    <div class="page-title">
      <h1>生成图片</h1>
      <p>选择模型，描述画面，AI 一键生成专业电商图片</p>
    </div>

    <!-- 创作台 -->
    <div class="stage">
      <div class="stage-head">
        <span class="tt">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="3" />
            <circle cx="9" cy="9" r="2" />
            <path d="M21 15l-5-5L5 21" />
          </svg>
          图片生成工作台
        </span>
        <span class="stage-hint">JPG / JPEG / PNG / WebP，单张 ≤ 10MB</span>
      </div>

      <!-- 模型 + 分辨率 -->
      <div class="model-bar">
        <div class="model-cell grow">
          <label>模型</label>
          <el-select v-model="form.model_id" placeholder="请选择模型" style="width: 100%">
            <el-option
              v-for="m in models"
              :key="m.model_id"
              :label="m.model_name"
              :value="m.model_id"
            >
              <span>{{ m.model_name }}</span>
              <span class="price-tip">{{ m.price_tip }}</span>
            </el-option>
          </el-select>
        </div>
        <div class="model-cell">
          <label>分辨率</label>
          <el-select v-model="form.resolution" placeholder="请选择分辨率" style="width: 180px">
            <el-option v-for="r in resolutions" :key="r" :label="r" :value="r" />
          </el-select>
        </div>
      </div>

      <!-- 正向提示词 -->
      <div class="field-block">
        <div class="field-label">
          <span>正向提示词</span>
          <span class="chars">{{ form.prompt.length }}/2000</span>
        </div>
        <div class="prompt-box">
          <textarea
            v-model="form.prompt"
            maxlength="2000"
            rows="4"
            placeholder="描述你想生成的图片，例如：高清电商商品白底摄影图"
          />
        </div>
      </div>

      <!-- 反向提示词 -->
      <div class="field-block">
        <div class="field-label"><span>反向提示词</span><span class="opt">可选</span></div>
        <div class="prompt-box">
          <textarea
            v-model="form.negative_prompt"
            rows="2"
            placeholder="不希望出现的内容，例如：模糊、水印、低质量"
          />
        </div>
      </div>

      <!-- 参考图 -->
      <div class="field-block">
        <div class="field-label"><span>参考图</span><span class="opt">可选</span></div>
        <div class="material-bar">
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            accept=".jpg,.jpeg,.png,.webp"
            :before-upload="onBeforeUpload"
            :on-change="onFileChange"
          >
            <button type="button" class="material-item" :class="{ loading: uploading }">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="3" />
                <circle cx="9" cy="9" r="2" />
                <path d="M21 15l-5-5L5 21" />
              </svg>
              {{ uploading ? '上传中…' : '上传参考图' }}
            </button>
          </el-upload>
          <div v-if="asset.url" class="preview">
            <el-image :src="asset.url" fit="cover" class="preview-img" />
            <button type="button" class="remove-btn" @click="removeAsset">移除</button>
          </div>
        </div>
      </div>

      <!-- 重绘强度 -->
      <div v-if="asset.object_key" class="field-block">
        <div class="field-label">
          <span>重绘强度</span>
          <span class="chars">{{ form.denoising_strength }}</span>
        </div>
        <div class="slider-row">
          <el-slider v-model="form.denoising_strength" :min="0" :max="1" :step="0.05" />
        </div>
      </div>

      <!-- 底部操作栏 -->
      <div class="stage-foot">
        <span class="foot-note">提交后将按模型单价扣除积分</span>
        <button type="button" class="gen-btn" :disabled="submitting" @click="submit">
          <svg v-if="!submitting" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M23 4v6h-6M1 20v-6h6" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
          {{ submitting ? '提交中…' : '生成图片' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const models = ref([])
const uploading = ref(false)
const submitting = ref(false)
const form = reactive({
  model_id: null,
  prompt: '',
  negative_prompt: '',
  resolution: '',
  denoising_strength: 0.7,
  n: 1,
})
const asset = reactive({ object_key: '', url: '', media_type: '' })

const currentModel = computed(() => models.value.find((m) => m.model_id === form.model_id))
const resolutions = computed(() => currentModel.value?.support_resolution || [])

onMounted(async () => {
  try {
    models.value = await api.get('/model/image/list')
    if (models.value.length > 0) {
      form.model_id = models.value[0].model_id
      if (models.value[0].support_resolution?.length) {
        form.resolution = models.value[0].support_resolution[0]
      }
    }
  } catch (e) {
    ElMessage.error(e.message)
  }
})

function onBeforeUpload(file) {
  const ok = /\.(jpg|jpeg|png|webp)$/i.test(file.name)
  if (!ok) ElMessage.warning('仅支持 JPG/JPEG/PNG/WebP')
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('图片不能超过 10MB')
    return false
  }
  return ok
}

async function onFileChange(uploadFile) {
  const file = uploadFile.raw
  if (!file) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('gen_type', 'image')
    fd.append('file', file)
    const data = await api.post('/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    asset.object_key = data.object_key
    asset.url = data.url
    asset.media_type = data.media_type
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    uploading.value = false
  }
}

function removeAsset() {
  asset.object_key = ''
  asset.url = ''
  asset.media_type = ''
}

async function submit() {
  if (!form.model_id) {
    ElMessage.warning('请选择模型')
    return
  }
  if (!form.prompt.trim()) {
    ElMessage.warning('请输入正向提示词')
    return
  }
  if (!form.resolution) {
    ElMessage.warning('请选择分辨率')
    return
  }
  submitting.value = true
  try {
    const body = {
      gen_type: 'image_gen',
      model_id: form.model_id,
      prompt: form.prompt,
      negative_prompt: form.negative_prompt || null,
      resolution: form.resolution,
      n: form.n,
    }
    if (asset.object_key) {
      body.asset_object_key = asset.object_key
      body.denoising_strength = form.denoising_strength
    }
    const data = await api.post('/generate/task', body)
    ElMessage.success(`任务已提交，预估积分 ${data.expect_credit}`)
    router.push('/tasks')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
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

/* ===== 创作台 ===== */
.stage {
  background: var(--dj-card);
  border: 1px solid var(--dj-line);
  border-radius: var(--dj-r-lg);
  padding: 24px 26px;
  transition: var(--dj-t);
}
.stage:hover {
  border-color: var(--dj-line2);
}

.stage-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.stage-head .tt {
  font-size: 14.5px;
  font-weight: 800;
  color: var(--dj-sub);
  display: flex;
  align-items: center;
  gap: 10px;
}
.stage-head .tt svg {
  width: 17px;
  height: 17px;
  stroke: var(--brand-cyan);
}
.stage-hint {
  font-size: 12.5px;
  color: var(--dj-dim);
}

/* 模型行 */
.model-bar {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.model-cell.grow {
  flex: 1;
  min-width: 260px;
}
.model-cell label {
  display: block;
  font-size: 13px;
  color: var(--dj-sub);
  margin-bottom: 8px;
  font-weight: 600;
}
.price-tip {
  color: var(--dj-dim);
  font-size: 12px;
  float: right;
  margin-left: 16px;
}

/* 字段块 */
.field-block {
  margin-bottom: 20px;
}
.field-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--dj-sub);
  margin-bottom: 8px;
  font-weight: 600;
}
.field-label .chars {
  font-size: 12.5px;
  color: var(--dj-dim);
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.field-label .opt {
  font-size: 12px;
  color: var(--dj-dim);
  font-weight: 400;
}

/* 提示词输入 */
.prompt-box {
  background: var(--dj-card2);
  border: 1.5px solid var(--dj-line);
  border-radius: var(--dj-r);
  padding: 4px 16px;
  transition: var(--dj-t);
}
.prompt-box:focus-within {
  border-color: var(--brand-cyan);
  box-shadow: 0 0 0 4px var(--brand-cyan-dim);
}
.prompt-box textarea {
  width: 100%;
  background: transparent;
  border: none;
  outline: none;
  resize: vertical;
  color: var(--dj-text);
  font-size: 15px;
  line-height: 1.7;
  min-height: 48px;
  font-family: inherit;
  padding: 12px 0;
}
.prompt-box textarea::placeholder {
  color: var(--dj-dim);
}

/* 参考图 */
.material-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.material-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--dj-card2);
  border: 1.5px dashed var(--dj-line2);
  padding: 10px 18px;
  border-radius: var(--dj-r);
  font-size: 13.5px;
  color: var(--dj-sub);
  cursor: pointer;
  transition: var(--dj-t);
  font-weight: 500;
  font-family: inherit;
}
.material-item svg {
  width: 16px;
  height: 16px;
  stroke: var(--brand-cyan);
}
.material-item:hover {
  border-color: var(--brand-cyan);
  color: var(--dj-text);
  background: var(--brand-cyan-dim);
  transform: translateY(-1px);
}
.material-item.loading {
  opacity: 0.6;
  cursor: wait;
}
.preview {
  display: flex;
  align-items: center;
  gap: 12px;
}
.preview-img {
  width: 80px;
  height: 80px;
  border-radius: var(--dj-r-sm);
  border: 1px solid var(--dj-line);
}
.remove-btn {
  background: none;
  border: 1px solid var(--dj-line2);
  color: var(--dj-dim);
  font-size: 12.5px;
  padding: 6px 14px;
  border-radius: var(--dj-r-sm);
  cursor: pointer;
  font-family: inherit;
  transition: var(--dj-t);
}
.remove-btn:hover {
  color: #f43f5e;
  border-color: #f43f5e;
}

/* 滑杆 */
.slider-row {
  padding: 4px 8px 0;
}

/* 底部操作栏 */
.stage-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--dj-line);
  flex-wrap: wrap;
}
.foot-note {
  font-size: 12.5px;
  color: var(--dj-dim);
}
.gen-btn {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  border: none;
  cursor: pointer;
  font-size: 15px;
  font-weight: 800;
  background: linear-gradient(135deg, var(--brand-cyan), #0891b2);
  color: #fff;
  padding: 12px 28px;
  border-radius: var(--dj-r);
  box-shadow: 0 6px 20px rgba(16, 185, 225, 0.35);
  transition: var(--dj-t);
  font-family: inherit;
}
.gen-btn svg {
  width: 17px;
  height: 17px;
}
.gen-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(16, 185, 225, 0.45);
}
.gen-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ===== 响应式 ===== */
@media (max-width: 600px) {
  .stage {
    padding: 18px 16px;
  }
  .model-cell,
  .model-cell.grow {
    width: 100%;
    min-width: 0;
  }
  .model-cell .el-select {
    width: 100% !important;
  }
  .stage-foot {
    flex-direction: column;
    align-items: stretch;
  }
  .gen-btn {
    justify-content: center;
  }
}
</style>
