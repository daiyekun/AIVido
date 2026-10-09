<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2 class="title">EcomCraft AI 创意平台</h2>
      <el-form :model="form" label-position="top" @submit.prevent>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" maxlength="11" placeholder="请输入 11 位手机号" />
        </el-form-item>
        <el-form-item label="验证码">
          <div class="code-row">
            <el-input v-model="form.code" maxlength="6" placeholder="6 位验证码" />
            <el-button :disabled="countdown > 0" @click="sendCode">
              {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
            </el-button>
          </div>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.agreement">
            我已阅读并同意《用户协议》《隐私政策》《生成式 AI 使用声明》
          </el-checkbox>
        </el-form-item>
        <el-button type="primary" class="submit" :loading="loading" @click="login">
          登录 / 注册
        </el-button>
      </el-form>
      <p class="tip">未注册手机号验证通过后将自动注册</p>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const form = reactive({ phone: '', code: '', agreement: true })
const loading = ref(false)
const countdown = ref(0)

async function sendCode() {
  if (!/^1\d{10}$/.test(form.phone)) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  try {
    await api.post('/user/sms-code', { phone: form.phone })
    ElMessage.success('验证码已发送')
    countdown.value = 60
    const timer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) clearInterval(timer)
    }, 1000)
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function login() {
  if (!/^1\d{10}$/.test(form.phone)) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  if (!form.code) {
    ElMessage.warning('请输入验证码')
    return
  }
  if (!form.agreement) {
    ElMessage.warning('请先勾选同意协议')
    return
  }
  loading.value = true
  try {
    const data = await api.post('/user/login', { phone: form.phone, code: form.code })
    localStorage.setItem('token', data.token)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #409eff 0%, #6f7bf7 100%);
}
.login-card {
  width: 400px;
}
.title {
  text-align: center;
  margin: 0 0 16px;
}
.code-row {
  display: flex;
  gap: 12px;
  width: 100%;
}
.submit {
  width: 100%;
}
.tip {
  color: #909399;
  font-size: 12px;
  text-align: center;
}
</style>
