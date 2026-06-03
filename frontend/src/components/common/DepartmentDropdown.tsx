import { useState, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { DepartmentStat } from '../../api/types'

type Props = {
  data: DepartmentStat[]
}

const DepartmentDropdown = ({ data }: Props) => {
  const departments = data.map((dept) => dept.department)
  const [searchParams, setSearchParams] = useSearchParams()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null) // 외부 클릭 감지 위함

  const selected = searchParams.get('dept') ?? departments[0] ?? '부서 선택'

  const handleSelect = (dept: string) => {
    setSearchParams((prev) => {
      prev.set('dept', dept)
      return prev
    })
    setOpen(false)
  }

  // 외부 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="relative" ref={ref}>
      {/* 부서 + 아이콘 표시 */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 cursor-pointer"
      >
        <h1 className="font-bold text-xxl text-black">{selected}</h1>
        <span className="material-symbols-outlined text-xl text-black">
          expand_more
        </span>
      </button>

      {/* 드롭다운 리스트 */}
      {open && (
        <div className="absolute left-0 top-full pt-4 pb-[6px] bg-white rounded-b-lg shadow-md z-50 min-w-[133px]">
          {departments.map((dept) => (
            <div
              key={dept}
              onClick={() => handleSelect(dept)}
              className={`px-4 mb-[10px] text-lg cursor-pointer ${
                dept === selected ? 'font-bold' : 'font-medium'
              }`}
            >
              {dept}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default DepartmentDropdown