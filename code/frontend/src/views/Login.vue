<template>
  <div class="login-page">
    <div class="shell">
      <!-- 左侧品牌区 -->
      <aside class="brand-panel">
        <div class="bp-top">
          <span class="bp-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </span>
          <div>
            <b>创意AI</b>
            <small>创意无界 · AI 生成</small>
          </div>
        </div>
        <div class="bp-mid">
          <h2>一站式 AI 多媒体<br />创意平台</h2>
          <p>专注电商领域 AIGC，图片、文案、视频全链路专业服务。</p>
          <div class="feats">
            <span>
              <span class="fic">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              </span>
              40+ 专业电商创作应用
            </span>
            <span>
              <span class="fic">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              </span>
              批量出图 · 爆款复刻 · 模特换装
            </span>
            <span>
              <span class="fic">
                <svg viewBox="0 0 24 24" fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              </span>
              AI 视频生成与无限画布创作
            </span>
          </div>
        </div>
        <div class="bp-foot">
          <span>ICP：京18888888000</span>
          <span>京18888888000</span>
        </div>
      </aside>

      <!-- 右侧表单区 -->
      <div class="form-panel">
        <div class="fp-head">
          <div class="logo-mobile">
            <span class="m-logo">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </span>
            <b>创意AI</b>
          </div>
          <h2>欢迎登录</h2>
          <p>输入手机号获取验证码，开始你的 AI 之旅</p>
        </div>

        <form class="login-form" @submit.prevent>
          <!-- 手机号 -->
          <div class="field">
            <label for="phone">手机号码</label>
            <div class="control">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="5" y="2" width="14" height="20" rx="2" />
                <path d="M12 18h.01" />
              </svg>
              <input
                id="phone"
                v-model="form.phone"
                type="text"
                maxlength="11"
                placeholder="请输入 11 位手机号"
                autocomplete="username"
              />
            </div>
          </div>

          <!-- 验证码 -->
          <div class="field">
            <label for="code">验证码</label>
            <div class="control">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <input
                id="code"
                v-model="form.code"
                type="text"
                maxlength="6"
                placeholder="6 位验证码"
                autocomplete="one-time-code"
              />
              <button
                type="button"
                class="cap-btn"
                :disabled="countdown > 0"
                @click="sendCode"
              >
                {{ countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
              </button>
            </div>
          </div>

          <!-- 协议 -->
          <div class="agreements">
            <label class="agree">
              <input v-model="form.agreement" type="checkbox" />
              <span>
                我已阅读并同意
                <span class="hl" @click.prevent.stop="toast('演示版：用户协议')">《用户协议》</span>
                <span class="hl" @click.prevent.stop="toast('演示版：隐私政策')">《隐私政策》</span>
                <span class="hl" @click.prevent.stop="toast('演示版：AI 使用声明')">《生成式 AI 使用声明》</span>
              </span>
            </label>
          </div>

          <button type="button" class="login-btn" :disabled="loading" @click="login">
            {{ loading ? '登录中…' : '立即登录' }}
          </button>
          <p class="tip">未注册手机号验证通过后将自动注册</p>
        </form>
      </div>
    </div>
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

function toast(msg) {
  ElMessage.info(msg)
}

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
    localStorage.setItem('is_admin', data.is_admin ? '1' : '0')
    ElMessage.success(data.is_admin ? '管理员登录成功' : '登录成功')
    router.push(data.is_admin ? '/admin/models' : '/')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(900px 520px at 10% -10%, rgba(16, 185, 225, 0.1), transparent 55%),
    radial-gradient(800px 460px at 95% 110%, rgba(139, 92, 246, 0.1), transparent 55%),
    var(--dj-bg);
}

.shell {
  width: 100%;
  max-width: 960px;
  min-height: 640px;
  border-radius: var(--dj-r-lg);
  overflow: hidden;
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: var(--dj-card);
  border: 1px solid var(--dj-line);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
}

/* ===== 左侧品牌区 ===== */
.brand-panel {
  position: relative;
  overflow: hidden;
  padding: 48px 40px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: linear-gradient(160deg, #0f172a 0%, #1e3a5f 55%, #0e7490 100%);
  color: #fff;
}

.brand-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(ellipse 80% 80% at 30% 50%, black, transparent);
  -webkit-mask-image: radial-gradient(ellipse 80% 80% at 30% 50%, black, transparent);
}

.brand-panel::after {
  content: '';
  position: absolute;
  right: -100px;
  bottom: -100px;
  width: 340px;
  height: 340px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(16, 185, 225, 0.25), transparent 65%);
}

.bp-top {
  display: flex;
  align-items: center;
  gap: 14px;
  position: relative;
  z-index: 2;
}

.bp-logo {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  flex-shrink: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0.08));
  border: 1px solid rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
}

.bp-logo svg {
  width: 26px;
  height: 26px;
  stroke: #fff;
}

.bp-top b {
  font-size: 22px;
  letter-spacing: -0.3px;
  display: block;
}

.bp-top small {
  font-size: 11px;
  font-weight: 400;
  opacity: 0.7;
  letter-spacing: 2.5px;
}

.bp-mid {
  position: relative;
  z-index: 2;
  margin: 44px 0;
}

.bp-mid h2 {
  font-size: 30px;
  line-height: 1.3;
  font-weight: 900;
  letter-spacing: -0.5px;
  margin-bottom: 16px;
}

.bp-mid p {
  font-size: 14.5px;
  line-height: 1.8;
  opacity: 0.85;
  max-width: 340px;
}

.feats {
  margin-top: 32px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.feats span {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  opacity: 0.95;
  font-weight: 500;
}

.fic {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  flex-shrink: 0;
  background: rgba(16, 185, 225, 0.2);
  border: 1px solid rgba(16, 185, 225, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
}

.fic svg {
  width: 13px;
  height: 13px;
  stroke: #67e8f9;
}

.bp-foot {
  position: relative;
  z-index: 2;
  display: flex;
  gap: 20px;
  font-size: 12px;
  opacity: 0.6;
  flex-wrap: wrap;
}

/* ===== 右侧表单区 ===== */
.form-panel {
  padding: 48px 44px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.fp-head {
  text-align: center;
  margin-bottom: 32px;
}

.fp-head .logo-mobile {
  display: none;
}

.fp-head h2 {
  font-size: 27px;
  font-weight: 900;
  letter-spacing: -0.5px;
  color: var(--dj-text);
}

.fp-head p {
  color: var(--dj-sub);
  font-size: 14px;
  margin-top: 8px;
}

.field {
  position: relative;
  margin-bottom: 22px;
}

.field label {
  display: block;
  font-size: 13.5px;
  color: var(--dj-sub);
  margin-bottom: 9px;
  font-weight: 600;
}

.control {
  display: flex;
  align-items: center;
  background: var(--dj-card2);
  border: 1.5px solid var(--dj-line);
  border-radius: var(--dj-r);
  padding: 0 16px;
  transition: var(--dj-t);
}

.control:focus-within {
  border-color: var(--brand-cyan);
  box-shadow: 0 0 0 4px var(--brand-cyan-dim);
}

.control > svg {
  width: 18px;
  height: 18px;
  stroke: var(--dj-dim);
  flex-shrink: 0;
}

.control input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--dj-text);
  font-size: 15px;
  padding: 14px 12px;
  font-family: inherit;
}

.control input::placeholder {
  color: var(--dj-dim);
}

.cap-btn {
  white-space: nowrap;
  border: none;
  background: none;
  color: var(--brand-cyan);
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
  padding-left: 10px;
  transition: var(--dj-t);
}

.cap-btn:hover:not(:disabled) {
  color: #2cc8ea;
}

.cap-btn:disabled {
  color: var(--dj-dim);
  cursor: not-allowed;
}

.agreements {
  margin: 8px 0 24px;
}

.agree {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-size: 12.5px;
  color: var(--dj-sub);
  line-height: 1.65;
  cursor: pointer;
  transition: var(--dj-t);
}

.agree:hover {
  color: var(--dj-text);
}

.agree input {
  width: 16px;
  height: 16px;
  margin-top: 2px;
  accent-color: var(--brand-cyan);
  flex-shrink: 0;
  cursor: pointer;
}

.agree .hl {
  color: var(--brand-cyan);
  font-weight: 600;
  cursor: pointer;
}

.agree .hl:hover {
  text-decoration: underline;
}

.login-btn {
  width: 100%;
  padding: 15px 0;
  border: none;
  border-radius: var(--dj-r);
  background: linear-gradient(135deg, var(--brand-cyan), #0891b2);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  transition: var(--dj-t);
  box-shadow: 0 6px 20px rgba(16, 185, 225, 0.35);
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(16, 185, 225, 0.45);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.tip {
  color: var(--dj-dim);
  font-size: 12.5px;
  text-align: center;
  margin-top: 18px;
}

/* ===== 响应式 ===== */
@media (max-width: 760px) {
  .shell {
    grid-template-columns: 1fr;
    max-width: 460px;
    min-height: auto;
  }
  .brand-panel {
    display: none;
  }
  .fp-head .logo-mobile {
    display: flex;
    align-items: center;
    gap: 12px;
    justify-content: center;
    margin-bottom: 24px;
  }
  .m-logo {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, var(--brand-cyan), #0891b2);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(16, 185, 225, 0.3);
  }
  .m-logo svg {
    width: 24px;
    height: 24px;
    stroke: #fff;
  }
  .fp-head .logo-mobile b {
    font-size: 20px;
    letter-spacing: -0.3px;
  }
  .form-panel {
    padding: 40px 28px;
  }
}
</style>
