import { useEffect, useRef, useState } from 'react'
import Navbar from './Navbar'
import { api } from './api'

function TeamCard({ team, onOpen, onLeaveOrDelete }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [copyState, setCopyState] = useState(null) // 'ok' | 'fail' | null
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return
    const close = (e) => { if (!menuRef.current?.contains(e.target)) setMenuOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [menuOpen])

  async function copyInvite(e) {
    e.stopPropagation()
    // await 뒤에는 e.currentTarget이 비므로 지금 붙잡아 둔다
    const button = e.currentTarget
    const text = `[${team.name}] 팀에 초대합니다. 초대코드: ${team.invite_code}`
    let ok = false
    try {
      await navigator.clipboard.writeText(text)
      ok = true
    } catch {
      // http 환경이나 권한 거부 — 됐다고 거짓말하지 않고, 코드를 선택해 두어 바로 복사할 수 있게 한다
      const code = button?.querySelector?.('code')
      if (code) window.getSelection()?.selectAllChildren(code)
    }
    setCopyState(ok ? 'ok' : 'fail')
    setTimeout(() => setCopyState(null), 2000)
  }

  const isLeader = team.role === 'leader'
  const alerts = [
    isLeader && team.pending_review_count ? { text: `승인 대기 ${team.pending_review_count}`, tone: 'wait' } : null,
    team.overdue_count ? { text: `마감 초과 ${team.overdue_count}`, tone: 'danger' } : null,
  ].filter(Boolean)

  return (
    // 카드 어디를 눌러도 열린다 — '열기' 버튼을 조준할 필요가 없다
    <div className="team-card" role="button" tabIndex={0}
         onClick={() => onOpen(team.id)}
         onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(team.id) } }}>
      <div className="tc-head">
        <span className="glyph">{team.name.trim().charAt(0)}</span>
        <div className="tc-name">
          <div className="tname">{team.name}</div>
          <span className={`role-tag ${team.role}`}>{isLeader ? '리더' : '멤버'}</span>
        </div>
        <div className="tc-menu" ref={menuRef}>
          <button className="icon-btn" title="더보기"
                  onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v) }}>⋯</button>
          {menuOpen && (
            <div className="menu">
              <button onClick={(e) => { e.stopPropagation(); setMenuOpen(false); copyInvite(e) }}>초대코드 복사</button>
              <button className="danger"
                      onClick={(e) => { e.stopPropagation(); setMenuOpen(false); onLeaveOrDelete(team) }}>
                {isLeader ? '팀 삭제' : '팀 나가기'}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="tc-progress">
        <div className="tc-bar"><span style={{ width: `${team.progress_pct}%` }} /></div>
        <span className="tc-pct">{team.progress_pct}%</span>
      </div>

      <div className="tc-stats">
        <span>멤버 {team.member_count}</span>
        <span>할 일 {team.task_count}</span>
        {alerts.map((a) => <span className={`tc-alert ${a.tone}`} key={a.text}>{a.text}</span>)}
      </div>

      <button className="tc-invite" onClick={copyInvite} title="초대 문구를 클립보드에 복사">
        <code>{team.invite_code}</code>
        <span>{copyState === 'ok' ? '복사됨' : copyState === 'fail' ? '복사 안 됨 — 직접 복사하세요' : '초대코드 복사'}</span>
      </button>
    </div>
  )
}

// GET /teams, POST /teams, POST /teams/join
export default function Teams({ token, username, onOpenTeam, onLogout }) {
  const [teams, setTeams] = useState(null) // null = 로딩 중
  const [newTeamName, setNewTeamName] = useState('')
  const [joinCode, setJoinCode] = useState('')
  const [error, setError] = useState('')

  function reload() {
    return api.listTeams(token).then(setTeams).catch((err) => setError(err.message))
  }
  useEffect(() => { reload() }, [token])

  async function handleCreate(e) {
    e.preventDefault()
    const name = newTeamName.trim()
    if (!name) return
    try {
      const team = await api.createTeam(token, name)
      setNewTeamName('')
      setError('')
      onOpenTeam(team.id)  // 만들자마자 그 팀으로 들어간다
    } catch (err) { setError(err.message) }
  }

  async function handleJoin(e) {
    e.preventDefault()
    const code = joinCode.trim()
    try {
      const team = await api.joinTeam(token, code)
      setJoinCode('')
      setError('')
      onOpenTeam(team.id)
    } catch (err) { setError(err.message) }
  }

  async function handleLeaveOrDelete(team) {
    const isLeader = team.role === 'leader'
    const message = isLeader
      ? `"${team.name}" 팀을 삭제하면 모든 할 일이 함께 삭제됩니다. 계속할까요?`
      : `"${team.name}" 팀에서 나가시겠어요?`
    if (!window.confirm(message)) return
    if (isLeader) await api.deleteTeam(token, team.id)
    else await api.leaveTeam(token, team.id)
    setTeams((prev) => prev.filter((t) => t.id !== team.id))
  }

  return (
    <>
      <Navbar brand="Deadline Dashboard" username={username} onLogout={onLogout} />
      <div className="container">
        <div className="page-heading compact">
          <h1>내 팀</h1>
        </div>

        {teams === null ? (
          <div className="empty">불러오는 중…</div>
        ) : teams.length ? (
          <div className="team-grid">
            {teams.map((t) => (
              <TeamCard key={t.id} team={t} onOpen={onOpenTeam} onLeaveOrDelete={handleLeaveOrDelete} />
            ))}
          </div>
        ) : <div className="empty">아직 속한 팀이 없습니다. 아래에서 팀을 만들어 시작하세요.</div>}

        <div className="split-2" style={{ marginTop: 26 }}>
          <section className="panel">
            <div className="panel-body">
              <div className="section-label"><span className="tdot" /> 새 팀 만들기</div>
              <form className="inline-form" onSubmit={handleCreate}>
                <input className="input" placeholder="팀 이름" value={newTeamName} onChange={(e) => setNewTeamName(e.target.value)} required />
                <button className="btn btn-primary">만들기</button>
              </form>
            </div>
          </section>

          <section className="panel">
            <div className="panel-body">
              <div className="section-label"><span className="tdot" /> 초대코드로 합류</div>
              <form className="inline-form" onSubmit={handleJoin}>
                <input className="input" placeholder="초대코드 입력" value={joinCode} onChange={(e) => setJoinCode(e.target.value)} required />
                <button className="btn btn-ghost">합류하기</button>
              </form>
            </div>
          </section>
        </div>
        {error && <div className="field-err">{error}</div>}
      </div>
    </>
  )
}
