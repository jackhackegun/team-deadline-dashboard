// 접속한 호스트(localhost든 LAN IP든) 기준으로 백엔드를 찾는다. 별도 배포 시 VITE_API_URL로 덮어쓴다.
const BASE_URL = import.meta.env.VITE_API_URL || `http://${location.hostname}:8000`

let unauthorizedHandler = null
export function onUnauthorized(handler) {
  unauthorizedHandler = handler
}

// 서버 detail은 보통 문자열이지만 검증 오류는 배열로 올 수 있다.
// 그대로 Error에 넣으면 화면에 "[object Object]"가 찍혀 사용자가 원인을 알 수 없다.
export function readDetail(data, status) {
  const d = data?.detail
  if (typeof d === 'string' && d) return d
  if (Array.isArray(d) && d.length) return d.map((e) => e?.msg || String(e)).join(' ')
  if (d && typeof d === 'object' && d.msg) return d.msg
  return `요청 실패 (${status})`
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
  if (!res.ok) throw new Error(readDetail(data, res.status))
  return data
}

export const api = {
  signup: (email, password, name) => request('/auth/signup', { method: 'POST', body: { email, password, name } }),
  login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password } }),

  listTeams: (token) => request('/teams', { token }),
  createTeam: (token, name) => request('/teams', { method: 'POST', token, body: { name } }),
  joinTeam: (token, inviteCode) => request('/teams/join', { method: 'POST', token, body: { invite_code: inviteCode } }),
  transferLeader: (token, teamId, userId) =>
    request(`/teams/${teamId}/transfer-leader`, { method: 'POST', token, body: { user_id: userId } }),
  leaveTeam: (token, teamId) => request(`/teams/${teamId}/leave`, { method: 'DELETE', token }),
  deleteTeam: (token, teamId) => request(`/teams/${teamId}`, { method: 'DELETE', token }),

  getDashboard: (token, teamId) => request(`/teams/${teamId}/dashboard`, { token }),

  getMe: (token) => request('/auth/me', { token }),
  setGithubLogin: (token, githubLogin) => request('/auth/me', { method: 'PATCH', token, body: { github_login: githubLogin } }),

  connectOrg: (token, teamId, org) => request(`/teams/${teamId}/github/org`, { method: 'PUT', token, body: { org } }),
  disconnectOrg: (token, teamId) => request(`/teams/${teamId}/github/org`, { method: 'DELETE', token }),
  browseOrgRepos: (token, teamId) => request(`/teams/${teamId}/github/org/repos`, { token }),
  selectRepos: (token, teamId, repos) => request(`/teams/${teamId}/github/repos`, { method: 'PUT', token, body: { repos } }),
  listCommits: (token, teamId) => request(`/teams/${teamId}/github/commits`, { token }),
  createTask: (token, teamId, payload) => request(`/teams/${teamId}/tasks`, { method: 'POST', token, body: payload }),
  updateTask: (token, taskId, patch) => request(`/tasks/${taskId}`, { method: 'PATCH', token, body: patch }),
  deleteTask: (token, taskId) => request(`/tasks/${taskId}`, { method: 'DELETE', token }),
  addStep: (token, taskId, title) => request(`/tasks/${taskId}/steps`, { method: 'POST', token, body: { title } }),
  linkCommit: (token, taskId, sha) => request(`/tasks/${taskId}/commits`, { method: 'POST', token, body: { sha } }),
  unlinkCommit: (token, taskId, commitId) => request(`/tasks/${taskId}/commits/${commitId}`, { method: 'DELETE', token }),
  syncGithub: (token, teamId) => request(`/teams/${teamId}/github/sync`, { method: 'POST', token }),

  requestReview: (token, taskId) => request(`/tasks/${taskId}/request-review`, { method: 'POST', token }),
  approveTask: (token, taskId) => request(`/tasks/${taskId}/approve`, { method: 'POST', token }),
  rejectTask: (token, taskId) => request(`/tasks/${taskId}/reject`, { method: 'POST', token }),

  toggleStep: (token, taskId, stepId, done) => request(`/tasks/${taskId}/steps/${stepId}`, { method: 'PATCH', token, body: { done } }),
}
