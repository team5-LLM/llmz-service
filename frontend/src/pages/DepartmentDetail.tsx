import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import DateFilter from '../components/common/DateFilter'
import DepartmentDropdown from '../components/common/DepartmentDropdown'
import KpiCard from '../components/common/KpiCard'
import WorkTypeChart from '../components/department/WorkTypeChart'
import RecommendationList from '../components/department/RecommendationList'
import { getDashboardDepartments, getDepartmentDetail, getRecommendationsByDepartment } from '../api'
import type { DepartmentStat, Recommendation } from '../api/types'
import EmptyChart from '../components/common/EmptyChart'

const formatTokens = (value: number) => {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return value.toString()
}

const DepartmentDetail = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const dept  = searchParams.get('dept')
  const month = searchParams.get('month') ?? undefined

  const [allDepts, setAllDepts] = useState<DepartmentStat[]>([])
  const [overview, setOverview] = useState({ total_tokens: 0, total_cost: 0, user_count: 0, task_distribution: [] as { label: string; count: number; ratio: number }[] })
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])

  // 드롭다운 목록: month가 바뀔 때
  useEffect(() => {
    getDashboardDepartments(month)
      .then((res) => setAllDepts(res.department_stats))
      .catch(console.error)
  }, [month])

  // 부서 상세 + 추천: dept 또는 month가 바뀔 때
  useEffect(() => {
    const target = dept ?? allDepts[0]?.department
    if (!target) return

    getDepartmentDetail(target, month)
      .then((res) => {
        // 백엔드 응답: { overview: { total_tokens, total_cost, user_count }, tasks_by_priority }
        setOverview({
          total_tokens: res.overview.total_tokens,
          total_cost: res.overview.total_cost,
          user_count: res.overview.user_count,
          task_distribution: (res.tasks_by_priority ?? []).map((t: { task_label: string; count: number; ratio: number }) => ({
            label: t.task_label,
            count: t.count,
            ratio: t.ratio / 100,  // tasks_by_priority ratio는 0~100 단위 → 0~1로 변환
          })),
        })
      })
      .catch(console.error)

    getRecommendationsByDepartment(target, month)
      .then((res) => setRecommendations(res.recommendations))
      .catch(console.error)
  }, [dept, month, allDepts])

  const kpiData = [
    { label: '사용량', value: formatTokens(overview.total_tokens) },
    { label: '비용', value: `₩${overview.total_cost.toLocaleString()}` },
    { label: '사용자 수', value: `${overview.user_count}명` },
  ]

  return (
    <div className="flex flex-col gap-[30px]">
      <div className="flex flex-row justify-between items-center">
        <DepartmentDropdown data={allDepts} />
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
        {kpiData.map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </div>

      {/* 업무 유형 차트 */}
      <div className="bg-white rounded-lg p-4">
        <h2 className="font-bold text-lg text-black mb-6">업무 유형</h2>
        {overview.task_distribution.length === 0
          ? <EmptyChart />
          : <WorkTypeChart data={overview.task_distribution} />
        }
      </div>

      {/* 자동화 추천 리스트 */}
      <h1 className="font-bold text-xxl text-black">자동화 추천 리스트</h1>
      <div className="grid grid-cols-3 gap-[30px]">
        {recommendations.length === 0
          ? <EmptyChart height={200} message="추천 데이터가 없습니다" />
          : <RecommendationList data={recommendations} />
        }
      </div>
    </div>
  )
}

export default DepartmentDetail
