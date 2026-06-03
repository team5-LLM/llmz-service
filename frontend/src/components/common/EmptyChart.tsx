type Props = {
  height?: number
  message?: string
}

const EmptyChart = ({ height = 300, message = '데이터가 없습니다' }: Props) => {
  return (
    <div
      className="flex items-center justify-center text-gray-500 text-md"
      style={{ height }}
    >
      {message}
    </div>
  )
}

export default EmptyChart
