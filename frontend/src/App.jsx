import { useEffect, useState } from 'react'
import Login from './Login'
import Signup from './Signup'
import Teams from './Teams'
import Dashboard from './Dashboard'
import { api, onUnauthorized } from './api'

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [screen, setScreen] = useState(token ? 'teams' : 'login')
  const [username, setUsername] = useState('')
  const [currentTeamId, setCurrentTeamId] = useState(null)

  // 로그인하면 항상 팀 목록부터 보여준다. 팀이 하나여도 건너뛰지 않는다 —
  // 어느 팀에 들어가는지 스스로 고르는 편이 예측 가능하다
  function handleAuthed(accessToken, name) {
    localStorage.setItem('token', accessToken)
    setToken(accessToken)
    setUsername(name)
    setScreen('teams')
  }

  function handleLogout() {
    localStorage.removeItem('token')
    setToken(null)
    setCurrentTeamId(null)
    setScreen('login')
  }

  // 토큰 만료/무효화로 401을 받으면 어느 화면에 있든 로그인 화면으로 돌려보낸다
  useEffect(() => { onUnauthorized(handleLogout) }, [])

  // 새로고침하면 로그인 때 받은 이름이 사라진다 — 토큰이 남아 있으면 서버에서 되찾는다
  useEffect(() => {
    if (token && !username) api.getMe(token).then((me) => setUsername(me.name)).catch(() => {})
  }, [token, username])

  if (screen === 'login') {
    return (
      <Login
        onLogin={async (email, password) => {
          const { access_token } = await api.login(email, password)
          handleAuthed(access_token, email.split('@')[0])
        }}
        onGotoSignup={() => setScreen('signup')}
      />
    )
  }
  if (screen === 'signup') {
    return (
      <Signup
        onSignup={async (name, email, password) => {
          const { access_token } = await api.signup(email, password, name)
          handleAuthed(access_token, name)
        }}
        onGotoLogin={() => setScreen('login')}
      />
    )
  }
  if (screen === 'teams') {
    return (
      <Teams
        token={token}
        username={username}
        onOpenTeam={(id) => { setCurrentTeamId(id); setScreen('dashboard') }}
        onLogout={handleLogout}
      />
    )
  }
  return (
    <Dashboard
      token={token}
      teamId={currentTeamId}
      username={username}
      onBack={() => setScreen('teams')}
      onLogout={handleLogout}
    />
  )
}
