import { useState, useEffect, useMemo, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import DepartmentDropdown from '../components/common/DepartmentDropdown'
import DateFilter from '../components/common/DateFilter'
import type { DepartmentStat, Recommendation as RecommendationItem } from '../api/types'
import RecommendationDetailList from '../components/recommendation/RecommendationDetailList'
import InfoBox from '../components/recommendation/InfoBox'
import {
  getDashboardDepartments,
  getRecommendationsByDepartment,
  resolveDashboardMonth,
} from '../api'
import EmptyChart from '../components/common/EmptyChart'

function parseMonthParam(month: string | null): { year: number; month: number } | null {
  const match = month?.match(/^(\d{4})-(\d{2})$/)
  if (!match) return null
  const year = Number(match[1])
  const mon = Number(match[2])
  if (mon < 1 || mon > 12) return null
  return { year, month: mon }
}

export default function RecommendationPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const dept = searchParams.get('dept')
  const monthParam = searchParams.get('month')
  const month = monthParam?.match(/^\d{4}-\d{2}$/) ? monthParam : undefined

  const [allDepts, setAllDepts] = useState<DepartmentStat[]>([])
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([])
  const [emptyMessage, setEmptyMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

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

    setRecommendations([])
    setEmptyMessage(null)
    setLoading(true)

    async function load() {
      try {
        let activeMonth = month
        if (!activeMonth) {
          const resolved = await resolveDashboardMonth(null)
          if (cancelled) return
          if (resolved) {
            activeMonth = resolved
            setSearchParams(
              (prev) => {
                const next = new URLSearchParams(prev)
                next.set('month', resolved)
                return next
              },
              { replace: true },
            )
            return
          }
        }

        const deptRes = await getDashboardDepartments(activeMonth)
        if (cancelled) return

        const stats = deptRes.department_stats ?? []
        setAllDepts(stats)

        if (stats.length === 0) {
          setEmptyMessage(
            activeMonth
              ? `${activeMonth}에 표시할 추천 데이터가 없습니다.`
              : '표시할 추천 데이터가 없습니다. CSV를 업로드해 주세요.',
          )
          return
        }

        const target =
          dept && stats.some((d) => d.department === dept)
            ? dept
            : stats[0].department

        const recRes = await getRecommendationsByDepartment(target, activeMonth)
        if (cancelled) return

        setRecommendations(recRes.recommendations)
        if (recRes.recommendations.length === 0) {
          setEmptyMessage(
            activeMonth
              ? `${activeMonth} · ${target}에 추천 카드가 없습니다.`
              : `${target}에 추천 카드가 없습니다.`,
          )
        }
      } catch (err) {
        if (!cancelled) {
          console.error('RecommendationPage load failed:', err)
          setRecommendations([])
          setAllDepts([])
          const msg = err instanceof Error ? err.message : '추천 API 호출 실패'
          setEmptyMessage(msg)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [dept, month, setSearchParams])

  return (
    <div className="flex flex-col gap-[30px]">
      <div className="flex flex-row justify-between items-center">
        <div className="flex items-center gap-2 min-w-0">
          <DepartmentDropdown data={allDepts} />
          <h1 className="font-bold text-xxl text-black shrink-0">자동화 추천</h1>
        </div>
        <DateFilter
          year={filterDate.year}
          month={filterDate.month}
          onChange={setMonthInUrl}
        />
      </div>

      <div className="flex flex-row gap-1 items-start">
        <span className="text-md text-primary">
          Opportunity Score가 높더라도 Risk Score가 높으면 자동화 우선이 아니라 보안 검토 필요로
          분류합니다.
        </span>
        <InfoBox
          content={
            'Opportunity Score: 반복 사용 패턴과 업무 유형을 분석하여 자동화 효과를 예측한 점수\nRisk Score: 개인정보, 고객정보, 기밀정보 등의 포함 가능성을 분석한 위험도 점수'
          }
        />
      </div>

      {loading && <p className="text-sm text-gray-500">추천 데이터를 불러오는 중…</p>}

      {!loading && emptyMessage && (
        <p className="text-sm text-secondary rounded-lg border border-secondary/30 bg-secondary-light px-4 py-3">
          {emptyMessage}
        </p>
      )}

      <div className="grid grid-cols-3 gap-[30px]">
        {loading ? null : recommendations.length === 0 ? (
          <div className="col-span-3">
            <EmptyChart height={200} message="추천 데이터가 없습니다" />
          </div>
        ) : (
          <RecommendationDetailList data={recommendations} />
        )}
      </div>
    </div>
  )
}
