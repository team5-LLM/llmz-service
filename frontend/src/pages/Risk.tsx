import { useEffect, useState } from 'react'
import { analyzeSample } from '../api'
import type { DepartmentStat, RiskLevel } from '../api/types'
import KpiCard from '../components/common/KpiCard'

const levelStyle: Record<RiskLevel, { bg: string; color: string }> = {
  Low:      { bg: 'var(--color-risk-low)', color: '#2d6a2d' },
  Medium:   { bg: 'var(--color-risk-medium)', color: '#856c00' },
  High:     { bg: 'var(--color-risk-high)', color: '#8b0000' },
  Critical: { bg: 'var(--color-risk-critical)', color: '#4b0082' },
}

const legendItems = [
  { label: '개인정보', color: 'var(--color-chart-pink)' },
  { label: '고객정보', color: 'var(--color-chart-coral)' },
  { label: '기밀정보', color: 'var(--color-chart-green)' },
  { label: '소스코드', color: 'var(--color-chart-blue)' },
  { label: '재무/법무', color: 'var(--color-chart-purple)' },
]

const BAR_COLORS = [
  'var(--color-chart-pink)',
  'var(--color-chart-coral)',
  'var(--color-chart-green)',
  'var(--color-chart-blue)',
  'var(--color-chart-purple)',
]

function deriveBars(stat: DepartmentStat): { ratio: number; color: string }[] {
  const dist = stat.task_distribution
  const ratios = dist.slice(0, 5).map(t => t.ratio)
  while (ratios.length < 5) ratios.push(0)
  const sum = ratios.reduce((a, b) => a + b, 0)
  const normalized = sum > 0 ? ratios.map(r => (r / sum) * 100) : [20, 20, 20, 20, 20]
  return normalized
    .map((ratio, i) => ({ ratio, color: BAR_COLORS[i] }))
    .sort((a, b) => b.ratio - a.ratio)
}

const Risk = () => {
  const [stats, setStats] = useState<DepartmentStat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    analyzeSample()
      .then(result => setStats(result.department_stats))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const criticalDepts = stats.filter(d => d.risk_level === 'Critical')
  const highDepts = stats.filter(d => d.risk_level === 'High' || d.risk_level === 'Critical')

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="font-bold text-xxl text-black">위험도 개요</h1>
        <button className="flex items-center gap-2 border border-gray-100 rounded-md px-4 py-2 text-sm bg-white">
          <span className="material-symbols-outlined text-base leading-none" style={{ color: 'var(--color-gray-500)' }}>
            calendar_month
          </span>
          <span style={{ color: 'var(--color-gray-500)' }}>2026년 5월</span>
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <KpiCard label="Critical 부서" value={`${criticalDepts.length}개`} />
        <KpiCard label="High 이상 부서" value={`${highDepts.length}개`} />
      </div>

      <div className="bg-white rounded-lg p-6">
        <div className="flex justify-between items-center mb-6">
          <h2 className="font-bold text-lg text-black">부서별 Risk Score</h2>
          <div className="flex gap-4">
            {legendItems.map(({ label, color }) => (
              <div key={label} className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-xs" style={{ color: 'var(--color-gray-500)' }}>{label}</span>
              </div>
            ))}
          </div>
        </div>

        {loading && (
          <p className="text-sm text-center py-8" style={{ color: 'var(--color-gray-500)' }}>데이터 불러오는 중...</p>
        )}
        {error && (
          <p className="text-sm text-center py-8 text-secondary">{error}</p>
        )}

        <div className="flex flex-col gap-5">
          {stats.map(stat => {
            const ls = levelStyle[stat.risk_level]
            const bars = deriveBars(stat)
            return (
              <div key={stat.department} className="flex items-center gap-4">
                <span className="text-sm text-black w-28 shrink-0">{stat.department}</span>
                <div className="flex-1 h-8 rounded-md overflow-hidden bg-bg">
                  <div
                    className="flex h-full overflow-hidden"
                    style={{ width: `${stat.avg_risk_score}%`, borderRadius: '0 6px 6px 0' }}
                  >
                    {bars.map(({ ratio, color }, i) => (
                      <div key={i} style={{ width: `${ratio}%`, backgroundColor: color }} />
                    ))}
                  </div>
                </div>
                <span className="text-sm font-bold text-black w-8 text-right shrink-0">
                  {stat.avg_risk_score}
                </span>
                <span
                  className="px-3 py-0.5 rounded-full text-xs font-medium w-16 text-center shrink-0"
                  style={{ backgroundColor: ls.bg, color: ls.color }}
                >
                  {stat.risk_level}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default Risk
