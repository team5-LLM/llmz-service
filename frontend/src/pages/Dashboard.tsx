import DateFilter from '../components/common/DateFilter'
import KpiCard from '../components/common/KpiCard'
import DepartmentWorkTypeChart from '../components/dashboard/DepartmentWorkTypeChart'
import type { DepartmentStat, Summary } from '../api/types'
import TokenDonutChart from '../components/dashboard/TokenDonutChart'
import RiskBarChart from '../components/dashboard/RiskBarChart'
import EmptyChart from '../components/common/EmptyChart'
import { useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { getDashboardDepartments, getDashboardSummary } from '../api'

const Dashboard = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const month = searchParams.get('month') ?? undefined

  const [summary, setSummary] = useState<Summary>({
    total_logs: 0,
    departments: 0,
    total_tokens: 0,
    total_cost: 0,
    avg_risk_score: 0,
  })
  const [deptStats, setDeptStats] = useState<DepartmentStat[]>([])

  useEffect(() => {
    getDashboardSummary(month).then((res) => setSummary(res.summary)).catch(console.error)
    getDashboardDepartments(month).then((res) => setDeptStats(res.department_stats)).catch(console.error)
  }, [month])

  const formatTokens = (value: number) => {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
    return value.toString()
  }

  const getSummaryKpiData = (summary: Summary) => [
    { label: '총 분석 프롬프트 수', value: summary.total_logs.toLocaleString() },
    { label: '총 토큰 사용량', value: formatTokens(summary.total_tokens) },
    { label: '총 비용', value: `₩${summary.total_cost.toLocaleString()}` },
  ]

  return (
    <div className="flex flex-col gap-[30px]">
      <div className="flex flex-row justify-between">
        <h1 className="font-bold text-xxl text-black">Dashboard</h1>
        {/* 날짜 필터 */}
        <DateFilter
          onChange={(year, month) => {
            setSearchParams((prev) => {
              prev.set('month', `${year}-${String(month).padStart(2, '0')}`)
              return prev
            })
          }}
        />
      </div>

      {/* KPI 카드 */}
      <div className="grid grid-cols-3 gap-[30px]">
        {getSummaryKpiData(summary).map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </div>

      {/* 부서별 업무 유형 그래프 */}
      <div className="bg-white rounded-lg p-4">
        <div className="flex justify-between items-center mb-[30px]">
          <h2 className="font-bold text-lg text-black">부서별 업무 유형</h2>
        </div>
        {deptStats.length === 0
          ? <EmptyChart />
          : <DepartmentWorkTypeChart data={deptStats} />
        }
      </div>

      {/* 부서별 사용량 & 평균 위험도 */}
      <div className="flex flex-row gap-[30px]">
        <div className="bg-white rounded-lg p-4 w-1/2">
          <div className="flex justify-between items-center mb-[30px]">
            <h2 className="font-bold text-lg text-black">부서별 사용량</h2>
          </div>
          {deptStats.length === 0
            ? <EmptyChart />
            : <TokenDonutChart data={deptStats} />
          }
        </div>
        <div className="bg-white rounded-lg p-4 w-1/2">
          <div className="flex justify-between items-center mb-[30px]">
            <h2 className="font-bold text-lg text-black">부서별 평균 위험도</h2>
          </div>
          {deptStats.length === 0
            ? <EmptyChart />
            : <RiskBarChart data={deptStats} />
          }
        </div>
      </div>
      
    </div>
  )
};

export default Dashboard
