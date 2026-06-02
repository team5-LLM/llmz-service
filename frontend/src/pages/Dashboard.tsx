import { useCallback, useEffect, useState } from 'react'
import DateFilter from '../components/common/DateFilter'
import KpiCard from '../components/common/KpiCard'
import DepartmentWorkTypeChart from '../components/dashboard/DepartmentWorkTypeChart'
import type { DepartmentStat, Summary } from '../api/types'
import { getDashboardDepartments, getDashboardSummary } from '../api'
import TokenDonutChart from '../components/dashboard/TokenDonutChart'
import RiskBarChart from '../components/dashboard/RiskBarChart'

const formatTokens = (value: number) => {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return value.toString()
}

const getSummaryKpiData = (summary: Summary) => [
  { label: '총 분석 프롬프트 수', value: summary.total_logs.toLocaleString() },
  { label: '총 토큰 사용량', value: formatTokens(summary.total_tokens) },
  { label: '총 비용', value: `₩${Math.round(summary.total_cost).toLocaleString()}` },
]

const formatMonth = (year: number, month: number) =>
  `${year}-${String(month).padStart(2, '0')}`

const emptySummary: Summary = {
  total_logs: 0,
  departments: 0,
  total_tokens: 0,
  total_cost: 0,
  avg_risk_score: 0,
}

const Dashboard = () => {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [summary, setSummary] = useState<Summary>(emptySummary)
  const [deptStats, setDeptStats] = useState<DepartmentStat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadDashboard = useCallback(async (y: number, m: number) => {
    setLoading(true)
    setError('')
    const monthParam = formatMonth(y, m)
    try {
      const [summaryRes, deptRes] = await Promise.all([
        getDashboardSummary(monthParam),
        getDashboardDepartments(monthParam),
      ])
      setSummary(summaryRes.summary)
      setDeptStats(deptRes.department_stats)
    } catch (err) {
      setSummary(emptySummary)
      setDeptStats([])
      setError(
        err instanceof Error
          ? err.message
          : '대시보드 데이터를 불러오지 못했습니다. 백엔드가 실행 중인지 확인하세요.',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard(year, month)
  }, [year, month, loadDashboard])

  const handleDateChange = (y: number, m: number) => {
    setYear(y)
    setMonth(m)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-row justify-between">
        <h1 className="font-bold text-xxl text-black">Dashboard</h1>
        <DateFilter onChange={handleDateChange} />
      </div>

      {error && (
        <p className="text-sm text-secondary bg-white rounded-lg p-4">{error}</p>
      )}

      {loading && !error && (
        <p className="text-sm text-center py-4" style={{ color: 'var(--color-gray-500)' }}>
          데이터 불러오는 중...
        </p>
      )}

      {/* KPI 카드 */}
      <div className="grid grid-cols-3 gap-4">
        {getSummaryKpiData(summary).map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </div>

      {/* 부서별 업무 유형 그래프 */}
      <div className="bg-white rounded-lg p-4">
        <div className="flex justify-between items-center mb-6">
          <h2 className="font-bold text-lg text-black">부서별 업무 유형</h2>
        </div>
        {deptStats.length > 0 ? (
          <DepartmentWorkTypeChart data={deptStats} />
        ) : (
          !loading && (
            <p className="text-sm text-center py-8" style={{ color: 'var(--color-gray-500)' }}>
              해당 기간 부서 데이터가 없습니다. CSV 업로드 후 다시 선택해 보세요.
            </p>
          )
        )}
      </div>

      {/* 부서별 사용량 & 평균 위험도 */}
      <div className="flex flex-row gap-6">
        <div className="bg-white rounded-lg p-4 w-1/2">
          <div className="flex justify-between items-center mb-6">
            <h2 className="font-bold text-lg text-black">부서별 사용량</h2>
          </div>
          {deptStats.length > 0 ? (
            <TokenDonutChart data={deptStats} />
          ) : (
            !loading && (
              <p className="text-sm text-center py-8" style={{ color: 'var(--color-gray-500)' }}>
                데이터 없음
              </p>
            )
          )}
        </div>
        <div className="bg-white rounded-lg p-4 w-1/2">
          <div className="flex justify-between items-center mb-6">
            <h2 className="font-bold text-lg text-black">부서별 평균 위험도</h2>
          </div>
          {deptStats.length > 0 ? (
            <RiskBarChart data={deptStats} />
          ) : (
            !loading && (
              <p className="text-sm text-center py-8" style={{ color: 'var(--color-gray-500)' }}>
                데이터 없음
              </p>
            )
          )}
        </div>
      </div>
    </div>
  )
}

export default Dashboard
