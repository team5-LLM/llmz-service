import { useSearchParams } from 'react-router-dom'
import DateFilter from '../components/common/DateFilter'
import DepartmentDropdown from '../components/common/DepartmentDropdown'
import KpiCard from '../components/common/KpiCard'
import WorkTypeChart from '../components/department/WorkTypeChart'
import RecommendationList from '../components/department/RecommendationList'
import type { DepartmentStat, Recommendation } from '../api/types'

const dummyDeptStats: DepartmentStat[] = [
  { department: '마케팅팀', total_requests: 100, total_tokens: 520000, total_cost: 156000, user_count: 12, avg_risk_score: 24, risk_level: 'Low', high_critical_ratio: 0, task_distribution: [{ label: '보고서 작성형', count: 72, ratio: 0.72 }, { label: '코드 생성형', count: 28, ratio: 0.28 }] },
  { department: '개발팀', total_requests: 100, total_tokens: 980000, total_cost: 294000, user_count: 23, avg_risk_score: 18, risk_level: 'Low', high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 47, ratio: 0.47 }, { label: '코드 생성형', count: 53, ratio: 0.53 }] },
  { department: '인사팀', total_requests: 100, total_tokens: 310000, total_cost: 93000, user_count: 8, avg_risk_score: 12, risk_level: 'Low', high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 51, ratio: 0.51 }, { label: '보고서 작성형', count: 49, ratio: 0.49 }] },
  { department: '고객지원팀', total_requests: 100, total_tokens: 430000, total_cost: 129000, user_count: 15, avg_risk_score: 45, risk_level: 'Medium', high_critical_ratio: 0, task_distribution: [{ label: '문서 요약형', count: 65, ratio: 0.65 }, { label: '고객 응대형', count: 35, ratio: 0.35 }] },
  { department: '재무/기획팀', total_requests: 100, total_tokens: 760000, total_cost: 228000, user_count: 10, avg_risk_score: 72, risk_level: 'High', high_critical_ratio: 0, task_distribution: [{ label: '고객 응대형', count: 59, ratio: 0.59 }, { label: '보고서 작성형', count: 41, ratio: 0.41 }] },
  { department: '영업팀', total_requests: 100, total_tokens: 210000, total_cost: 63000, user_count: 18, avg_risk_score: 28, risk_level: 'Low', high_critical_ratio: 0, task_distribution: [{ label: '단순 검색/질문형', count: 83, ratio: 0.83 }, { label: '문서 요약형', count: 17, ratio: 0.17 }] },
]

const dummyRecommendations: Recommendation[] = [
  { department: '마케팅팀', task_label: '보고서 작성형', service_name: 'GPT 보고서 자동화', expected_effect: '작성 시간 60% 절감', difficulty: '하', required_resources: 'API 키', opportunity_score: 88, risk_score: 24, risk_level: 'Low', decision: '도입 권장', decision_level: 'green', decision_message: '즉시 도입 가능', required_action: '없음', reason: '마케팅팀에서 \'보고서 작성형\' 업무 비중이 41.4%로 나타났습니다.\n해당 업무유형을 사용한 사용자 수는 12명입니다.' },
  { department: '마케팅팀', task_label: '코드 생성형', service_name: 'Copilot 도입', expected_effect: '개발 생산성 향상', difficulty: '중', required_resources: '라이선스', opportunity_score: 65, risk_score: 30, risk_level: 'Low', decision: '보안 검토 필요', decision_level: 'yellow', decision_message: '팀 교육 필요', required_action: '교육 계획', reason: '사용 비율 낮음' },
  { department: '개발팀', task_label: '코드 생성형', service_name: 'Copilot 도입', expected_effect: '개발 속도 40% 향상', difficulty: '하', required_resources: '라이선스', opportunity_score: 92, risk_score: 18, risk_level: 'Low', decision: '도입 권장', decision_level: 'green', decision_message: '즉시 도입 가능', required_action: '라이선스 구매', reason: '코드 생성 비율 높음' },
  { department: '개발팀', task_label: '문서 요약형', service_name: 'Claude 요약 봇', expected_effect: '문서 처리 시간 절감', difficulty: '하', required_resources: 'API 키', opportunity_score: 75, risk_score: 20, risk_level: 'Low', decision: '도입 권장', decision_level: 'green', decision_message: '즉시 도입 가능', required_action: 'API 연동', reason: '문서 처리 빈번' },
  { department: '고객지원팀', task_label: '고객 응대형', service_name: '챗봇 자동화', expected_effect: '응대 시간 50% 절감', difficulty: '상', required_resources: '개발 인력', opportunity_score: 70, risk_score: 45, risk_level: 'Medium', decision: '보안 검토 필요', decision_level: 'yellow', decision_message: '보안 검토 필요', required_action: '보안 감사', reason: '고객 데이터 처리' },
  { department: '재무/기획팀', task_label: '고객 응대형', service_name: '재무 분석 AI', expected_effect: '분석 정확도 향상', difficulty: '상', required_resources: '전문 인력', opportunity_score: 60, risk_score: 72, risk_level: 'High', decision: '보류', decision_level: 'red', decision_message: '위험도 재검토', required_action: '위험 분석', reason: '민감 데이터 포함' },
  { department: '영업팀', task_label: '단순 검색/질문형', service_name: '영업 지원 봇', expected_effect: '정보 검색 시간 절감', difficulty: '하', required_resources: 'API 키', opportunity_score: 80, risk_score: 28, risk_level: 'Low', decision: '도입 권장', decision_level: 'green', decision_message: '즉시 도입 가능', required_action: 'API 연동', reason: '단순 반복 검색 많음' },
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
  const recommendations = dummyRecommendations.filter((r) => r.department === selectedDept.department)

  const kpiData = [
    { label: '사용량', value: formatTokens(selectedDept.total_tokens) },
    { label: '비용', value: `₩${selectedDept.total_cost.toLocaleString()}` },
    { label: '사용자 수', value: `${selectedDept.user_count}명` },
  ]

  return (
    <div className="flex flex-col gap-[30px]">
      <div className="flex flex-row justify-between items-center">
        <DepartmentDropdown data={dummyDeptStats} />
        <DateFilter />
      </div>

      {/* KPI 카드 */}
      <div className="grid grid-cols-3 gap-[30px]">
        {kpiData.map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </div>

      {/* 업무 유형 차트 */}
      <div className="bg-white rounded-lg p-4">
        <h2 className="font-bold text-lg text-black mb-6">업무 유형</h2>
        <WorkTypeChart data={selectedDept.task_distribution} />
      </div>

      {/* 자동화 추천 리스트 */}
      <h1 className="font-bold text-xxl text-black">자동화 추천 리스트</h1>
      <div className="grid grid-cols-3 gap-[30px]">
        <RecommendationList data={recommendations} />
      </div>
    </div>
  )
}

export default DepartmentDetail
