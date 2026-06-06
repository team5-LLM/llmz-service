import { BarChart, Bar, XAxis, YAxis, Cell, LabelList, ResponsiveContainer } from 'recharts'
import { WORK_TYPE_COLORS, COLORS } from '../../constants/colors'

type TaskItem = {
  label: string
  label_display?: string
  ratio: number
}

type Props = {
  data: TaskItem[]
}

const WorkTypeChart = ({ data }: Props) => {
  const chartData = data.map((task) => {
    const displayLabel = task.label_display || task.label
    const percentage = Math.round(task.ratio * 100)
    return {
      label: displayLabel,
      percentage,
      color: WORK_TYPE_COLORS[displayLabel] ?? COLORS.gray100,
      displayLabel: `${displayLabel} ${percentage}%`,
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
