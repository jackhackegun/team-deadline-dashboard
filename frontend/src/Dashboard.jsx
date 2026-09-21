import { useEffect, useState } from 'react'
import Navbar from './Navbar'
import Gauge from './Gauge'
import TaskCard from './TaskCard'
import Github from './Github'
import { syncStatus, groupTasks } from './dashboardMath'
import { api } from './api'

// 한 화면에 전부 쌓지 않고 탭으로 나눈다 — 매일 보는 건 '할 일' 하나뿐이다
const TABS = [
  { key: 'tasks', label: '할 일' },
  { key: 'members', label: '멤버' },
  { key: 'settings', label: '설정' },
]

export default function Dashboard({ token, teamId, username, onBack, onLogout }) {
  const [dashboard, setDashboard] = useState(null) // null = 로딩 중
  const [error, setError] = useState('')
  const [tab, setTab] = useState('tasks')
  const [editingTaskId, setEditingTaskId] = useState(null)
  const [adding, setAdding] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newAssigneeId, setNewAssigneeId] = useState('')
  const [newDeadline, setNewDeadline] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [me, setMe] = useState(null) // /auth/me — 내 id와 깃허브 아이디
  const [ghInput, setGhInput] = useState('')

  function refresh() {
    return api.getDashboard(token, teamId).then(setDashboard).catch((err) => setError(err.message))
  }

  useEffect(() => { api.getMe(token).then(setMe).catch(() => {}) }, [token])

  useEffect(() => {
    api.getDashboard(token, teamId).then(setDashboard).catch((err) => setError(err.message))
    // 다른 팀원이 바꾼 내용도 보이도록 60초마다 재조회 (설계문서 §5.2)
    const id = setInterval(() => {
      api.getDashboard(token, teamId).then(setDashboard).catch((err) => setError(err.message))
    }, 60000)
    return () => clearInterval(id)
  }, [token, teamId])

  const nav = (
    <Navbar brand="Deadline Dashboard" backLabel="팀 목록" onBack={onBack} username={username} onLogout={onLogout} />
  )
  if (error) return (
    <>{nav}<div className="container"><div className="panel"><div className="field-err" style={{ padding: 22 }}>{error}</div></div></div></>
  )
  if (!dashboard) return <>{nav}<div className="container"><div className="empty">불러오는 중…</div></div></>

  async function handleAddTask(e) {
    e.preventDefault()
    const assigneeId = newAssigneeId || dashboard.members[0]?.user_id
    if (!newTitle.trim() || !newDeadline || !assigneeId) return
    await api.createTask(token, teamId, {
      title: newTitle.trim(), assignee_id: Number(assigneeId), deadline: `${newDeadline}T00:00:00`,
    })
    setNewTitle('')
    setNewDeadline('')
    setAdding(false)
    refresh()
  }

  async function handleSync() {
    setSyncing(true)
    try {
      await api.syncGithub(token, teamId)
    } catch {
      // 실패 사유는 대시보드의 github_last_error로 내려온다
    }
    await refresh()
    setSyncing(false)
  }

  const sync = syncStatus(dashboard)
  const isLeader = dashboard.my_role === 'leader'
  const overdueTotal = dashboard.members.reduce((s, m) => s + m.overdue_count, 0)
  const doneCount = dashboard.tasks.filter((t) => t.done).length
  const needsGithubId = me && !me.github_login

  const tabBadge = {
    tasks: isLeader ? dashboard.pending_review_count : 0,
    members: 0,
    settings: needsGithubId ? 1 : 0,
  }

  function taskCardProps(task) {
    return {
      task,
      assignee: dashboard.members.find((m) => m.user_id === task.assignee_id),
      members: dashboard.members,
      isEditing: editingTaskId === task.id,
      hasRepo: Boolean(dashboard.repos?.length),
      isLeader,
      isMine: task.assignee_id === me?.id,
      myGithubLogin: me?.github_login,
      loadCommits: () => api.listCommits(token, teamId).then((r) => r.commits),
      onEdit: () => setEditingTaskId(task.id),
      onCancelEdit: () => setEditingTaskId(null),
      onSave: async (id, patch) => { await api.updateTask(token, id, patch); setEditingTaskId(null); refresh() },
      onDelete: async () => { await api.deleteTask(token, task.id); refresh() },
      onToggleStep: async (stepId, checked) => { await api.toggleStep(token, task.id, stepId, checked); refresh() },
      onAddStep: async (title) => { await api.addStep(token, task.id, title); refresh() },
      onRequestReview: async () => { await api.requestReview(token, task.id); refresh() },
      onApprove: async () => { await api.approveTask(token, task.id); refresh() },
      onReject: async () => { await api.rejectTask(token, task.id); refresh() },
      onLinkCommit: async (sha) => { await api.linkCommit(token, task.id, sha); refresh() },
      onUnlinkCommit: async (commitId) => { await api.unlinkCommit(token, task.id, commitId); refresh() },
    }
  }

  return (
    <>
      <Navbar brand={dashboard.team_name} backLabel="팀 목록" onBack={onBack} username={username} onLogout={onLogout} />
      <div className="container container-wide">
        {/* 요약 한 줄 — 큰 제목과 설명문 대신 숫자만 */}
        <div className="team-bar">
          <Gauge percent={dashboard.progress_pct} />
          <div className="tb-name">
            <h1>{dashboard.team_name}</h1>
            <span>멤버 {dashboard.members.length} · 완료 {doneCount}/{dashboard.tasks.length}
              {overdueTotal ? <em className="tb-alert"> · 마감 초과 {overdueTotal}</em> : null}</span>
          </div>
        </div>

        <div className="tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.key} role="tab" aria-selected={tab === t.key}
              className={`tab ${tab === t.key ? 'on' : ''}`} onClick={() => setTab(t.key)}
            >
              {t.label}
              {tabBadge[t.key] ? <span className="tab-badge">{tabBadge[t.key]}</span> : null}
            </button>
          ))}
        </div>

        {tab === 'tasks' && (
          <section className="panel">
            <div className="panel-body">
              <div className="tasks-head">
                {sync && (
                  <span className="sync-inline">
                    <span className={`dot-mark ${sync.error ? 'bad' : 'ok'}`} />
                    {sync.error || sync.label}
                    <button className="btn-quiet" onClick={handleSync} disabled={syncing || !sync.repoCount}>
                      {syncing ? '확인 중…' : '커밋 새로 확인'}
                    </button>
                  </span>
                )}
                <span className="grow" />
                <button className="btn btn-primary btn-sm" onClick={() => setAdding((v) => !v)}>
                  {adding ? '닫기' : '+ 할 일 추가'}
                </button>
              </div>

              {adding && (
                <form className="task-form" onSubmit={handleAddTask}>
                  <input className="input" autoFocus placeholder="새 할 일 제목" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} required />
                  <select className="input" value={newAssigneeId || dashboard.members[0]?.user_id || ''} onChange={(e) => setNewAssigneeId(e.target.value)} required>
                    {dashboard.members.map((m) => <option key={m.user_id} value={m.user_id}>{m.name}</option>)}
                  </select>
                  <input className="input" type="date" value={newDeadline} onChange={(e) => setNewDeadline(e.target.value)} required />
                  <button className="btn btn-primary">추가</button>
                </form>
              )}

              <div style={{ marginTop: 16 }}>
                {dashboard.tasks.length ? groupTasks(dashboard.tasks, isLeader).map((group) => (
                  <div className={`task-group tone-${group.tone}`} key={group.key}>
                    <div className="group-head">
                      <span className="group-title">{group.title}</span>
                      <span className="group-count">{group.tasks.length}</span>
                    </div>
                    {group.tasks.map((task) => <TaskCard key={task.id} {...taskCardProps(task)} />)}
                  </div>
                )) : <div className="empty">아직 할 일이 없습니다. 위 &lsquo;할 일 추가&rsquo;로 시작하세요.</div>}
              </div>
            </div>
          </section>
        )}

        {tab === 'members' && (
          <section className="panel">
            <div className="panel-body">
              <div className="member-list">
                {dashboard.members.map((m) => (
                  <div className="member-row" key={m.user_id}>
                    <Gauge percent={m.progress_pct} />
                    <div className="minfo">
                      <div className="mname">
                        {m.name}<span className="mrole">{m.role === 'leader' ? '리더' : '멤버'}</span>
                        {m.github_login
                          ? <span className="mgh">@{m.github_login}</span>
                          : <span className="mgh muted">깃허브 미등록</span>}
                      </div>
                      <span className={`badge ${m.overdue_count ? 'badge-warn' : 'badge-ok'}`}>
                        {m.overdue_count ? `마감 초과 ${m.overdue_count}건` : '순조롭게 진행 중'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {tab === 'settings' && (
          <>
            <section className="panel">
              <div className="panel-head"><h2 className="panel-title"><span className="tdot" />내 깃허브 아이디</h2></div>
              <div className="panel-body">
                <p className="muted">등록해야 내가 올린 커밋이 나로 표시됩니다.</p>
                <form
                  className="inline-form"
                  onSubmit={async (e) => {
                    e.preventDefault()
                    const saved = await api.setGithubLogin(token, ghInput.trim())
                    setMe({ ...me, github_login: saved.github_login })
                    setGhInput('')
                    refresh()
                  }}
                >
                  <input className="input" placeholder={me?.github_login || '깃허브 아이디'}
                         value={ghInput} onChange={(e) => setGhInput(e.target.value)} />
                  <button className="btn btn-ghost">{me?.github_login ? '변경' : '등록'}</button>
                </form>
                {me?.github_login && <div className="muted" style={{ marginTop: 8 }}>현재: @{me.github_login}</div>}
              </div>
            </section>

            <Github token={token} teamId={teamId} org={dashboard.github_org} isLeader={isLeader} onChanged={refresh} />
          </>
        )}
      </div>
    </>
  )
}
