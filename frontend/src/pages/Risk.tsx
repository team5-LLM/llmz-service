import { useEffect, useState } from 'react'
import { getRiskOverview } from '../api'
import type { DepartmentRiskWithBreakdown, RiskLevel } from '../api/types'
import KpiCard from '../components/common/KpiCard'
import DateFilter from '../components/common/DateFilter'
import { useSearchParams } from 'react-router-dom'
import { useMonthParam } from '../hooks/useMonthParam'
import EmptyChart from '../components/common/EmptyChart'
import RiskTable from '../components/recommendation/RiskTable'
import RiskGradeBarChart, { type RiskGradeChartItem } from '../components/recommendation/RiskGradeBarChart'

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


const Risk = () => {
  const [allDepts, setAllDepts] = useState<DepartmentRiskWithBreakdown[]>([])
  const [criticalCount, setCriticalCount] = useState(0)
  const [highCount, setHighCount] = useState(0)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [, setSearchParams] = useSearchParams()

  const month = useMonthParam()

  useEffect(() => {
    if (!month) return

    let cancelled = false
    setLoading(true)
    setAllDepts([])
    setError('')

    getRiskOverview(month)
      .then((overview) => {
        if (!cancelled) {
          setAllDepts(overview.all_departments)
          setCriticalCount(overview.summary.critical_count)
          setHighCount(overview.summary.high_count + overview.summary.critical_count)
        }
      })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [month])

  const GRADES = ['Low', 'Medium', 'High', 'Critical'] as const
  const total = allDepts.length || 1
  const riskChartData: RiskGradeChartItem[] = GRADES.map((grade) => ({
    grade,
    ratio: Math.round((allDepts.filter(d => d.risk_level === grade).length / total) * 100),
  }))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="font-bold text-xxl text-black">위험도 개요</h1>
        <DateFilter
          value={month}
          onChange={(year, month) => {
            setSearchParams((prev) => {
              prev.set('month', `${year}-${String(month).padStart(2, '0')}`)
              return prev
            })
          }}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <KpiCard label="Critical 부서" value={`${criticalCount}개`} />
        <KpiCard label="High 이상 부서" value={`${highCount}개`} />
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
          {allDepts.map(dept => {
            const ls = levelStyle[dept.risk_level]
            const bars = dept.sensitive_breakdown
              .slice(0, 5)
              .map((item, i) => ({ ratio: item.ratio, color: BAR_COLORS[i] }))
              .sort((a, b) => b.ratio - a.ratio)
            return (
              <div key={dept.department} className="flex items-center gap-4">
                <span className="text-sm text-black w-28 shrink-0">{dept.department}</span>
                <div className="flex-1 h-8 rounded-md overflow-hidden bg-bg">
                  <div
                    className="flex h-full overflow-hidden"
                    style={{ width: `${dept.avg_risk_score}%`, borderRadius: '0 6px 6px 0' }}
                  >
                    {bars.map(({ ratio, color }, i) => (
                      <div key={i} style={{ width: `${ratio}%`, backgroundColor: color }} />
                    ))}
                  </div>
                </div>
                <span className="text-sm font-bold text-black w-8 text-right shrink-0">
                  {dept.avg_risk_score}
                </span>
                <span
                  className="px-3 py-0.5 rounded-full text-xs font-medium w-16 text-center shrink-0"
                  style={{ backgroundColor: ls.bg, color: ls.color }}
                >
                  {dept.risk_level}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      <div className="flex flex-row gap-[30px]">
        <div className="bg-white rounded-lg p-4 w-1/2">
          <div className="flex justify-between items-center mb-6">
            <h2 className="font-bold text-lg text-black">위험도 등급</h2>
          </div>
          <RiskTable />
        </div>
        <div className="bg-white rounded-lg p-4 w-1/2">
          <div className="flex justify-between items-center mb-6">
            <h2 className="font-bold text-lg text-black">위험도 등급 분포</h2>
          </div>
          {allDepts.length === 0
            ? <EmptyChart />
            : <RiskGradeBarChart data={riskChartData} />
          }
        </div>
        
      </div>
    </div>
  )
}

export default Risk
