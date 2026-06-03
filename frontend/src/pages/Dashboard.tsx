import DateFilter from '../components/common/DateFilter'

import KpiCard from '../components/common/KpiCard'

import DepartmentWorkTypeChart from '../components/dashboard/DepartmentWorkTypeChart'

import type { DepartmentStat, Summary } from '../api/types'

import TokenDonutChart from '../components/dashboard/TokenDonutChart'

import RiskBarChart from '../components/dashboard/RiskBarChart'

import EmptyChart from '../components/common/EmptyChart'

import { Link, useSearchParams } from 'react-router-dom'

import { useCallback, useEffect, useMemo, useState } from 'react'

import {

  getApiBaseUrl,

  getDashboardDepartments,

  getDashboardSummary,

  resolveDashboardMonth,

} from '../api'



function parseMonthParam(month: string | null): { year: number; month: number } | null {

  const match = month?.match(/^(\d{4})-(\d{2})$/)

  if (!match) return null

  const year = Number(match[1])

  const mon = Number(match[2])

  if (mon < 1 || mon > 12) return null

  return { year, month: mon }

}



function toMonthParam(year: number, month: number): string {

  return `${year}-${String(month).padStart(2, '0')}`

}



const emptySummary: Summary = {

  total_logs: 0,

  departments: 0,

  total_tokens: 0,

  total_cost: 0,

  avg_risk_score: 0,

}



const Dashboard = () => {

  const [searchParams, setSearchParams] = useSearchParams()

  const monthParam = searchParams.get('month')



  const [summary, setSummary] = useState<Summary>(emptySummary)

  const [deptStats, setDeptStats] = useState<DepartmentStat[]>([])

  const [loading, setLoading] = useState(true)

  const [error, setError] = useState<string | null>(null)

  const [activeMonth, setActiveMonth] = useState<string | undefined>(

    monthParam?.match(/^\d{4}-\d{2}$/) ? monthParam : undefined,

  )



  const filterDate = useMemo(() => {

    const parsed = parseMonthParam(monthParam) ?? parseMonthParam(activeMonth ?? null)

    if (parsed) return parsed

    const now = new Date()

    return { year: now.getFullYear(), month: now.getMonth() + 1 }

  }, [activeMonth, monthParam])



  const setMonthInUrl = useCallback(

    (year: number, month: number) => {

      const value = toMonthParam(year, month)

      setSearchParams((prev) => {

        const next = new URLSearchParams(prev)

        next.set('month', value)

        return next

      })

    },

    [setSearchParams],

  )



  useEffect(() => {

    let cancelled = false



    async function load() {

      setLoading(true)

      setError(null)

      try {

        const urlMonth = monthParam?.match(/^\d{4}-\d{2}$/) ? monthParam : undefined

        // URL에 month가 없을 때만(첫 진입) 데이터가 있는 월로 자동 이동
        if (!urlMonth) {

          const resolved = await resolveDashboardMonth(null)

          if (cancelled) return

          if (!resolved) {

            setActiveMonth(undefined)

            setSummary(emptySummary)

            setDeptStats([])

            setError('표시할 로그 데이터가 없습니다. 데이터 관리에서 CSV를 업로드해 주세요.')

            return

          }

          setSearchParams((prev) => {

            const next = new URLSearchParams(prev)

            next.set('month', resolved)

            return next

          }, { replace: true })

          return

        }



        const month = urlMonth

        setActiveMonth(month)



        const [summaryRes, deptRes] = await Promise.all([

          getDashboardSummary(month),

          getDashboardDepartments(month),

        ])



        if (cancelled) return



        setSummary(summaryRes.summary)

        setDeptStats(deptRes.department_stats)



        if (summaryRes.summary.total_logs === 0) {

          setError(

            `${month}에 집계된 로그가 없습니다. CSV의 created_at 월과 필터 월이 일치하는지 확인해 주세요.`,

          )

        } else {

          setError(null)

        }

      } catch (err) {

        if (cancelled) return

        const message = err instanceof Error ? err.message : '대시보드 로드 실패'

        setError(`${message} (API: ${getApiBaseUrl()})`)

        setSummary(emptySummary)

        setDeptStats([])

      } finally {

        if (!cancelled) setLoading(false)

      }

    }



    load()

    return () => {

      cancelled = true

    }

  }, [monthParam, setSearchParams])



  const formatTokens = (value: number) => {

    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`

    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`

    return value.toString()

  }



  const getSummaryKpiData = (data: Summary) => [

    { label: '총 분석 프롬프트 수', value: data.total_logs.toLocaleString() },

    { label: '총 토큰 사용량', value: formatTokens(data.total_tokens) },

    { label: '총 비용', value: `₩${data.total_cost.toLocaleString()}` },

  ]



  const hasChartData = deptStats.length > 0 && summary.total_logs > 0



  return (

    <div className="flex flex-col gap-[30px]">

      <div className="flex flex-row justify-between items-start">

        <h1 className="font-bold text-xxl text-black">Dashboard</h1>

        <DateFilter

          year={filterDate.year}

          month={filterDate.month}

          onChange={(year, month) => setMonthInUrl(year, month)}

        />

      </div>



      {loading && (

        <p className="text-sm text-gray-500">대시보드 데이터를 불러오는 중…</p>

      )}



      {!loading && error && (

        <div

          className="rounded-lg border border-secondary/30 bg-secondary-light px-4 py-3 text-sm text-secondary"

          role="alert"

        >

          {error}

          <div className="mt-2">

            <Link to="/dataManagement" className="text-primary font-medium underline">

              데이터 관리에서 CSV 업로드

            </Link>

          </div>

        </div>

      )}



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

        {!hasChartData ? (

          <EmptyChart />

        ) : (

          <DepartmentWorkTypeChart data={deptStats} />

        )}

      </div>



      {/* 부서별 사용량 & 평균 위험도 */}

      <div className="flex flex-row gap-[30px]">

        <div className="bg-white rounded-lg p-4 w-1/2">

          <div className="flex justify-between items-center mb-[30px]">

            <h2 className="font-bold text-lg text-black">부서별 사용량</h2>

          </div>

          {!hasChartData ? <EmptyChart /> : <TokenDonutChart data={deptStats} />}

        </div>

        <div className="bg-white rounded-lg p-4 w-1/2">

          <div className="flex justify-between items-center mb-[30px]">

            <h2 className="font-bold text-lg text-black">부서별 평균 위험도</h2>

          </div>

          {!hasChartData ? <EmptyChart /> : <RiskBarChart data={deptStats} />}

        </div>

      </div>

    </div>

  )

}



export default Dashboard

