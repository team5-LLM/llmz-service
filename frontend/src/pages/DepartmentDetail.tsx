import { useSearchParams } from 'react-router-dom'
import DateFilter from '../components/common/DateFilter'

const DepartmentDetail = () => {
  const [searchParams] = useSearchParams()
  const dept = searchParams.get('dept')
  const month = searchParams.get('month')

  return (
    <div className="flex flex-row justify-between">
        <h1 className="font-bold text-xxl text-black">부서 상세</h1>
        <DateFilter /> 
      </div>
  )
}

export default DepartmentDetail
