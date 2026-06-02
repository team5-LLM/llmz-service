import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { COLORS, RISK_COLORS } from "../../constants/colors"
import type { Recommendation } from "../../api/types"

type Props = {
  data: Recommendation[]
}

const GRADES = ['Low', 'Medium', 'High', 'Critical'] as const

const RiskGradeBarChart = ({ data }: Props) => {
  const counts = GRADES.reduce((acc, grade) => {
    acc[grade] = 0
    return acc
  }, {} as Record<string, number>)

  data.forEach((item) => {
    if (item.risk_level in counts) counts[item.risk_level]++
  })

  const total = data.length || 1

  const chartData = GRADES.map((grade) => ({
    grade,
    ratio: Math.round((counts[grade] / total) * 100),
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={chartData}
        margin={{ top: 0, right: 0, bottom: 0, left: -20 }}
        barSize={40}
        barCategoryGap={16}
      >
        <XAxis
          dataKey="grade"
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 16, fill: COLORS.black }}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 14, fill: COLORS.black }}
          tickFormatter={(v) => `${v}%`}
          domain={[0, 100]}
        />
        <Tooltip
          formatter={(value: number) => [`${value}%`, '비율']}
          cursor={{ fill: 'transparent' }}
        />
        <Bar dataKey="ratio" isAnimationActive radius={6}>
          {chartData.map((item) => (
            <Cell
              key={item.grade}
              fill={RISK_COLORS[item.grade] ?? COLORS.gray100}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default RiskGradeBarChart
