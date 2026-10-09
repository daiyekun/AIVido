<template>
  <el-container class="app">
    <el-header v-if="showNav" class="header">
      <div class="brand">EcomCraft AI 创意平台</div>
      <el-menu mode="horizontal" :default-active="activeMenu" router class="menu">
        <el-menu-item index="/">生成图片</el-menu-item>
        <el-menu-item index="/tasks">我的任务</el-menu-item>
      </el-menu>
      <el-button text @click="logout">退出登录</el-button>
    </el-header>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from './api'

const route = useRoute()
const router = useRouter()

const showNav = computed(() => route.name !== 'login')
const activeMenu = computed(() => route.path)

async function logout() {
  try {
    await api.post('/user/logout')
  } catch (e) {
    /* ignore */
  }
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<style>
body {
  margin: 0;
  background: #f5f7fa;
}
.app {
  min-height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  gap: 24px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}
.brand {
  font-size: 18px;
  font-weight: 600;
  color: #409eff;
  white-space: nowrap;
}
.menu {
  flex: 1;
  border-bottom: none;
}
.main {
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
}
</style>
