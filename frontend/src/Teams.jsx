import { useEffect, useState } from 'react'
import Navbar from './Navbar'
import { api } from './api'

// GET /teams, POST /teams, POST /teams/join
export default function Teams({ token, username, onOpenTeam, onLogout }) {
  const [teams, setTeams] = useState(null) // null = 로딩 중
  const [newTeamName, setNewTeamName] = useState('')
  const [joinCode, setJoinCode] = useState('')
  const [joinError, setJoinError] = useState('')

  useEffect(() => {
    api.listTeams(token).then(setTeams).catch((err) => setJoinError(err.message))
  }, [token])

  async function handleCreate(e) {
    e.preventDefault()
    const name = newTeamName.trim()
    if (!name) return
    const team = await api.createTeam(token, name)
    setTeams((prev) => [...prev, team])
    setNewTeamName('')
  }

  async function handleJoin(e) {
    e.preventDefault()
    const code = joinCode.trim()
    try {
      const team = await api.joinTeam(token, code)
      setTeams((prev) => [...prev, team])
      setJoinError('')
      setJoinCode('')
    } catch (err) {
      setJoinError(err.message)
    }
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
        <div className="page-heading">
          <span className="pill-badge"><span className="dot" /> 워크스페이스</span>
          <h1>내 팀</h1>
          <p>참여 중인 팀을 열어 진행 상황을 확인하거나, 새 팀을 만들어 보세요.</p>
        </div>

        <div className="section-label">
          <span className="tdot" /> 참여 중인 팀 <span className="count">{teams?.length ?? 0}</span>
        </div>
        {teams === null ? (
          <div className="empty">불러오는 중…</div>
        ) : teams.length ? (
          <div className="team-grid">
            {teams.map((t) => (
              <div className="team-card" key={t.id}>
                <div className="top">
                  <div className="id">
                    <span className="glyph">{t.name.trim().charAt(0)}</span>
                    <div style={{ minWidth: 0 }}>
                      <div className="tname">{t.name}</div>
                      <div className="code">초대코드 <code>{t.invite_code}</code></div>
                    </div>
                  </div>
                  <span className={`role-tag ${t.role}`}>{t.role === 'leader' ? '리더' : '멤버'}</span>
                </div>
                <div className="acts">
                  <button className="btn btn-primary btn-sm" onClick={() => onOpenTeam(t.id)}>열기</button>
                  <button className="btn btn-danger-ghost btn-sm" onClick={() => handleLeaveOrDelete(t)}>
                    {t.role === 'leader' ? '삭제' : '나가기'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : <div className="empty">아직 속한 팀이 없습니다. 아래에서 팀을 만들어 시작하세요.</div>}

        <div className="split-2" style={{ marginTop: 30 }}>
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
              <div className="field-err">{joinError}</div>
            </div>
          </section>
        </div>
      </div>
    </>
  )
}
