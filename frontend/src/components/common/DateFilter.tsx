import { useState, useRef, useEffect } from 'react'

type DateFilterProps = {
  onChange?: (year: number, month: number) => void
}

const DateFilter = ({ onChange }: DateFilterProps) => {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [open, setOpen] = useState(false)
  const [tempYear, setTempYear] = useState(now.getFullYear())
  const ref = useRef<HTMLDivElement>(null)

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
    setYear(tempYear)
    setMonth(m)
    onChange?.(tempYear, m)
    setOpen(false)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex justify-center items-center w-[136px] h-[40px] gap-2  bg-white border border-primary rounded-sm text-primary text-md font-medium cursor-pointer"
      >
        <span className="material-symbols-outlined text-lg leading-none">calendar_month</span>
        {year}년 {month}월
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white border border-gray-100 rounded-sm shadow-lg p-4 z-50 w-[200px]">
          {/* 연도 선택 커스텀 */}
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={() => setTempYear((y) => y - 1)}
              className="material-symbols-outlined text-lg text-black cursor-pointer"
            >
              chevron_left
            </button>
            <span className="text-md font-medium text-black">{tempYear}년</span>
            <button
              onClick={() => setTempYear((y) => y + 1)}
              className="material-symbols-outlined text-lg text-black cursor-pointer"
            >
              chevron_right
            </button>
          </div>

          {/* 월 선택 그리드 커스텀 */}
          <div className="grid grid-cols-4 gap-1">
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <button
                key={m}
                onClick={() => handleSelect(m)}
                className={`py-2 rounded-sm text-sm font-medium cursor-pointer transition-colors ${
                  tempYear === year && m === month
                    ? 'bg-primary text-white'
                    : 'text-black hover:bg-primary-light hover:text-primary'
                }`}
              >
                {m}월
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default DateFilter