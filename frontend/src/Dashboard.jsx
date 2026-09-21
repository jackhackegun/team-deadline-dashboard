import { useEffect, useState } from 'react'
import Navbar from './Navbar'
import Gauge from './Gauge'
import TaskCard from './TaskCard'
import Github from './Github'
import { syncStatus } from './dashboardMath'
import { api } from './api'

// GET /teams/:id/dashboard + task/step CRUD
export default function Dashboard({ token, teamId, username, onBack, onLogout }) {
  const [dashboard, setDashboard] = useState(null) // null = 로딩 중
  const [error, setError] = useState('')
  const [editingTaskId, setEditingTaskId] = useState(null)
  const [newTitle, setNewTitle] = useState('')
  const [newAssigneeId, setNewAssigneeId] = useState('')
  const [newDeadline, setNewDeadline] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [me, setMe] = useState(null) // /auth/me — 내 id와 깃허브 아이디

  function refresh() {
    return api.getDashboard(token, teamId).then(setDashboard).catch((err) => setError(err.message))
  }

  useEffect(() => {
    api.getMe(token).then(setMe).catch(() => {})
  }, [token])

  useEffect(() => {
    api.getDashboard(token, teamId).then(setDashboard).catch((err) => setError(err.message))
    // 다른 팀원이 바꾼 내용도 보이도록 60초마다 재조회 (설계문서 §5.2)
    const id = setInterval(() => {
      api.getDashboard(token, teamId).then(setDashboard).catch((err) => setError(err.message))
    }, 60000)
    return () => clearInterval(id)
  }, [token, teamId])

  async function handleAddTask(e) {
    e.preventDefault()
    const assigneeId = newAssigneeId || dashboard.members[0]?.user_id
    if (!newTitle.trim() || !newDeadline || !assigneeId) return
    await api.createTask(token, teamId, {
      title: newTitle.trim(), assignee_id: Number(assigneeId), deadline: `${newDeadline}T00:00:00`,
    })
    setNewTitle('')
    setNewDeadline('')
    refresh()
  }

  if (error) return (
    <>
      <Navbar brand="Deadline Dashboard" backLabel="팀 목록" onBack={onBack} username={username} onLogout={onLogout} />
      <div className="container"><div className="panel"><div className="field-err" style={{ padding: 22 }}>{error}</div></div></div>
    </>
  )
  if (!dashboard) return (
    <>
      <Navbar brand="Deadline Dashboard" backLabel="팀 목록" onBack={onBack} username={username} onLogout={onLogout} />
      <div className="container"><div className="empty">불러오는 중…</div></div>
    </>
  )

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

  return (
    <>
      <Navbar brand={dashboard.team_name} backLabel="팀 목록" onBack={onBack} username={username} onLogout={onLogout} />
      <div className="container container-wide">
        <div className="page-heading">
          <span className="pill-badge"><span className="dot" /> 팀 대시보드</span>
          <h1>{dashboard.team_name}</h1>
          <p>팀 전체와 멤버별 진행 상황을 한눈에 확인하세요.</p>
          {sync && (
            <div className="sync-bar">
              <span className={`badge ${sync.error ? 'badge-warn' : 'badge-ok'}`}>
                {sync.org} · 레포 {sync.repoCount}
              </span>
              <span className="sync-text">{sync.error || sync.label}</span>
              <button className="btn btn-ghost btn-sm" onClick={handleSync} disabled={syncing || !sync.repoCount}>
                {syncing ? '커밋 확인 중…' : '커밋 새로 확인'}
              </button>
            </div>
          )}
          {me && !me.github_login && (
            <div className="sync-bar gh-prompt">
              <span className="sync-text">내 깃허브 아이디를 등록해야 내 커밋이 나로 표시됩니다.</span>
              <input
                className="input input-sm"
                placeholder="깃허브 아이디"
                onKeyDown={async (e) => {
                  if (e.key !== 'Enter' || !e.target.value.trim()) return
                  const saved = await api.setGithubLogin(token, e.target.value.trim())
                  setMe({ ...me, github_login: saved.github_login })
                  refresh()
                }}
              />
            </div>
          )}
        </div>

        {/* 오버뷰 — 회로형 허브 */}
        <section className="panel panel-hero">
          <div className="panel-body">
            <div className="hub">
              <div className="hub-core"><Gauge percent={dashboard.progress_pct} large /></div>
              <div className="hub-cap"><span className="lead">{dashboard.team_name}</span>팀 전체 진행률</div>
              <div className="link-down" />
              <div className="bus">
                <div className="node"><div className="v">{dashboard.members.length}</div><div className="l">멤버</div></div>
                <div className="link-line" />
                <div className="node"><div className="v">{doneCount}/{dashboard.tasks.length}</div><div className="l">완료한 할 일</div></div>
                <div className="link-line" />
                <div className={`node${overdueTotal ? ' alert' : ''}`}><div className="v">{overdueTotal}</div><div className="l">마감 초과</div></div>
              </div>
            </div>
          </div>
        </section>

        <div className="dash-grid" style={{ marginTop: 20 }}>
          {/* 할 일 (메인) */}
          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title"><span className="tdot" />할 일<span className="count">{dashboard.tasks.length}</span></h2>
              {isLeader && dashboard.pending_review_count > 0 && (
                <span className="badge badge-warn">승인 대기 {dashboard.pending_review_count}건</span>
              )}
            </div>
            <div className="panel-body">
              <form className="task-form" onSubmit={handleAddTask}>
                <input className="input" placeholder="새 할 일 제목" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} required />
                <select className="input" value={newAssigneeId || dashboard.members[0]?.user_id || ''} onChange={(e) => setNewAssigneeId(e.target.value)} required>
                  {dashboard.members.map((m) => <option key={m.user_id} value={m.user_id}>{m.name}</option>)}
                </select>
                <input className="input" type="date" value={newDeadline} onChange={(e) => setNewDeadline(e.target.value)} required />
                <button className="btn btn-primary">추가</button>
              </form>

              <div style={{ marginTop: 18 }}>
                {dashboard.tasks.length ? dashboard.tasks.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    assignee={dashboard.members.find((m) => m.user_id === task.assignee_id)}
                    members={dashboard.members}
                    isEditing={editingTaskId === task.id}
                    hasRepo={Boolean(dashboard.repos?.length)}
                    isLeader={isLeader}
                    isMine={task.assignee_id === me?.id}
                    onEdit={() => setEditingTaskId(task.id)}
                    onCancelEdit={() => setEditingTaskId(null)}
                    onSave={async (id, patch) => { await api.updateTask(token, id, patch); setEditingTaskId(null); refresh() }}
                    onDelete={async () => { await api.deleteTask(token, task.id); refresh() }}
                    onToggleStep={async (stepId, checked) => { await api.toggleStep(token, task.id, stepId, checked); refresh() }}
                    onAddStep={async (title) => { await api.addStep(token, task.id, title); refresh() }}
                    onRequestReview={async () => { await api.requestReview(token, task.id); refresh() }}
                    onApprove={async () => { await api.approveTask(token, task.id); refresh() }}
                    onReject={async () => { await api.rejectTask(token, task.id); refresh() }}
                    onLinkCommit={async (sha) => { await api.linkCommit(token, task.id, sha); refresh() }}
                    onUnlinkCommit={async (commitId) => { await api.unlinkCommit(token, task.id, commitId); refresh() }}
                  />
                )) : <div className="empty">아직 할 일이 없습니다. 위에서 첫 할 일을 추가해 보세요.</div>}
              </div>
            </div>
          </section>

          {/* 멤버 (사이드) */}
          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title"><span className="tdot" />멤버별 진행률<span className="count">{dashboard.members.length}</span></h2>
            </div>
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
        </div>

        <Github
          token={token}
          teamId={teamId}
          org={dashboard.github_org}
          isLeader={isLeader}
          onChanged={refresh}
        />
      </div>
    </>
  )
}
