import { useState } from 'react'

// POST /auth/login
export default function Login({ onLogin, onGotoSignup }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!email || !password) { setError('이메일과 비밀번호를 입력하세요.'); return }
    setError('')
    try {
      await onLogin(email, password)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="auth-hero">
      <div className="logo"><span className="brand-mark">D</span> Deadline Dashboard</div>
      <span className="pill-badge"><span className="dot" /> 팀 마감 관리 · Beta</span>
      <h1 className="auth-title">팀의 마감을<br />한눈에, 놓치지 않게.</h1>
      <p className="auth-lead">진행률과 남은 마감을 실시간으로 공유하는 팀 프로젝트 대시보드.</p>

      <div className="auth-card">
        <h2>로그인</h2>
        <p className="sub">계정에 로그인해 팀 대시보드를 확인하세요.</p>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>이메일</label>
            <input type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="field">
            <label>비밀번호</label>
            <input type="password" placeholder="••••••••" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <div className="field-err">{error}</div>
          </div>
          <button className="btn btn-primary btn-block">로그인</button>
          <div className="auth-switch">계정이 없으신가요? <a onClick={onGotoSignup}>회원가입</a></div>
        </form>
      </div>
    </div>
  )
}
