import { useState, useRef, useEffect } from 'react'

type DateFilterProps = {
  year?: number
  month?: number
  onChange?: (year: number, month: number) => void
}

const DateFilter = ({ year: yearProp, month: monthProp, onChange }: DateFilterProps) => {
  const now = new Date()
  const currentYear = now.getFullYear()
  const currentMonth = now.getMonth() + 1
  const [internalYear, setInternalYear] = useState(currentYear)
  const [internalMonth, setInternalMonth] = useState(currentMonth)
  const year = yearProp ?? internalYear
  const month = monthProp ?? internalMonth
  const [open, setOpen] = useState(false)
  const [tempYear, setTempYear] = useState(year)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setTempYear(year)
  }, [year])

  useEffect(() => {
    if (yearProp != null) setInternalYear(yearProp)
    if (monthProp != null) setInternalMonth(monthProp)
  }, [yearProp, monthProp])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (m: number) => {
    setInternalYear(tempYear)
    setInternalMonth(m)
    onChange?.(tempYear, m)
    setOpen(false)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex justify-center items-center w-[136px] h-[40px] gap-2  bg-white border border-primary rounded-sm text-primary text-md font-medium cursor-pointer"
      >
        <span className="material-symbols-outlined text-lg leading-none">calendar_month</span>
        {year}년 {month}월
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white border border-gray-100 rounded-sm shadow-lg p-4 z-50 w-[200px]">
          <div className="flex items-center justify-between mb-3">
            <button
              type="button"
              onClick={() => setTempYear((y) => y - 1)}
              className="material-symbols-outlined text-lg text-black cursor-pointer"
            >
              chevron_left
            </button>
            <span className="text-md font-medium text-black">{tempYear}년</span>
            <button
              type="button"
              onClick={() => setTempYear((y) => y + 1)}
              disabled={tempYear >= currentYear}
              className={`material-symbols-outlined text-lg cursor-pointer ${tempYear >= currentYear ? 'text-gray-100' : 'text-black'}`}
            >
              chevron_right
            </button>
          </div>

          <div className="grid grid-cols-4 gap-1">
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => {
              const isFuture =
                tempYear > currentYear || (tempYear === currentYear && m > currentMonth)
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => !isFuture && handleSelect(m)}
                  disabled={isFuture}
                  className={`py-2 rounded-sm text-sm font-medium transition-colors ${
                    isFuture
                      ? 'text-gray-100 cursor-not-allowed'
                      : tempYear === year && m === month
                        ? 'bg-primary text-white cursor-pointer'
                        : 'text-black hover:bg-primary-light hover:text-primary cursor-pointer'
                  }`}
                >
                  {m}월
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default DateFilter
