// 화면 표시용 파생값 계산. progress_pct 자체는 백엔드(GET /teams/:id/dashboard)가 계산해서 내려준다.

// 백엔드 task_units()와 같은 우선순위: 사람이 되돌린 판단 > 깃허브 이슈/PR > 로드맵 단계 > done 플래그
export function unitsOf(task) {
  if (task.done_override) return [task.done ? 1 : 0, 1]
  if (task.links?.length) return [task.links.filter(isLinkClosed).length, task.links.length]
  if (task.steps.length) return [task.steps.filter((s) => s.done).length, task.steps.length]
  return [task.done ? 1 : 0, 1]
}

export function isLinkClosed(link) {
  return link.state === 'closed' || link.state === 'merged'
}

export function syncLabel(dashboard) {
  if (!dashboard.github_repo) return null
  if (dashboard.github_last_error) return `동기화 실패 — ${dashboard.github_last_error}`
  if (!dashboard.github_last_sync_at) return '아직 동기화하지 않음'
  const mins = Math.floor((Date.now() - new Date(`${dashboard.github_last_sync_at}Z`)) / 60000)
  if (mins < 1) return '방금 동기화됨'
  return mins < 60 ? `${mins}분 전 동기화` : `${Math.floor(mins / 60)}시간 전 동기화`
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
