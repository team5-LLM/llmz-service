import { useSearchParams } from 'react-router-dom'

const DepartmentDetail = () => {
  const [searchParams] = useSearchParams()
  const dept = searchParams.get('dept')
  const month = searchParams.get('month')

  return (
    <div>
      <h1 className="font-bold text-xxl text-black">부서 상세</h1>
    </div>
  )
}

export default DepartmentDetail
