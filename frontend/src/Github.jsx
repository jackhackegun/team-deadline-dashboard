import { useEffect, useState } from 'react'
import { api } from './api'

function shortDate(iso) {
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

// 팀에 연결된 GitHub 레포의 커밋/PR 활동 피드
export default function Github({ token, teamId }) {
  const [data, setData] = useState(null) // null = 로딩 중
  const [error, setError] = useState('')
  const [repoInput, setRepoInput] = useState('')
  const [busy, setBusy] = useState(false)

  function load() {
    setError('')
    return api.getGithub(token, teamId).then(setData).catch((err) => setError(err.message))
  }

  useEffect(() => { setData(null); load() }, [token, teamId])

  async function handleConnect(e) {
    e.preventDefault()
    const repo = repoInput.trim()
    if (!repo) return
    setBusy(true); setError('')
    try {
      await api.connectGithub(token, teamId, repo)
      setRepoInput('')
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleDisconnect() {
    if (!window.confirm('GitHub 레포 연결을 해제할까요?')) return
    setBusy(true)
    try { await api.disconnectGithub(token, teamId); await load() } finally { setBusy(false) }
  }

  return (
    <section className="panel" style={{ marginTop: 20 }}>
      <div className="panel-head">
        <h2 className="panel-title"><span className="tdot" />GitHub 활동</h2>
        {data?.repo && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <a className="gh-repo" href={`https://github.com/${data.repo}`} target="_blank" rel="noreferrer">{data.repo} ↗</a>
            <button className="btn btn-ghost btn-sm" onClick={load} disabled={busy}>새로고침</button>
            <button className="btn btn-danger-ghost btn-sm" onClick={handleDisconnect} disabled={busy}>연결 해제</button>
          </div>
        )}
      </div>

      <div className="panel-body">
        {data === null ? (
          <div className="empty">불러오는 중…</div>
        ) : !data.repo ? (
          <div className="gh-connect">
            <p className="gh-hint">팀의 GitHub 레포를 연결하면 최근 커밋과 PR을 여기서 볼 수 있어요.</p>
            <form className="inline-form" onSubmit={handleConnect}>
              <input className="input" placeholder="owner/name  (예: facebook/react)" value={repoInput} onChange={(e) => setRepoInput(e.target.value)} required />
              <button className="btn btn-primary" disabled={busy}>{busy ? '연결 중…' : '연결'}</button>
            </form>
            <div className="field-err">{error}</div>
          </div>
        ) : (
          <>
            <div className="field-err">{error}</div>
            <div className="gh-grid">
              <div>
                <div className="gh-sub">최근 커밋</div>
                {data.commits.length ? data.commits.map((c) => (
                  <a className="gh-row" key={c.sha} href={c.url} target="_blank" rel="noreferrer">
                    <code className="gh-sha">{c.sha}</code>
                    <span className="gh-msg">{c.message}</span>
                    <span className="gh-meta">{c.author} · {shortDate(c.date)}</span>
                  </a>
                )) : <div className="empty">커밋이 없습니다.</div>}
              </div>
              <div>
                <div className="gh-sub">Pull Request</div>
                {data.pulls.length ? data.pulls.map((p) => (
                  <a className="gh-row" key={p.number} href={p.url} target="_blank" rel="noreferrer">
                    <span className={`pr-state ${p.state}`}>{p.state === 'merged' ? '머지됨' : p.state === 'open' ? '열림' : '닫힘'}</span>
                    <span className="gh-msg">#{p.number} {p.title}</span>
                    <span className="gh-meta">{p.author}</span>
                  </a>
                )) : <div className="empty">PR이 없습니다.</div>}
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  )
}
