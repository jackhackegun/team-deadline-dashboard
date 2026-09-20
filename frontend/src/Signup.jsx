import { useState } from 'react'

// POST /auth/signup
export default function Signup({ onSignup, onGotoLogin }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!name || !email || !password) { setError('모든 항목을 입력하세요.'); return }
    setError('')
    try {
      await onSignup(name, email, password)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="auth-hero">
      <div className="logo"><span className="brand-mark">D</span> Deadline Dashboard</div>
      <span className="pill-badge"><span className="dot" /> 무료로 시작 · Beta</span>
      <h1 className="auth-title">팀을 만들고<br />첫 마감을 등록하세요.</h1>
      <p className="auth-lead">계정을 만들면 바로 팀을 초대하고 진행률을 공유할 수 있어요.</p>

      <div className="auth-card">
        <h2>회원가입</h2>
        <p className="sub">30초면 시작할 수 있습니다.</p>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>이름</label>
            <input placeholder="홍길동" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="field">
            <label>이메일</label>
            <input type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="field">
            <label>비밀번호</label>
            <input type="password" placeholder="8자 이상" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <div className="field-err">{error}</div>
          </div>
          <button className="btn btn-primary btn-block">회원가입</button>
          <div className="auth-switch">이미 계정이 있으신가요? <a onClick={onGotoLogin}>로그인</a></div>
        </form>
      </div>
    </div>
  )
}
