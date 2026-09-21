import { useState } from 'react'
import { unitsOf, deadlineState, deadlineLabel, taskState, agoLabel } from './dashboardMath'

export default function TaskCard({
  task, assignee, members, isEditing, isLeader, isMine, hasRepo, myGithubLogin,
  onEdit, onCancelEdit, onSave, onDelete, onToggleStep, onAddStep,
  onRequestReview, onApprove, onReject, onLinkCommit, onUnlinkCommit, loadCommits,
}) {
  // 입력칸은 기본으로 접어둔다 — 카드마다 빈 칸이 널려 있으면 목록을 읽을 수가 없다
  const [panel, setPanel] = useState(null) // 'step' | 'commit' | null
  const [stepTitle, setStepTitle] = useState('')
  const [picker, setPicker] = useState(null) // 최근 커밋 목록 (null = 불러오는 중)
  const [error, setError] = useState('')

  const dState = deadlineState(task)
  const status = taskState(task)

  if (isEditing) {
    return (
      <div className="task-card editing">
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
  const steps = task.steps
  const commits = task.commits || []

  async function run(fn) {
    try {
      setError('')
      await fn()
    } catch (err) {
      setError(err.message)
    }
  }

  function togglePanel(name) {
    setError('')
    const next = panel === name ? null : name
    setPanel(next)
    // 커밋은 해시를 외워서 칠 수 있는 게 아니다 — 열면 최근 목록을 가져와 고르게 한다
    if (next === 'commit') {
      setPicker(null)
      loadCommits().then(setPicker).catch((err) => { setError(err.message); setPanel(null) })
    }
  }

  return (
    <div className={`task-card ${status} ${dState === 'overdue' ? 'overdue' : ''}`}>
      <div className="task-top">
        <div className="task-main">
          <div className="task-title-row">
            <span className={`task-title ${task.done ? 'done' : ''}`}>{task.title}</span>
            {status === 'pending' && <span className="chip chip-wait">승인 대기</span>}
            {status === 'approved' && <span className="chip chip-done">완료</span>}
          </div>
          <div className="task-sub">
            <span className="who">{assignee ? assignee.name : '담당자 없음'}</span>
            <span className={`when ${dState === 'overdue' ? 'is-overdue' : dState === 'soon' ? 'is-soon' : ''}`}>
              {deadlineLabel(task)}
            </span>
            {commits.length > 0 && <span className="meta-dot">커밋 {commits.length}</span>}
            {steps.length > 0 && <span className="meta-dot">단계 {done}/{steps.length}</span>}
          </div>
        </div>

        <div className="task-side">
          {/* 지금 이 할 일에 할 수 있는 '진짜 행동' 하나만 눈에 띄게 둔다 */}
          {isLeader && status === 'pending' && (
            <button className="btn btn-primary btn-sm" onClick={() => run(onApprove)}>승인</button>
          )}
          {!isLeader && isMine && status === 'todo' && (
            <button className="btn btn-ghost btn-sm" onClick={() => run(onRequestReview)}>완료 요청</button>
          )}
          {isLeader && status === 'approved' && (
            <button className="btn-quiet" onClick={() => run(onReject)}>승인 취소</button>
          )}
          {isLeader && status === 'pending' && (
            <button className="btn-quiet" onClick={() => run(onReject)}>반려</button>
          )}
        </div>
      </div>

      {(steps.length > 0 || task.done) && (
        <div className="progress-bar"><span style={{ width: `${pct}%` }} /></div>
      )}

      {steps.length > 0 && (
        <div className="steps">
          {steps.map((s) => (
            <label className={`step-row ${s.done ? 'done' : ''}`} key={s.id}>
              <input type="checkbox" checked={s.done} onChange={(e) => onToggleStep(s.id, e.target.checked)} />
              <span>{s.title}</span>
            </label>
          ))}
        </div>
      )}

      {commits.length > 0 && (
        <div className="commits">
          {commits.map((c) => (
            <div className="commit-row" key={c.id}>
              <code className="sha">{c.sha.slice(0, 7)}</code>
              <a href={c.url} target="_blank" rel="noreferrer">{c.message}</a>
              <span className="commit-meta">{c.author_login || c.author_name} · {agoLabel(c.committed_at)}</span>
              <button type="button" className="row-x" title="연결 해제" onClick={() => run(() => onUnlinkCommit(c.id))}>×</button>
            </div>
          ))}
        </div>
      )}

      {/* 덜 쓰는 조작은 한 줄로 접어둔다 */}
      <div className="task-tools">
        <button className={`tool ${panel === 'step' ? 'on' : ''}`} onClick={() => togglePanel('step')}>단계 추가</button>
        {hasRepo && (
          <button className={`tool ${panel === 'commit' ? 'on' : ''}`} onClick={() => togglePanel('commit')}>커밋 붙이기</button>
        )}
        <span className="tool-gap" />
        <button className="tool" onClick={onEdit}>수정</button>
        <button className="tool danger" onClick={onDelete}>삭제</button>
      </div>

      {panel === 'step' && (
        <div className="tool-panel">
          <input
            autoFocus placeholder="단계 이름 (예: 자료 조사)" value={stepTitle}
            onChange={(e) => setStepTitle(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.nextSibling.click() } }}
          />
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => {
              const title = stepTitle.trim()
              if (!title) return
              run(async () => { await onAddStep(title); setStepTitle('') })
            }}
          >추가</button>
        </div>
      )}

      {panel === 'commit' && (
        <div className="commit-picker">
          {picker === null && <div className="picker-empty">최근 커밋을 불러오는 중…</div>}
          {picker && picker.length === 0 && (
            <div className="picker-empty">최근 커밋이 없습니다. 레포가 연결돼 있는지 확인하세요.</div>
          )}
          {picker && picker.length > 0 && (
            <>
              <div className="picker-hint">
                붙일 커밋을 고르세요. 다음부터는 커밋 메시지에 <code>[#{task.id}]</code>만 적으면 자동으로 붙습니다.
              </div>
              <div className="picker-list">
                {picker.map((c) => {
                  const already = commits.some((x) => x.sha === c.sha)
                  const mine = myGithubLogin && c.author_login === myGithubLogin
                  return (
                    <button
                      type="button" key={c.sha} disabled={already}
                      className={`picker-row ${already ? 'used' : ''} ${mine ? 'mine' : ''}`}
                      onClick={() => run(async () => { await onLinkCommit(c.sha); setPanel(null) })}
                    >
                      <code className="sha">{c.sha.slice(0, 7)}</code>
                      <span className="pmsg">{c.message}</span>
                      <span className="pmeta">{c.author_login || c.author_name} · {agoLabel(c.committed_at)}</span>
                      <span className="pmark">{already ? '붙음' : mine ? '내 커밋' : ''}</span>
                    </button>
                  )
                })}
              </div>
            </>
          )}
        </div>
      )}

      {error && <div className="field-err">{error}</div>}
    </div>
  )
}
