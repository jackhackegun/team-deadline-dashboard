import { useEffect, useState } from 'react'
import { api } from './api'

// 1단계: 팀장이 오가니제이션을 등록하고, 이 팀이 쓸 레포를 고른다
export default function Github({ token, teamId, org, isLeader, onChanged }) {
  const [input, setInput] = useState('')
  const [repos, setRepos] = useState(null) // null = 아직 안 불러옴
  const [selected, setSelected] = useState(new Set())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!org) { setRepos(null); return }
    let alive = true
    api.browseOrgRepos(token, teamId)
      .then((data) => {
        if (!alive) return
        setRepos(data.repos)
        setSelected(new Set(data.repos.filter((r) => r.selected).map((r) => r.full_name)))
      })
      .catch((err) => alive && setError(err.message))
    return () => { alive = false }
  }, [token, teamId, org])

  async function run(fn) {
    setBusy(true)
    try {
      setError('')
      await fn()
      onChanged()
    } catch (err) {
      setError(err.message)
    }
    setBusy(false)
  }

  return (
    <section className="panel" style={{ marginTop: 20 }}>
      <div className="panel-head">
        <h2 className="panel-title"><span className="tdot" />GitHub 오가니제이션</h2>
        {org && isLeader && (
          <button className="btn btn-ghost btn-sm" onClick={() => run(() => api.disconnectOrg(token, teamId))}>
            연결 해제
          </button>
        )}
      </div>
      <div className="panel-body">
        {!org && (
          <>
            <p className="muted">
              {isLeader
                ? '팀의 오가니제이션을 등록하면 그 안의 레포에서 커밋을 읽어옵니다.'
                : '팀장이 오가니제이션을 등록하면 여기에 표시됩니다.'}
            </p>
            {isLeader && (
              <div className="step-add">
                <input
                  placeholder="오가니제이션 이름 (예: vercel)"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                />
                <button
                  className="btn btn-primary btn-sm"
                  disabled={busy}
                  onClick={() => input.trim() && run(() => api.connectOrg(token, teamId, input.trim()))}
                >
                  {busy ? '확인 중…' : '등록'}
                </button>
              </div>
            )}
          </>
        )}

        {org && (
          <>
            <div className="sync-bar">
              <span className="badge badge-ok">{org}</span>
              <span className="sync-text">{selected.size}개 레포를 보고 있습니다</span>
            </div>

            {repos === null && <div className="empty">레포 목록 불러오는 중…</div>}
            {repos && repos.length === 0 && <div className="empty">이 오가니제이션에 레포가 없습니다.</div>}
            {repos && repos.length > 0 && (
              <div className="repo-list">
                {repos.map((r) => (
                  <label className={`repo-row ${selected.has(r.full_name) ? 'on' : ''}`} key={r.full_name}>
                    <input
                      type="checkbox"
                      disabled={!isLeader}
                      checked={selected.has(r.full_name)}
                      onChange={(e) => {
                        const next = new Set(selected)
                        if (e.target.checked) next.add(r.full_name)
                        else next.delete(r.full_name)
                        setSelected(next)
                        run(() => api.selectRepos(token, teamId, [...next]))
                      }}
                    />
                    <span className="repo-name">{r.full_name.split('/')[1]}</span>
                    {r.private && <span className="badge badge-warn">비공개</span>}
                    <span className="repo-desc">{r.description || ''}</span>
                  </label>
                ))}
              </div>
            )}
          </>
        )}

        {error && <div className="field-err">{error}</div>}
      </div>
    </section>
  )
}
