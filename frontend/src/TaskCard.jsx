import { useState } from 'react'
import { unitsOf, deadlineState, deadlineLabel, isLinkClosed } from './dashboardMath'

const LINK_STATE_LABEL = { open: '열림', closed: '닫힘', merged: '머지됨' }

export default function TaskCard({
  task, assignee, members, isEditing, hasRepo,
  onEdit, onCancelEdit, onSave, onDelete, onToggleDone, onToggleStep, onAddStep, onAddLink, onRemoveLink,
}) {
  const [stepTitle, setStepTitle] = useState('')
  const [linkRef, setLinkRef] = useState('')
  const [linkError, setLinkError] = useState('')

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
  const hasSteps = task.steps.length > 0
  const links = task.links || []
  const hasLinks = links.length > 0
  const pct = total ? Math.round((done / total) * 100) : 0

  async function submitLink() {
    const ref = linkRef.trim()
    if (!ref) return
    try {
      setLinkError('')
      await onAddLink(ref)
      setLinkRef('')
    } catch (err) {
      setLinkError(err.message)
    }
  }

  return (
    <div className={`task-card ${cardClass}`}>
      <div className="task-head">
        {hasSteps || hasLinks
          ? <span className="step-count">{done}/{total}</span>
          : <input type="checkbox" checked={task.done} onChange={(e) => onToggleDone(e.target.checked)} />}
        <span className={`task-title ${task.done ? 'done' : ''}`}>{task.title}</span>
        {task.auto_completed_at && <span className="badge badge-ok auto-badge">깃허브 자동 완료</span>}
        {task.done_override && <span className="badge badge-warn auto-badge">직접 지정</span>}
        <span className={`task-meta ${metaClass}`}>{assignee ? assignee.name : '-'} · {deadlineLabel(task)}</span>
        <div className="task-actions">
          {hasLinks && (
            <button className="btn-icon" onClick={() => onToggleDone(!task.done)}>
              {task.done ? '완료 해제' : '완료 처리'}
            </button>
          )}
          <button className="btn-icon" onClick={onEdit}>수정</button>
          <button className="btn-icon" onClick={onDelete}>삭제</button>
        </div>
      </div>

      {hasLinks && (
        <>
          <div className="progress-bar"><span style={{ width: `${pct}%` }} /></div>
          <div className="links">
            {links.map((l) => (
              <span className={`link-chip ${l.state}`} key={l.id}>
                <a href={l.url} target="_blank" rel="noreferrer">
                  <strong>{l.kind === 'pr' ? 'PR #' : '#'}{l.number}</strong> {l.title}
                </a>
                <span className={`link-state ${isLinkClosed(l) ? 'closed' : ''}`}>{LINK_STATE_LABEL[l.state]}</span>
                <button type="button" className="link-x" title="연결 해제" onClick={() => onRemoveLink(l.id)}>×</button>
              </span>
            ))}
          </div>
        </>
      )}

      {hasRepo && (
        <div className="step-add" style={{ marginTop: 10 }}>
          <input
            placeholder="+ 이슈/PR 연결 (예: 123 또는 PR 주소)"
            value={linkRef}
            onChange={(e) => setLinkRef(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); submitLink() } }}
          />
          <button type="button" className="btn btn-ghost btn-sm" onClick={submitLink}>연결</button>
        </div>
      )}
      {linkError && <div className="field-err">{linkError}</div>}

      {hasSteps && (
        <>
          <div className="progress-bar"><span style={{ width: `${pct}%` }} /></div>
          <div className="steps">
            {task.steps.map((s) => (
              <div className={`step-row ${s.done ? 'done' : ''}`} key={s.id}>
                <input type="checkbox" checked={s.done} onChange={(e) => onToggleStep(s.id, e.target.checked)} />
                <label>{s.title}</label>
              </div>
            ))}
            <div className="step-add">
              <input placeholder="+ 단계 추가" value={stepTitle} onChange={(e) => setStepTitle(e.target.value)} />
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
        </>
      )}

      {!hasSteps && !hasLinks && (
        <div className="step-add" style={{ marginTop: 10 }}>
          <input placeholder="+ 로드맵 단계로 나누기" value={stepTitle} onChange={(e) => setStepTitle(e.target.value)} />
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
      )}
    </div>
  )
}
