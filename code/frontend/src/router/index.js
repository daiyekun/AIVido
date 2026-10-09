import { createRouter, createWebHistory } from 'vue-router'
import api from '../api'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
  { path: '/', name: 'workbench', component: () => import('../views/Workbench.vue'), meta: { admin: false, title: '生成图片' } },
  { path: '/tasks', name: 'tasks', component: () => import('../views/Tasks.vue'), meta: { admin: false, title: '我的任务' } },
  { path: '/admin/models', name: 'admin-models', component: () => import('../views/AdminModels.vue'), meta: { admin: true, title: '模型管理' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

let roleLoaded = false

async function loadRole() {
  try {
    const me = await api.get('/user/me')
    localStorage.setItem('is_admin', me.is_admin ? '1' : '0')
    roleLoaded = true
    return me.is_admin
  } catch (e) {
    return null
  }
}

router.beforeEach(async (to) => {
  const token = localStorage.getItem('token')

  if (to.name !== 'login' && !token) {
    return { name: 'login' }
  }
  if (to.name === 'login' && token) {
    const isAdmin = localStorage.getItem('is_admin') === '1'
    return { name: isAdmin ? 'admin-models' : 'workbench' }
  }

  if (to.meta.admin === undefined) return true

  let isAdmin = localStorage.getItem('is_admin') === '1'
  if (!roleLoaded) {
    const remote = await loadRole()
    if (remote !== null) isAdmin = remote
  }

  // 管理员只能进后台配置页
  if (to.meta.admin === true && !isAdmin) {
    return { name: 'workbench' }
  }
  // 普通用户只能进创作页
  if (to.meta.admin === false && isAdmin) {
    return { name: 'admin-models' }
  }
  return true
})

export { loadRole }
export default router
