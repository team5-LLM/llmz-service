import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { DepartmentStat } from '../../api/types'
import { CHART_COLORS } from '../../constants/colors'

type Props = {
  data: DepartmentStat[]
}

const TokenDonutChart = ({ data }: Props) => {
  const chartData = data.map((dept) => ({
    name: dept.department,
    value: dept.total_tokens,
  }))

  const total = chartData.reduce((sum, item) => sum + item.value, 0)

  return (
    <div className="flex items-center gap-4">
      {/* 도넛 차트 */}
      <ResponsiveContainer width="60%" height={300}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={110}
            dataKey="value"
          >
            {chartData.map((_, index) => (
              <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
            ))}
          </Pie>
          {/* 마우스 hover 시 사용량 상세 표시 */}
          <Tooltip
            formatter={(value: number) => [`${value.toLocaleString()} 토큰`, '']}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* 범례 */}
      <div className="flex flex-col gap-2 flex-1">
        {chartData.map((item, index) => (
          <div key={item.name} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div
                className="w-4 h-4 rounded-full shrink-0"
                style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
              />
              <span className="text-md text-black">{item.name}</span>
            </div>
            <span className="text-md text-black font-medium">
              {total > 0 ? Math.round((item.value / total) * 100) : 0}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default TokenDonutChart