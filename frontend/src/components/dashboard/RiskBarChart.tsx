import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { DepartmentStat } from '../../api/types'
import { COLORS, RISK_COLORS } from '../../constants/colors'

type Props = {
  data: DepartmentStat[]
}

const RiskBarChart = ({ data }: Props) => {
  const chartData = data.map((dept) => ({
    department: dept.department,
    value: dept.avg_risk_score,
    riskLevel: dept.risk_level,
  }))

  return (
    // 세로 바 차트 
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={chartData}
        margin={{ top: 0, right: 0, bottom: 0, left: -20 }}
        barSize={32}
        barCategoryGap={16}
      >
        <XAxis
          type="category"
          dataKey="department"
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 16, fill: COLORS.black }}
        />
        <YAxis
          type="number"
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 14, fill: COLORS.black }}
        />
        <Tooltip
          formatter={(value: number) => [value.toFixed(1), '평균 위험도']}
          cursor={{ fill: COLORS.white }}
        />
        <Bar dataKey="value" isAnimationActive radius={6}>
          {chartData.map((item, index) => (
            <Cell
              key={index}
              fill={RISK_COLORS[item.riskLevel] ?? COLORS.gray100}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default RiskBarChart