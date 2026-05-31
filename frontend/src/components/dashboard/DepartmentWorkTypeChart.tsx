import { BarChart, Bar, XAxis, YAxis, Cell, LabelList, ResponsiveContainer } from 'recharts'
import type { DepartmentStat } from '../../api/types'
import { WORK_TYPE_COLORS, COLORS } from '../../constants/colors'

const DEFAULT_COLOR = COLORS.gray100

type Props = {
  data: DepartmentStat[]
}

const DepartmentWorkTypeChart = ({ data }: Props) => {
  // 부서별 TOP 업무 유형 산출
  const chartData = data.map((dept) => {
    const topTask = dept.task_distribution.reduce((a, b) =>
      a.ratio > b.ratio ? a : b
    )
    const percentage = Math.round(topTask.ratio * 100)
    return {
      department: dept.department,
      percentage,
      color: WORK_TYPE_COLORS[topTask.label] ?? DEFAULT_COLOR,
      label: `${topTask.label} ${percentage}%`,
    }
  })

  return (
    // 가로 바 차트
    <ResponsiveContainer width="100%" height={chartData.length * 56}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 0, right: 200, bottom: 0, left: 0 }}
        barSize={30}
        barCategoryGap={16}
      >
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis
          type="category"
          dataKey="department"
          width={90}
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 16, fill: COLORS.black }}
        />
        <Bar dataKey="percentage" isAnimationActive radius={6}>
          {chartData.map((item, index) => (
            <Cell key={index} fill={item.color} />
          ))}
          <LabelList
            dataKey="label"
            position="right"
            offset={16}
            style={{ fontSize: 14, fill: COLORS.black }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default DepartmentWorkTypeChart
