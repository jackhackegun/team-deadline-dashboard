// 화면 표시용 파생값 계산. progress_pct 자체는 백엔드(GET /teams/:id/dashboard)가 계산해서 내려준다.

// 스텝이 있으면 스텝 완료 개수 기준, 없으면 done 플래그 기준 (완료/전체 단위) — TaskCard의 "n/m 완료" 표시용
export function unitsOf(task) {
  if (task.steps.length) return [task.steps.filter((s) => s.done).length, task.steps.length]
  return [task.done ? 1 : 0, 1]
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
