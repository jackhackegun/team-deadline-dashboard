export default function Navbar({ brand, backLabel, onBack, username, onLogout }) {
  const initial = (username || '?').trim().charAt(0)
  return (
    <header className="app-header">
      <div className="brand">
        {backLabel
          ? <span className="brand-back" onClick={onBack}>{backLabel}</span>
          : <span className="brand-mark">D</span>}
        <span className="brand-sep">{backLabel ? '/' : ''}</span>
        <span className="brand-title">{brand}</span>
      </div>
      <div className="nav-user">
        <span className="uname">{username}님</span>
        <span className="avatar" title={username}>{initial}</span>
        <button className="btn btn-ghost btn-sm" onClick={onLogout}>로그아웃</button>
      </div>
    </header>
  )
}
