import { useState } from 'react'

// 초대코드 표시 + 복사. 팀 목록 카드와 팀 안 설정 탭이 같은 것을 쓴다
export default function InviteCode({ teamName, code, onClick }) {
  const [state, setState] = useState(null) // 'ok' | 'fail' | null

  async function copy(e) {
    e.stopPropagation()
    onClick?.(e)
    // await 뒤에는 e.currentTarget이 비므로 지금 붙잡아 둔다
    const button = e.currentTarget
    let ok = false
    try {
      await navigator.clipboard.writeText(`[${teamName}] 팀에 초대합니다. 초대코드: ${code}`)
      ok = true
    } catch {
      // http 환경이나 권한 거부 — 됐다고 거짓말하지 않고 코드를 선택해 둔다
      const el = button?.querySelector?.('code')
      if (el) window.getSelection()?.selectAllChildren(el)
    }
    setState(ok ? 'ok' : 'fail')
    setTimeout(() => setState(null), 2000)
  }

  return (
    <button type="button" className="tc-invite" onClick={copy} title="초대 문구를 클립보드에 복사">
      <code>{code}</code>
      <span>{state === 'ok' ? '복사됨' : state === 'fail' ? '복사 안 됨 — 직접 복사하세요' : '초대코드 복사'}</span>
    </button>
  )
}
