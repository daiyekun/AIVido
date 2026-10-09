<template>
  <!-- 登录页：独立全屏布局 -->
  <router-view v-if="!showNav" />

  <!-- 应用布局：左侧导航 + 顶栏 + 内容 -->
  <div v-else class="shell">
    <aside class="sidebar">
      <router-link to="/" class="side-brand">
        <span class="side-logo">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </span>
        <div class="brand-text">
          <b>创意AI</b>
          <small>创意无界 · AI 生成</small>
        </div>
      </router-link>

      <nav class="side-nav">
        <!-- 普通用户：只有创作入口 -->
        <template v-if="!isAdmin">
          <div class="nav-group">创作</div>
          <router-link
            to="/"
            class="nav-item"
            :class="{ on: route.path === '/' }"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="3" />
              <circle cx="9" cy="9" r="2" />
              <path d="M21 15l-5-5L5 21" />
            </svg>
            <span>生成图片</span>
          </router-link>
          <router-link
            to="/tasks"
            class="nav-item"
            :class="{ on: route.path === '/tasks' }"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
            <span>我的任务</span>
          </router-link>
        </template>

        <!-- 管理员：只有后台配置 -->
        <template v-else>
          <div class="nav-group">后台配置</div>
          <router-link
            to="/admin/models"
            class="nav-item"
            :class="{ on: route.path === '/admin/models' }"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="3" width="20" height="14" rx="2" />
              <path d="M8 21h8M12 17v4" />
            </svg>
            <span>模型管理</span>
          </router-link>
        </template>
      </nav>

      <div class="side-foot">
        <span class="avatar">{{ isAdmin ? '管' : '创' }}</span>
        <span class="user-meta">
          <b>{{ isAdmin ? '管理员' : '普通用户' }}</b>
        </span>
        <button class="logout-btn" @click="logout">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <path d="M16 17l5-5-5-5" />
            <path d="M21 12H9" />
          </svg>
          退出
        </button>
      </div>
    </aside>

    <div class="main-col">
      <header class="topbar">
        <div class="crumb">
          {{ pageTitle }}
          <small>{{ isAdmin ? '后台配置中心 · 仅管理员可操作' : '专注电商领域 AIGC 平台 · 提供全链路专业服务' }}</small>
        </div>
        <div class="spacer"></div>

        <span v-if="isAdmin" class="admin-badge">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          管理员后台
        </span>

        <template v-else>
          <div class="points">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M8 14s1.5 2 4 2 4-2 4-2" />
              <path d="M9 9h.01M15 9h.01" />
            </svg>
            {{ creditText }}
          </div>
          <button class="top-link" @click="toast('演示版：积分商城')">积分商城</button>
          <button class="vip-btn" @click="toast('演示版：会员中心')">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            开通会员
          </button>
        </template>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>

    <button class="support" title="联系客服" @click="toast('演示版：联系客服')">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    </button>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from './api'

const route = useRoute()
const router = useRouter()

const showNav = computed(() => route.name !== 'login')
const isAdmin = ref(localStorage.getItem('is_admin') === '1')
const credit = ref(0)
const creditText = computed(() => Number(credit.value || 0).toFixed(2))

const pageTitle = computed(() => {
  if (route.meta.title) return route.meta.title
  return route.path === '/' ? '生成图片' : '我的任务'
})

async function refreshMe() {
  if (!localStorage.getItem('token')) return
  try {
    const me = await api.get('/user/me')
    isAdmin.value = !!me.is_admin
    credit.value = me.credit_balance || 0
    localStorage.setItem('is_admin', me.is_admin ? '1' : '0')
  } catch (e) {
    /* 401 由拦截器处理 */
  }
}

onMounted(refreshMe)
watch(() => route.path, refreshMe)

function toast(msg) {
  ElMessage.info(msg)
}

async function logout() {
  try {
    await api.post('/user/logout')
  } catch (e) {
    /* ignore */
  }
  localStorage.removeItem('token')
  localStorage.removeItem('is_admin')
  router.push('/login')
}
</script>

<style scoped>
/* ===== 外壳 ===== */
.shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--dj-bg);
}

/* ===== 左侧导航 ===== */
.sidebar {
  width: 232px;
  flex-shrink: 0;
  background: var(--dj-panel);
  border-right: 1px solid var(--dj-line);
  display: flex;
  flex-direction: column;
  transition: var(--dj-t);
}

.side-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 18px 16px;
  border-bottom: 1px solid var(--dj-line);
  text-decoration: none;
}

.side-logo {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand-cyan), #0891b2);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(16, 185, 225, 0.3);
}

.side-logo svg {
  width: 20px;
  height: 20px;
  stroke: #fff;
}

.brand-text b {
  font-size: 16.5px;
  letter-spacing: -0.3px;
  display: block;
  color: var(--dj-text);
}

.brand-text small {
  font-size: 10px;
  color: var(--dj-dim);
  letter-spacing: 2px;
  display: block;
  margin-top: 1px;
}

.nav-group {
  font-size: 10.5px;
  font-weight: 700;
  color: var(--dj-dim);
  letter-spacing: 2px;
  padding: 18px 20px 8px;
  text-transform: uppercase;
}

.side-nav {
  flex: 1;
  overflow-y: auto;
  padding: 4px 12px 14px;
}

.side-nav::-webkit-scrollbar {
  width: 5px;
}

.side-nav::-webkit-scrollbar-thumb {
  background: var(--dj-line2);
  border-radius: 3px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  border-radius: var(--dj-r);
  font-size: 14px;
  color: var(--dj-sub);
  cursor: pointer;
  transition: var(--dj-t);
  margin-bottom: 3px;
  position: relative;
  text-decoration: none;
}

.nav-item svg {
  width: 18px;
  height: 18px;
  stroke: currentColor;
  flex-shrink: 0;
}

.nav-item:hover {
  background: var(--dj-card);
  color: var(--dj-text);
}

.nav-item.on {
  background: linear-gradient(90deg, var(--brand-cyan-dim), transparent);
  color: var(--brand-cyan);
  font-weight: 600;
}

.nav-item.on::before {
  content: '';
  position: absolute;
  left: 0;
  top: 9px;
  bottom: 9px;
  width: 3px;
  border-radius: 3px;
  background: var(--brand-cyan);
}

.side-foot {
  padding: 14px 18px;
  border-top: 1px solid var(--dj-line);
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.user-meta b {
  font-size: 12.5px;
  color: var(--dj-sub);
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand-cyan), var(--brand-violet));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12.5px;
  font-weight: 800;
  flex-shrink: 0;
}

.logout-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--dj-dim);
  font-size: 12.5px;
  cursor: pointer;
  font-family: inherit;
  padding: 4px 0;
  transition: var(--dj-t);
}

.logout-btn svg {
  width: 15px;
  height: 15px;
}

.logout-btn:hover {
  color: var(--brand-cyan);
}

/* ===== 主列 ===== */
.main-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 28px;
  background: rgba(11, 15, 23, 0.88);
  backdrop-filter: blur(16px) saturate(1.6);
  -webkit-backdrop-filter: blur(16px) saturate(1.6);
  border-bottom: 1px solid var(--dj-line);
  flex-shrink: 0;
}

.crumb {
  font-size: 15.5px;
  font-weight: 800;
  letter-spacing: -0.2px;
  color: var(--dj-text);
}

.crumb small {
  display: block;
  font-size: 11.5px;
  color: var(--dj-dim);
  font-weight: 400;
  margin-top: 2px;
}

.spacer {
  flex: 1;
}

.admin-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: rgba(139, 92, 246, 0.12);
  border: 1px solid rgba(139, 92, 246, 0.4);
  color: #a78bfa;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 16px;
  border-radius: var(--dj-r-full);
}

.admin-badge svg {
  width: 15px;
  height: 15px;
}

.points {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--dj-card);
  border: 1px solid var(--dj-line);
  padding: 8px 16px;
  border-radius: var(--dj-r-full);
  font-size: 13.5px;
  font-weight: 800;
  color: var(--dj-text);
}

.points svg {
  width: 16px;
  height: 16px;
  stroke: var(--dj-gold);
}

.top-link {
  padding: 8px 16px;
  border-radius: var(--dj-r-full);
  border: 1px solid var(--dj-line);
  background: var(--dj-card);
  color: var(--dj-sub);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: var(--dj-t);
}

.top-link:hover {
  color: var(--dj-text);
  border-color: var(--dj-line2);
  transform: translateY(-1px);
}

.vip-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 20px;
  border-radius: var(--dj-r-full);
  border: none;
  cursor: pointer;
  font-size: 13.5px;
  font-weight: 800;
  font-family: inherit;
  background: linear-gradient(135deg, #f59e0b, #ea580c);
  color: #fff;
  box-shadow: 0 4px 16px rgba(249, 115, 22, 0.35);
  transition: var(--dj-t);
}

.vip-btn svg {
  width: 15px;
  height: 15px;
  stroke: #fff;
}

.vip-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(249, 115, 22, 0.45);
}

/* ===== 内容区 ===== */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 28px 28px 72px;
  max-width: 1240px;
  width: 100%;
  margin: 0 auto;
}

.content::-webkit-scrollbar {
  width: 7px;
}

.content::-webkit-scrollbar-thumb {
  background: var(--dj-line2);
  border-radius: 4px;
}

/* ===== 客服悬浮 ===== */
.support {
  position: fixed;
  right: 24px;
  bottom: 28px;
  width: 54px;
  height: 54px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--brand-cyan), #0891b2);
  color: #fff;
  border: none;
  cursor: pointer;
  box-shadow: 0 10px 30px rgba(16, 185, 225, 0.4);
  z-index: 80;
  transition: var(--dj-t);
}

.support:hover {
  transform: translateY(-3px) scale(1.06);
  box-shadow: 0 14px 36px rgba(16, 185, 225, 0.5);
}

.support svg {
  width: 22px;
  height: 22px;
}

/* ===== 响应式 ===== */
@media (max-width: 900px) {
  .sidebar {
    width: 68px;
  }
  .brand-text,
  .nav-group,
  .nav-item span,
  .logout-btn {
    display: none;
  }
  .nav-item {
    justify-content: center;
    padding: 12px 0;
  }
  .side-foot {
    justify-content: center;
  }
  .topbar {
    padding: 12px 16px;
    flex-wrap: wrap;
  }
  .content {
    padding: 18px 16px 80px;
  }
}
</style>
