import KpiCard from '../components/common/KpiCard'

// 더미 데이터
const kpiData = [
  { label: '총 분석 프롬프트 수', value: '12,846' },
  { label: '총 토큰 사용량', value: '3.8M' },
  { label: '총 비용', value: '₩482,000' },
]

const Dashboard = () => {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-bold text-xxl text-black">Dashboard</h1>

      {/* KPI 카드 */}
      <div className="grid grid-cols-3 gap-4">
        {kpiData.map((kpi) => (
          <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} />
        ))}
      </div>
    </div>
  )
};

export default Dashboard
