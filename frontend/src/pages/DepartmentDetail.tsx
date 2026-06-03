import { useState, useEffect, useMemo, useCallback } from 'react'
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

type OverviewState = {
  total_tokens: number
  total_cost: number
  user_count: number
  task_distribution: { label: string; count: number; ratio: number }[]
}

const emptyOverview: OverviewState = {
  total_tokens: 0,
  total_cost: 0,
  user_count: 0,
  task_distribution: [],
}

function parseMonthParam(month: string | null): { year: number; month: number } | null {
  const match = month?.match(/^(\d{4})-(\d{2})$/)
  if (!match) return null
  const year = Number(match[1])
  const mon = Number(match[2])
  if (mon < 1 || mon > 12) return null
  return { year, month: mon }
}

const DepartmentDetail = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const dept = searchParams.get('dept')
  const monthParam = searchParams.get('month')
  const month = monthParam?.match(/^\d{4}-\d{2}$/) ? monthParam : undefined

  const [allDepts, setAllDepts] = useState<DepartmentStat[]>([])
  const [overview, setOverview] = useState<OverviewState>(emptyOverview)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [emptyMessage, setEmptyMessage] = useState<string | null>(null)

  const filterDate = useMemo(() => {
    const parsed = parseMonthParam(monthParam)
    if (parsed) return parsed
    const now = new Date()
    return { year: now.getFullYear(), month: now.getMonth() + 1 }
  }, [monthParam])

  const setMonthInUrl = useCallback(
    (year: number, mon: number) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.set('month', `${year}-${String(mon).padStart(2, '0')}`)
        return next
      })
    },
    [setSearchParams],
  )

  useEffect(() => {
    let cancelled = false

    setOverview(emptyOverview)
    setRecommendations([])
    setEmptyMessage(null)

    async function load() {
      try {
        const deptRes = await getDashboardDepartments(month)
        if (cancelled) return

        const stats = deptRes.department_stats
        setAllDepts(stats)

        if (stats.length === 0) {
          setEmptyMessage(
            month
              ? `${month}에 표시할 부서 데이터가 없습니다.`
              : '표시할 부서 데이터가 없습니다.',
          )
          return
        }

        const target =
          dept && stats.some((d) => d.department === dept)
            ? dept
            : stats[0].department

        const [detailRes, recRes] = await Promise.all([
          getDepartmentDetail(target, month),
          getRecommendationsByDepartment(target, month),
        ])
        if (cancelled) return

        const tasks = detailRes.tasks_by_priority ?? []
        setOverview({
          total_tokens: detailRes.overview.total_tokens,
          total_cost: detailRes.overview.total_cost,
          user_count: detailRes.overview.user_count,
          task_distribution: tasks.map(
            (t: { task_label: string; count: number; ratio: number }) => ({
              label: t.task_label,
              count: t.count,
              ratio: t.ratio > 1 ? t.ratio / 100 : t.ratio,
            }),
          ),
        })
        setRecommendations(recRes.recommendations)

        if (tasks.length === 0 && recRes.recommendations.length === 0) {
          setEmptyMessage(
            month
              ? `${month}에 해당 부서 로그가 없습니다.`
              : '해당 부서 로그가 없습니다.',
          )
        }
      } catch {
        if (!cancelled) {
          setOverview(emptyOverview)
          setRecommendations([])
          setAllDepts([])
          setEmptyMessage(
            month
              ? `${month}에 해당 부서 데이터를 불러올 수 없습니다.`
              : '부서 데이터를 불러올 수 없습니다.',
          )
        }
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [dept, month])

  const kpiData = [
    { label: '사용량', value: formatTokens(overview.total_tokens) },
    { label: '비용', value: `₩${overview.total_cost.toLocaleString()}` },
    { label: '사용자 수', value: `${overview.user_count}명` },
  ]

  const hasChartData = overview.task_distribution.length > 0

  return (
    <div className="flex flex-col gap-[30px]">
      <div className="flex flex-row justify-between items-center">
        <DepartmentDropdown data={allDepts} />
        <DateFilter
          year={filterDate.year}
          month={filterDate.month}
          onChange={setMonthInUrl}
        />
      </div>

      {emptyMessage && (
        <p className="text-sm text-secondary rounded-lg border border-secondary/30 bg-secondary-light px-4 py-3">
          {emptyMessage}
        </p>
      )}

      <div className="grid grid-cols-3 gap-[30px]">
        {kpiData.map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </div>

      <div className="bg-white rounded-lg p-4">
        <h2 className="font-bold text-lg text-black mb-6">업무 유형</h2>
        {!hasChartData ? <EmptyChart /> : <WorkTypeChart data={overview.task_distribution} />}
      </div>

      <h1 className="font-bold text-xxl text-black">자동화 추천 리스트</h1>
      <div className="grid grid-cols-3 gap-[30px]">
        {recommendations.length === 0 ? (
          <EmptyChart height={200} message="추천 데이터가 없습니다" />
        ) : (
          <RecommendationList data={recommendations} />
        )}
      </div>
    </div>
  )
}

export default DepartmentDetail
