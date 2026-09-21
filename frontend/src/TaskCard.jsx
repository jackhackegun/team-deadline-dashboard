import { useState } from 'react'
import { unitsOf, deadlineState, deadlineLabel, taskState, agoLabel } from './dashboardMath'

const STATE_BADGE = {
  approved: { text: '완료 승인됨', cls: 'badge-ok' },
  pending: { text: '승인 대기', cls: 'badge-warn' },
}

export default function TaskCard({
  task, assignee, members, isEditing, isLeader, isMine, hasRepo,
  onEdit, onCancelEdit, onSave, onDelete, onToggleStep, onAddStep,
  onRequestReview, onApprove, onReject, onLinkCommit, onUnlinkCommit,
}) {
  const [stepTitle, setStepTitle] = useState('')
  const [sha, setSha] = useState('')
  const [error, setError] = useState('')

  const state = deadlineState(task)
  const cardClass = state === 'overdue' ? 'overdue' : state === 'soon' ? 'soon' : ''
  const metaClass = state === 'overdue' ? 'overdue-text' : state === 'soon' ? 'soon-text' : ''

  if (isEditing) {
    return (
      <div className={`task-card ${cardClass}`}>
        <form
          className="edit-form"
          onSubmit={(e) => {
            e.preventDefault()
            const form = new FormData(e.target)
            onSave(task.id, {
              title: form.get('title'),
              assignee_id: Number(form.get('assignee_id')),
              deadline: `${form.get('deadline')}T00:00:00`,
            })
          }}
        >
          <input name="title" defaultValue={task.title} required />
          <select name="assignee_id" defaultValue={task.assignee_id}>
            {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.name}</option>)}
          </select>
          <input name="deadline" type="date" defaultValue={task.deadline.slice(0, 10)} required />
          <button type="submit" className="btn btn-primary btn-sm">저장</button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCancelEdit}>취소</button>
        </form>
      </div>
    )
  }

  const [done, total] = unitsOf(task)
  const pct = total ? Math.round((done / total) * 100) : 0
  const hasSteps = task.steps.length > 0
  const commits = task.commits || []
  const status = taskState(task)
  const badge = STATE_BADGE[status]

  async function run(fn) {
    try {
      setError('')
      await fn()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className={`task-card ${cardClass}`}>
      <div className="task-head">
        <span className="step-count">{done}/{total}</span>
        <span className={`task-title ${task.done ? 'done' : ''}`}>
          <span className="task-ref">#{task.id}</span> {task.title}
        </span>
        {badge && <span className={`badge ${badge.cls} auto-badge`}>{badge.text}</span>}
        <span className={`task-meta ${metaClass}`}>{assignee ? assignee.name : '-'} · {deadlineLabel(task)}</span>
        <div className="task-actions">
          {/* 팀원은 완료를 '요청'만, 진행도를 올리는 건 팀장 */}
          {!task.done && !task.review_requested_at && isMine && (
            <button className="btn-icon" onClick={() => run(onRequestReview)}>완료 요청</button>
          )}
          {isLeader && task.review_requested_at && !task.done && (
            <button className="btn-icon approve" onClick={() => run(onApprove)}>승인</button>
          )}
          {isLeader && (task.review_requested_at || task.done) && (
            <button className="btn-icon" onClick={() => run(onReject)}>{task.done ? '승인 취소' : '반려'}</button>
          )}
          <button className="btn-icon" onClick={onEdit}>수정</button>
          <button className="btn-icon" onClick={onDelete}>삭제</button>
        </div>
      </div>

      <div className="progress-bar"><span style={{ width: `${pct}%` }} /></div>

      {commits.length > 0 && (
        <div className="commits">
          {commits.map((c) => (
            <span className="commit-row" key={c.id}>
              <code className="sha">{c.sha.slice(0, 7)}</code>
              <a href={c.url} target="_blank" rel="noreferrer">{c.message}</a>
              <span className="commit-meta">{c.author_login || c.author_name} · {agoLabel(c.committed_at)}</span>
              {c.linked_manually && <span className="badge badge-warn commit-manual">수동</span>}
              <button type="button" className="link-x" title="연결 해제" onClick={() => run(() => onUnlinkCommit(c.id))}>×</button>
            </span>
          ))}
        </div>
      )}

      {hasRepo && commits.length === 0 && (
        <div className="commit-hint">
          커밋 메시지에 <code>[#{task.id}]</code>을 적으면 여기에 자동으로 붙습니다.
        </div>
      )}

      {hasRepo && (
        <div className="step-add" style={{ marginTop: 8 }}>
          <input placeholder="+ 커밋 해시로 직접 붙이기 (예: a1b2c3d)" value={sha} onChange={(e) => setSha(e.target.value)} />
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              const value = sha.trim()
              if (!value) return
              run(async () => { await onLinkCommit(value); setSha('') })
            }}
          >
            붙이기
          </button>
        </div>
      )}

      {error && <div className="field-err">{error}</div>}

      {hasSteps && (
        <div className="steps">
          {task.steps.map((s) => (
            <div className={`step-row ${s.done ? 'done' : ''}`} key={s.id}>
              <input type="checkbox" checked={s.done} onChange={(e) => onToggleStep(s.id, e.target.checked)} />
              <label>{s.title}</label>
            </div>
          ))}
        </div>
      )}

      <div className="step-add" style={{ marginTop: 8 }}>
        <input
          placeholder={hasSteps ? '+ 단계 추가' : '+ 로드맵 단계로 나누기'}
          value={stepTitle}
          onChange={(e) => setStepTitle(e.target.value)}
        />
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => {
            const title = stepTitle.trim()
            if (!title) return
            onAddStep(title)
            setStepTitle('')
          }}
        >
          추가
        </button>
      </div>
    </div>
  )
}
