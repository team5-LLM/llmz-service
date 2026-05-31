import { useSearchParams } from 'react-router-dom'
import DepartmentDropdown from '../components/common/DepartmentDropdown'
import DateFilter from '../components/common/DateFilter'
import type { DepartmentStat } from '../api/types'

const dummyDeptStats: DepartmentStat[] = [
  { department: '마케팅팀',   total_requests: 100, total_tokens: 520000, total_cost: 0, user_count: 0, avg_risk_score: 24, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '보고서 작성형', count: 72, ratio: 0.72 }, { label: '코드 생성형', count: 28, ratio: 0.28 }] },
  { department: '개발팀',     total_requests: 100, total_tokens: 980000, total_cost: 0, user_count: 0, avg_risk_score: 18, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 47, ratio: 0.47 }, { label: '코드 생성형', count: 53, ratio: 0.53 }] },
  { department: '인사팀',     total_requests: 100, total_tokens: 310000, total_cost: 0, user_count: 0, avg_risk_score: 12, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 51, ratio: 0.51 }, { label: '보고서 작성형', count: 49, ratio: 0.49 }] },
  { department: '고객지원팀', total_requests: 100, total_tokens: 430000, total_cost: 0, user_count: 0, avg_risk_score: 45, risk_level: 'Medium', high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 65, ratio: 0.65 }, { label: '고객 응대형', count: 35, ratio: 0.35 }] },
  { department: '재무/기획팀',total_requests: 100, total_tokens: 760000, total_cost: 0, user_count: 0, avg_risk_score: 72, risk_level: 'High',   high_critical_ratio: 0, task_distribution: [{ label: '고객 응대형', count: 59, ratio: 0.59 }, { label: '보고서 작성형', count: 41, ratio: 0.41 }] },
  { department: '영업팀',     total_requests: 100, total_tokens: 210000, total_cost: 0, user_count: 0, avg_risk_score: 28, risk_level: 'Low',    high_critical_ratio: 0, task_distribution: [{ label: '단순 검색/질문형', count: 83, ratio: 0.83 }, { label: '문서 요약형', count: 17, ratio: 0.17 }] },
]


const Recommendation = () => {
  const [searchParams] = useSearchParams()
  const dept = searchParams.get('dept')
  const month = searchParams.get('month')

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-row justify-between items-center">
        <div className="flex items-center gap-2">
          <DepartmentDropdown data={dummyDeptStats} />
          <h1 className="font-bold text-xxl text-black">자동화 추천</h1>
        </div>
        <DateFilter />
      </div>
    </div>
  )
}

export default Recommendation
