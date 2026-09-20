import { useState } from 'react'
import { unitsOf, deadlineState, deadlineLabel } from './dashboardMath'

export default function TaskCard({
  task, assignee, members, isEditing,
  onEdit, onCancelEdit, onSave, onDelete, onToggleDone, onToggleStep, onAddStep,
}) {
  const [stepTitle, setStepTitle] = useState('')

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
  const pct = total ? Math.round((done / total) * 100) : 0

  return (
    <div className={`task-card ${cardClass}`}>
      <div className="task-head">
        {hasSteps
          ? <span className="step-count">{done}/{total}</span>
          : <input type="checkbox" checked={task.done} onChange={(e) => onToggleDone(e.target.checked)} />}
        <span className={`task-title ${task.done ? 'done' : ''}`}>{task.title}</span>
        <span className={`task-meta ${metaClass}`}>{assignee ? assignee.name : '-'} · {deadlineLabel(task)}</span>
        <div className="task-actions">
          <button className="btn-icon" onClick={onEdit}>수정</button>
          <button className="btn-icon" onClick={onDelete}>삭제</button>
        </div>
      </div>

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

      {!hasSteps && (
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
