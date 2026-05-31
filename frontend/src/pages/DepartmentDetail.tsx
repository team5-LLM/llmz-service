import { useSearchParams } from 'react-router-dom'
import DateFilter from '../components/common/DateFilter'
import DepartmentDropdown from '../components/common/DepartmentDropdown'
import KpiCard from '../components/common/KpiCard'
import type { DepartmentStat } from '../api/types'

const dummyDeptStats: DepartmentStat[] = [
  { department: '마케팅팀',   total_requests: 100, total_tokens: 520000, total_cost: 156000, user_count: 12, avg_risk_score: 24, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '보고서 작성형', count: 72, ratio: 0.72 }, { label: '코드 생성형', count: 28, ratio: 0.28 }] },
  { department: '개발팀',     total_requests: 100, total_tokens: 980000, total_cost: 294000, user_count: 23, avg_risk_score: 18, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 47, ratio: 0.47 }, { label: '코드 생성형', count: 53, ratio: 0.53 }] },
  { department: '인사팀',     total_requests: 100, total_tokens: 310000, total_cost:  93000, user_count:  8, avg_risk_score: 12, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 51, ratio: 0.51 }, { label: '보고서 작성형', count: 49, ratio: 0.49 }] },
  { department: '고객지원팀', total_requests: 100, total_tokens: 430000, total_cost: 129000, user_count: 15, avg_risk_score: 45, risk_level: 'Medium', high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 65, ratio: 0.65 }, { label: '고객 응대형', count: 35, ratio: 0.35 }] },
  { department: '재무/기획팀',total_requests: 100, total_tokens: 760000, total_cost: 228000, user_count: 10, avg_risk_score: 72, risk_level: 'High',   high_critical_ratio: 0, task_distribution: [{ label: '고객 응대형', count: 59, ratio: 0.59 }, { label: '보고서 작성형', count: 41, ratio: 0.41 }] },
  { department: '영업팀',     total_requests: 100, total_tokens: 210000, total_cost:  63000, user_count: 18, avg_risk_score: 28, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '단순 검색/질문형', count: 83, ratio: 0.83 }, { label: '문서 요약형', count: 17, ratio: 0.17 }] },
]

const formatTokens = (value: number) => {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return value.toString()
}

const DepartmentDetail = () => {
  const [searchParams] = useSearchParams()
  const dept = searchParams.get('dept')
  const month = searchParams.get('month')

  const selectedDept = dummyDeptStats.find((d) => d.department === dept) ?? dummyDeptStats[0]

  const kpiData = [
    { label: '사용량',    value: formatTokens(selectedDept.total_tokens) },
    { label: '비용',      value: `₩${selectedDept.total_cost.toLocaleString()}` },
    { label: '사용자 수', value: `${selectedDept.user_count}명` },
  ]

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-row justify-between items-center">
        <DepartmentDropdown data={dummyDeptStats} />
        <DateFilter />
      </div>

      {/* KPI 카드 */}
      <div className="grid grid-cols-3 gap-4">
        {kpiData.map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </div>
    </div>
  )
}

export default DepartmentDetail
