import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import DepartmentDropdown from '../components/common/DepartmentDropdown'
import DateFilter from '../components/common/DateFilter'
import type { DepartmentStat, Recommendation } from '../api/types'
import RecommendationDetailList from '../components/recommendation/RecommendationDetailList'
import InfoBox from '../components/recommendation/InfoBox'
import { getDashboardDepartments, getRecommendationsByDepartment } from '../api'
import EmptyChart from '../components/common/EmptyChart'

const Recommendation = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const dept  = searchParams.get('dept')
  const month = searchParams.get('month') ?? undefined

  const [allDepts, setAllDepts] = useState<DepartmentStat[]>([])
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])

  // 드롭다운 목록
  useEffect(() => {
    getDashboardDepartments(month)
      .then((res) => setAllDepts(res.department_stats))
      .catch(console.error)
  }, [month])

  // 추천 데이터: dept 또는 allDepts가 바뀔 때
  useEffect(() => {
    const target = dept ?? allDepts[0]?.department
    if (!target) return
    getRecommendationsByDepartment(target, month)
      .then((res) => setRecommendations(res.recommendations))
      .catch(console.error)
  }, [dept, month, allDepts])

  return (
    <div className="flex flex-col gap-[30px]">
      <div className="flex flex-row justify-between items-center">
        <div className="flex items-center gap-2">
          <DepartmentDropdown data={allDepts} />
          <h1 className="font-bold text-xxl text-black">자동화 추천</h1>
        </div>
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
      <div className="flex flex-row gap-1">
        <span className="text-md text-primary">Opportunity Score가 높더라도 Risk Score가 높으면 ‘자동화 우선’이 아니라 ‘보안 검토 필요’로 분류합니다.</span>
        <InfoBox content={"Opportunity Score: 반복 사용 패턴과 업무 유형을 분석하여 자동화 효과를 예측한 점수\nRisk Score: 개인정보, 고객정보, 기밀정보 등의 포함 가능성을 분석한 위험도 점수"} />
      </div>
      <div className="grid grid-cols-3 gap-[30px]">
        {recommendations.length === 0
          ? <EmptyChart height={200} message="추천 데이터가 없습니다" />
          : <RecommendationDetailList data={recommendations} />
        }
      </div>
    </div>
  )
}

export default Recommendation
