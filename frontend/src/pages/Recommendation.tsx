import { useSearchParams } from 'react-router-dom'

const Recommendation = () => {
  const [searchParams] = useSearchParams()
  const dept = searchParams.get('dept')
  const month = searchParams.get('month')

  return (
    <div>
      <h1 className="font-bold text-xxl text-black">자동화 추천</h1>
    </div>
  )
}

export default Recommendation
