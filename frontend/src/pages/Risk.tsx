import { useEffect, useMemo, useState } from 'react'
import { getRiskDepartmentDetail, getRiskLevels, getRiskOverview } from '../api'
import type {
  RiskLevel,
  RiskLevelDefinition,
  RiskOverviewResponse,
  SensitiveBreakdownItem,
  SensitiveCategory,
} from '../api/types'
import KpiCard from '../components/common/KpiCard'
import DateFilter from '../components/common/DateFilter'
import { useSearchParams } from 'react-router-dom'
import RiskTable from '../components/recommendation/RiskTable'
import EmptyChart from '../components/common/EmptyChart'
import RiskGradeBarChart, { type RiskGradeChartItem } from '../components/recommendation/RiskGradeBarChart'

const levelStyle: Record<RiskLevel, { bg: string; color: string }> = {
  Low:      { bg: 'var(--color-risk-low)', color: '#2d6a2d' },
  Medium:   { bg: 'var(--color-risk-medium)', color: '#856c00' },
  High:     { bg: 'var(--color-risk-high)', color: '#8b0000' },
  Critical: { bg: 'var(--color-risk-critical)', color: '#4b0082' },
}

const LEGEND_ITEMS: { category: SensitiveCategory; label: string; color: string }[] = [
  { category: 'personal_info', label: '개인정보', color: 'var(--color-chart-pink)' },
  { category: 'customer_info', label: '고객정보', color: 'var(--color-chart-coral)' },
  { category: 'confidential', label: '기밀정보', color: 'var(--color-chart-green)' },
  { category: 'source_code', label: '소스코드', color: 'var(--color-chart-blue)' },
  { category: 'finance_legal', label: '재무/법무', color: 'var(--color-chart-purple)' },
]

const CATEGORY_COLORS = Object.fromEntries(
  LEGEND_ITEMS.map((item) => [item.category, item.color]),
) as Record<SensitiveCategory, string>

type DeptRiskRow = {
  department: string
  risk_score: number
  risk_level: RiskLevel
  sensitive_breakdown: SensitiveBreakdownItem[]
}

function breakdownToBars(breakdown: SensitiveBreakdownItem[]): { ratio: number; color: string }[] {
  const byCategory = Object.fromEntries(breakdown.map((item) => [item.category, item])) as Partial<
    Record<SensitiveCategory, SensitiveBreakdownItem>
  >

  const bars = LEGEND_ITEMS.map(({ category }) => ({
    ratio: byCategory[category]?.ratio ?? 0,
    color: CATEGORY_COLORS[category],
  }))

  const sum = bars.reduce((acc, bar) => acc + bar.ratio, 0)
  if (sum <= 0) {
    return bars.map((bar) => ({ ...bar, ratio: 20 }))
  }

  return bars
}

const Risk = () => {
  const [overview, setOverview] = useState<RiskOverviewResponse | null>(null)
  const [deptRows, setDeptRows] = useState<DeptRiskRow[]>([])
  const [riskLevels, setRiskLevels] = useState<RiskLevelDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const [levelsLoading, setLevelsLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchParams, setSearchParams] = useSearchParams()

  const month = searchParams.get('month') ?? undefined

  useEffect(() => {
    let cancelled = false

    const loadLevels = async () => {
      setLevelsLoading(true)
      try {
        const data = await getRiskLevels()
        if (!cancelled) setRiskLevels(data.levels)
      } catch {
        if (!cancelled) setRiskLevels([])
      } finally {
        if (!cancelled) setLevelsLoading(false)
      }
    }

    void loadLevels()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError('')

      try {
        const overviewData = await getRiskOverview(month)
        if (cancelled) return

        const departments = overviewData.all_departments
        const details = await Promise.all(
          departments.map(async (dept) => {
            try {
              return await getRiskDepartmentDetail(dept.department, month)
            } catch {
              return {
                department: dept.department,
                period: overviewData.period,
                risk_score: dept.avg_risk_score,
                risk_level: dept.risk_level,
                high_critical_ratio: 0,
                sensitive_breakdown: [] as SensitiveBreakdownItem[],
              }
            }
          }),
        )

        if (cancelled) return

        setOverview(overviewData)
        setDeptRows(
          details
            .map((detail) => ({
              department: detail.department,
              risk_score: detail.risk_score,
              risk_level: detail.risk_level,
              sensitive_breakdown: detail.sensitive_breakdown,
            }))
            .sort((a, b) => b.risk_score - a.risk_score),
        )
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '데이터를 불러오지 못했습니다.')
          setOverview(null)
          setDeptRows([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [month])

  const riskChartData: RiskGradeChartItem[] = useMemo(() => {
    if (!overview) return []

    const { critical_count, high_count, medium_count, low_count, total_departments } =
      overview.summary
    const total = total_departments || 1

    const counts: Record<RiskLevel, number> = {
      Low: low_count,
      Medium: medium_count,
      High: high_count,
      Critical: critical_count,
    }

    return (['Low', 'Medium', 'High', 'Critical'] as const).map((grade) => ({
      grade,
      ratio: Math.round((counts[grade] / total) * 100),
    }))
  }, [overview])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="font-bold text-xxl text-black">위험도 개요</h1>
        <DateFilter
          onChange={(year, monthValue) => {
            setSearchParams((prev) => {
              prev.set('month', `${year}-${String(monthValue).padStart(2, '0')}`)
              return prev
            })
          }}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <KpiCard label="Critical 부서" value={`${overview?.summary.critical_count ?? 0}개`} />
        <KpiCard label="High 이상 부서" value={`${overview?.summary.high_count ?? 0}개`} />
      </div>

      <div className="bg-white rounded-lg p-6">
        <div className="flex justify-between items-center mb-6">
          <h2 className="font-bold text-lg text-black">부서별 Risk Score</h2>
          <div className="flex gap-4">
            {LEGEND_ITEMS.map(({ label, color }) => (
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

        {!loading && !error && deptRows.length === 0 && (
          <EmptyChart message="표시할 위험 부서가 없습니다" />
        )}

        <div className="flex flex-col gap-5">
          {deptRows.map((row) => {
            const ls = levelStyle[row.risk_level]
            const bars = breakdownToBars(row.sensitive_breakdown)
            return (
              <div key={row.department} className="flex items-center gap-4">
                <span className="text-sm text-black w-28 shrink-0">{row.department}</span>
                <div className="flex-1 h-8 rounded-md overflow-hidden bg-bg">
                  <div
                    className="flex h-full overflow-hidden"
                    style={{ width: `${row.risk_score}%`, borderRadius: '0 6px 6px 0' }}
                  >
                    {bars.map(({ ratio, color }, i) => (
                      <div key={i} style={{ width: `${ratio}%`, backgroundColor: color }} />
                    ))}
                  </div>
                </div>
                <span className="text-sm font-bold text-black w-8 text-right shrink-0">
                  {row.risk_score}
                </span>
                <span
                  className="px-3 py-0.5 rounded-full text-xs font-medium w-16 text-center shrink-0"
                  style={{ backgroundColor: ls.bg, color: ls.color }}
                >
                  {row.risk_level}
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
          <RiskTable levels={riskLevels} loading={levelsLoading} />
        </div>
        <div className="bg-white rounded-lg p-4 w-1/2">
          <div className="flex justify-between items-center mb-6">
            <h2 className="font-bold text-lg text-black">위험도 등급 분포</h2>
          </div>
          {!overview || overview.summary.total_departments === 0
            ? <EmptyChart />
            : <RiskGradeBarChart data={riskChartData} />
          }
        </div>
      </div>
    </div>
  )
}

export default Risk
