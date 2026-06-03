const riskGrade = [
  { range: '0 ~ 30', grade: 'Low', meaning: '일반 업무 프롬프트', badgeClass: 'bg-risk-low' },
  { range: '31 ~ 60', grade: 'Medium', meaning: '일부 민감정보 가능성', badgeClass: 'bg-risk-medium' },
  { range: '61 ~ 80', grade: 'High', meaning: '개인정보/기밀정보 포함 가능성 높음', badgeClass: 'bg-risk-high' },
  { range: '81 ~ 100', grade: 'Critical', meaning: '원문 저장 금지, 관리자 검토 필요', badgeClass: 'bg-risk-critical' },
]

const RiskTable = () => {
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
          {riskGrade.map((row) => (
            <tr key={row.grade} className="border-b border-gray-100">
              <td className="px-4 py-3 text-black">{row.range}</td>
              <td className="px-4 py-3">
                <span className={`inline-block text-center w-[70px] py-2 rounded-full text-sm ${row.badgeClass}`}>
                  {row.grade}
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
