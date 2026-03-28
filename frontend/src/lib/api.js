import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

export const getProjects = () => api.get('/projects')

export const createProject = (title) => api.post('/projects', { title })

export const deleteProject = (id) => api.delete(`/projects/${id}`)

export const runStep = (projectId, stepNum, payload = {}) =>
  api.post(`/projects/${projectId}/steps/${stepNum}/run`, {
    project_id: projectId,
    payload,
  })

export const getStepStatus = (projectId, stepNum) =>
  api.get(`/projects/${projectId}/steps/${stepNum}/status`)

export const getStepData = (projectId, stepNum) =>
  api.get(`/projects/${projectId}/steps/${stepNum}/data`)

export const approveScript = (projectId, finalScript) =>
  api.post(`/projects/${projectId}/steps/2/approve`, { final_script: finalScript })

export const cancelStep = (projectId, stepNum) =>
  api.post(`/projects/${projectId}/steps/${stepNum}/cancel`)

export default api
