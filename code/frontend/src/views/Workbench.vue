<template>
  <div>
    <el-card class="panel">
      <template #header>
        <div class="panel-title">生成图片</div>
      </template>

      <el-form :model="form" label-width="90px">
        <el-form-item label="模型">
          <el-select v-model="form.model_id" placeholder="请选择模型" style="width: 320px">
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
        </el-form-item>

        <el-form-item label="正向提示词">
          <el-input
            v-model="form.prompt"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="描述你想生成的图片，例如：高清电商商品白底摄影图"
          />
        </el-form-item>

        <el-form-item label="反向提示词">
          <el-input
            v-model="form.negative_prompt"
            type="textarea"
            :rows="2"
            placeholder="不希望出现的内容，可选"
          />
        </el-form-item>

        <el-form-item label="参考图">
          <div class="upload-area">
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept=".jpg,.jpeg,.png,.webp"
              :before-upload="onBeforeUpload"
              :on-change="onFileChange"
            >
              <el-button :loading="uploading">上传参考图（可选）</el-button>
            </el-upload>
            <div v-if="asset.url" class="preview">
              <el-image :src="asset.url" fit="cover" class="preview-img" />
              <el-button text type="danger" @click="removeAsset">移除</el-button>
            </div>
          </div>
          <div class="hint">JPG / JPEG / PNG / WebP，单张 ≤ 10MB</div>
        </el-form-item>

        <el-form-item v-if="asset.object_key" label="重绘强度">
          <el-slider v-model="form.denoising_strength" :min="0" :max="1" :step="0.05" />
          <span class="slider-val">{{ form.denoising_strength }}</span>
        </el-form-item>

        <el-form-item label="分辨率">
          <el-select v-model="form.resolution" placeholder="请选择分辨率" style="width: 200px">
            <el-option
              v-for="r in resolutions"
              :key="r"
              :label="r"
              :value="r"
            />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submit">生成图片</el-button>
        </el-form-item>
      </el-form>
    </el-card>
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
.panel {
  margin-top: 16px;
}
.panel-title {
  font-weight: 600;
}
.price-tip {
  color: #909399;
  font-size: 12px;
  float: right;
}
.upload-area {
  display: flex;
  align-items: center;
  gap: 16px;
}
.preview-img {
  width: 80px;
  height: 80px;
  border-radius: 6px;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.slider-val {
  width: 40px;
  margin-left: 8px;
}
</style>
