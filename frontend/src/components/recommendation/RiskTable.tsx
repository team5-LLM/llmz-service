import type { RiskLevel, RiskLevelDefinition } from '../../api/types'

const BADGE_CLASS: Record<RiskLevel, string> = {
  Low: 'bg-risk-low',
  Medium: 'bg-risk-medium',
  High: 'bg-risk-high',
  Critical: 'bg-risk-critical',
}

type Props = {
  levels: RiskLevelDefinition[]
  loading?: boolean
}

const RiskTable = ({ levels, loading = false }: Props) => {
  if (loading) {
    return (
      <p className="text-sm text-center py-8" style={{ color: 'var(--color-gray-500)' }}>
        데이터 불러오는 중...
      </p>
    )
  }

  if (levels.length === 0) {
    return (
      <p className="text-sm text-center py-8" style={{ color: 'var(--color-gray-500)' }}>
        등급 정의를 불러오지 못했습니다.
      </p>
    )
  }

  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full text-md border-collapse">
        <thead>
          <tr className="bg-bg">
            <th className="px-4 py-2.5 text-left text-black border-b-2 border-gray-100">Risk Score</th>
            <th className="px-4 py-2.5 text-left text-black border-b-2 border-gray-100">등급</th>
            <th className="px-4 py-2.5 text-left text-black border-b-2 border-gray-100">의미</th>
          </tr>
        </thead>
        <tbody>
          {levels.map((row) => (
            <tr key={row.level} className="border-b border-gray-100">
              <td className="px-4 py-3 text-black">{row.score_range.replace('~', ' ~ ')}</td>
              <td className="px-4 py-3">
                <span className={`inline-block text-center w-[70px] py-2 rounded-full text-sm ${BADGE_CLASS[row.level]}`}>
                  {row.level}
                </span>
              </td>
              <td className="px-4 py-2.5 text-black">{row.meaning}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default RiskTable
