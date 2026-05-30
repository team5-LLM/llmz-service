import DateFilter from '../components/common/DateFilter'
import KpiCard from '../components/common/KpiCard'
import DepartmentWorkTypeChart from '../components/dashboard/DepartmentWorkTypeChart'
import type { DepartmentStat, Summary } from '../api/types'
import TokenDonutChart from '../components/dashboard/TokenDonutChart'
import RiskBarChart from '../components/dashboard/RiskBarChart'

// 더미 데이터
const dummySummary: Summary = {
  total_logs: 12846,
  departments: 6,
  total_tokens: 3800000,
  total_cost: 482000,
  avg_risk_score: 68,
}

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

const dummyDeptStats: DepartmentStat[] = [
  { department: '마케팅팀',   total_requests: 100, total_tokens: 520000, total_cost: 0, user_count: 0, avg_risk_score: 24, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '보고서 작성형', count: 72, ratio: 0.72 }, { label: '코드 생성형', count: 28, ratio: 0.28 }] },
  { department: '개발팀',     total_requests: 100, total_tokens: 980000, total_cost: 0, user_count: 0, avg_risk_score: 18, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 47, ratio: 0.47 }, { label: '코드 생성형', count: 53, ratio: 0.53 }] },
  { department: '인사팀',     total_requests: 100, total_tokens: 310000, total_cost: 0, user_count: 0, avg_risk_score: 12, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 51, ratio: 0.51 }, { label: '보고서 작성형', count: 49, ratio: 0.49 }] },
  { department: '고객지원팀', total_requests: 100, total_tokens: 430000, total_cost: 0, user_count: 0, avg_risk_score: 45, risk_level: 'Medium', high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 65, ratio: 0.65 }, { label: '고객 응대형', count: 35, ratio: 0.35 }] },
  { department: '재무/기획팀',total_requests: 100, total_tokens: 760000, total_cost: 0, user_count: 0, avg_risk_score: 72, risk_level: 'High',   high_critical_ratio: 0, task_distribution: [{ label: '고객 응대형', count: 59, ratio: 0.59 }, { label: '보고서 작성형', count: 41, ratio: 0.41 }] },
  { department: '영업팀',     total_requests: 100, total_tokens: 210000, total_cost: 0, user_count: 0, avg_risk_score: 28, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '단순 검색/질문형', count: 83, ratio: 0.83 }, { label: '문서 요약형', count: 17, ratio: 0.17 }] },
]

const Dashboard = () => {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-row justify-between">
        <h1 className="font-bold text-xxl text-black">Dashboard</h1>
        <DateFilter />
      </div>

      {/* KPI 카드 */}
      <div className="grid grid-cols-3 gap-4">
        {getSummaryKpiData(dummySummary).map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </div>

      {/* 부서별 업무 유형 그래프 */}
      <div className="bg-white rounded-lg p-4">
        <div className="flex justify-between items-center mb-6">
          <h2 className="font-bold text-lg text-black">부서별 업무 유형</h2>
        </div>
        <DepartmentWorkTypeChart data={dummyDeptStats} />
      </div>

      {/* 부서별 사용량 & 평균 위험도 */}
      <div className="flex flex-row gap-6">
        <div className="bg-white rounded-lg p-4 w-1/2">
          <div className="flex justify-between items-center mb-6">
            <h2 className="font-bold text-lg text-black">부서별 사용량</h2>
          </div>
          <TokenDonutChart data={dummyDeptStats} />
        </div>
        <div className="bg-white rounded-lg p-4 w-1/2">
          <div className="flex justify-between items-center mb-6">
            <h2 className="font-bold text-lg text-black">부서별 평균 위험도</h2>
          </div>
          <RiskBarChart data={dummyDeptStats}/>
        </div>
      </div>
      
    </div>
  )
};

export default Dashboard
