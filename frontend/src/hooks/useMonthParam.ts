import { useLayoutEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

function currentMonthParam(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

/** URL ?month=YYYY-MM — 없으면 현재 월을 URL에 먼저 기록한 뒤 반환 */
export function useMonthParam(): string | undefined {
  const [searchParams, setSearchParams] = useSearchParams()
  const month = searchParams.get('month') ?? undefined

  useLayoutEffect(() => {
    if (month) return
    setSearchParams(
      (prev) => {
        prev.set('month', currentMonthParam())
        return prev
      },
      { replace: true },
    )
  }, [month, setSearchParams])

  return month
}
