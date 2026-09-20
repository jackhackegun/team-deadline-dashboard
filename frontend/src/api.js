// 접속한 호스트(localhost든 LAN IP든) 기준으로 백엔드를 찾는다. 별도 배포 시 VITE_API_URL로 덮어쓴다.
const BASE_URL = import.meta.env.VITE_API_URL || `http://${location.hostname}:8000`

let unauthorizedHandler = null
export function onUnauthorized(handler) {
  unauthorizedHandler = handler
}

async function request(path, { method = 'GET', token, body } = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  // 로그인 자체의 401(비밀번호 틀림)은 세션이 없으므로 제외 — 토큰을 들고 보낸 요청이 거부된 경우만 로그아웃
  if (res.status === 401 && token && unauthorizedHandler) unauthorizedHandler()
  if (!res.ok) throw new Error(data.detail || `요청 실패 (${res.status})`)
  return data
}

export const api = {
  signup: (email, password, name) => request('/auth/signup', { method: 'POST', body: { email, password, name } }),
  login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password } }),

  listTeams: (token) => request('/teams', { token }),
  createTeam: (token, name) => request('/teams', { method: 'POST', token, body: { name } }),
  joinTeam: (token, inviteCode) => request('/teams/join', { method: 'POST', token, body: { invite_code: inviteCode } }),
  leaveTeam: (token, teamId) => request(`/teams/${teamId}/leave`, { method: 'DELETE', token }),
  deleteTeam: (token, teamId) => request(`/teams/${teamId}`, { method: 'DELETE', token }),

  getDashboard: (token, teamId) => request(`/teams/${teamId}/dashboard`, { token }),
  getGithub: (token, teamId) => request(`/teams/${teamId}/github`, { token }),
  connectGithub: (token, teamId, repo) => request(`/teams/${teamId}/github`, { method: 'PUT', token, body: { repo } }),
  disconnectGithub: (token, teamId) => request(`/teams/${teamId}/github`, { method: 'DELETE', token }),
  createTask: (token, teamId, payload) => request(`/teams/${teamId}/tasks`, { method: 'POST', token, body: payload }),
  updateTask: (token, taskId, patch) => request(`/tasks/${taskId}`, { method: 'PATCH', token, body: patch }),
  deleteTask: (token, taskId) => request(`/tasks/${taskId}`, { method: 'DELETE', token }),
  addStep: (token, taskId, title) => request(`/tasks/${taskId}/steps`, { method: 'POST', token, body: { title } }),
  toggleStep: (token, taskId, stepId, done) => request(`/tasks/${taskId}/steps/${stepId}`, { method: 'PATCH', token, body: { done } }),
}
