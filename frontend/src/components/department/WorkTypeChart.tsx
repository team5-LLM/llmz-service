import { BarChart, Bar, XAxis, YAxis, Cell, LabelList, ResponsiveContainer } from 'recharts'
import { WORK_TYPE_COLORS, COLORS } from '../../constants/colors'

type TaskItem = {
  label: string
  ratio: number
}

type Props = {
  data: TaskItem[]
}

const WorkTypeChart = ({ data }: Props) => {
  const chartData = data.map((task) => ({
    label: task.label,
    percentage: Math.round(task.ratio * 100),
    color: WORK_TYPE_COLORS[task.label] ?? COLORS.gray100,
    displayLabel: `${task.label} ${Math.round(task.ratio * 100)}%`,
  }))

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
          dataKey="label"
          hide
        />
        <Bar dataKey="percentage" isAnimationActive radius={6}>
          {chartData.map((item, index) => (
            <Cell key={index} fill={item.color} />
          ))}
          <LabelList
            dataKey="displayLabel"
            position="right"
            offset={16}
            style={{ fontSize: 14, fill: COLORS.black }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default WorkTypeChart
