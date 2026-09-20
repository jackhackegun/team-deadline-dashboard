import { gaugeColor } from './dashboardMath'

export default function Gauge({ percent, large }) {
  return (
    <div
      className={`gauge${large ? ' gauge-lg' : ''}`}
      data-label={`${percent}%`}
      style={{ background: `conic-gradient(${gaugeColor(percent)} calc(${percent}*3.6deg), var(--track) 0)` }}
    />
  )
}
