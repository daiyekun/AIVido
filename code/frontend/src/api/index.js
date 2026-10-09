import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code !== 0) {
        const err = new Error(body.msg || '请求失败')
        err.code = body.code
        err.traceId = body.trace_id
        return Promise.reject(err)
      }
      return body.data
    }
    return body
  },
  (err) => {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('is_admin')
      window.location.href = '/login'
    }
    const body = err.response && err.response.data
    if (body && typeof body === 'object' && body.msg) {
      const e2 = new Error(body.msg)
      e2.code = body.code
      e2.traceId = body.trace_id
      return Promise.reject(e2)
    }
    return Promise.reject(err)
  },
)

export default api
