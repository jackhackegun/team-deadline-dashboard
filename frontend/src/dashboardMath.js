// 화면 표시용 파생값 계산. progress_pct 자체는 백엔드(GET /teams/:id/dashboard)가 계산해서 내려준다.

// 백엔드 task_units()와 같은 규칙: 완료 판정은 팀장 승인이 하고,
// 승인 전에는 로드맵 단계만큼만 부분 진행률을 준다(마지막 한 칸은 팀장 몫)
export function unitsOf(task) {
  if (task.done) return [1, 1]
  if (task.steps.length) return [task.steps.filter((s) => s.done).length, task.steps.length + 1]
  return [0, 1]
}

export function taskState(task) {
  if (task.done) return 'approved'
  if (task.review_requested_at) return 'pending'
  return 'todo'
}

export function agoLabel(iso) {
  if (!iso) return '아직 확인 안 함'
  const mins = Math.floor((Date.now() - new Date(`${iso}Z`)) / 60000)
  if (mins < 1) return '방금'
  if (mins < 60) return `${mins}분 전`
  const hours = Math.floor(mins / 60)
  return hours < 24 ? `${hours}시간 전` : `${Math.floor(hours / 24)}일 전`
}

// 팀의 레포들 중 가장 최근 동기화 시각과 첫 실패 사유
export function syncStatus(dashboard) {
  if (!dashboard.github_org) return null
  const repos = dashboard.repos || []
  const failed = repos.find((r) => r.last_error)
  const latest = repos.map((r) => r.last_sync_at).filter(Boolean).sort().pop()
  return {
    org: dashboard.github_org,
    repoCount: repos.length,
    error: failed ? `${failed.full_name} — ${failed.last_error}` : null,
    label: repos.length ? agoLabel(latest) + ' 확인함' : '볼 레포를 고르세요',
  }
}

export function gaugeColor(p) {
  return p >= 70 ? '#22d3ee' : p >= 40 ? '#10b981' : '#f59e0b'
}

export function deadlineState(task) {
  if (task.done) return 'done'
  const diffDays = Math.floor((new Date(task.deadline) - new Date()) / 86400000)
  if (diffDays < 0) return 'overdue'
  if (diffDays <= 1) return 'soon'
  return 'normal'
}

export function deadlineLabel(task) {
  const d = new Date(task.deadline)
  const mmdd = `${d.getMonth() + 1}/${d.getDate()}`
  const diffDays = Math.floor((d - new Date()) / 86400000)
  const suffix = diffDays < 0 ? ' (초과)' : diffDays === 0 ? ' (D-day)' : diffDays === 1 ? ' (D-1)' : ''
  return `마감 ${mmdd}${suffix}`
}
