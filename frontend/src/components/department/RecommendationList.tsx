import type { Recommendation } from "../../api/types"

type Props = {
  data: Recommendation[]
}

const RecommendationList = ({ data }: Props) => {
  return (
    <>
      {data.map((item, index) => (
        <div key={index} className="bg-white rounded-lg p-[30px] flex flex-col gap-4">
          <span className="font-bold text-xl text-black">{item.service_name}</span>

          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1">
              <span className="font-bold text-md text-black">기대 효과</span>
            </div>
            <span className="text-md text-black">{item.expected_effect}</span>
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1">
              <span className="font-bold text-md text-black">구현 난이도</span>
            </div>
            <span className="text-md text-black">{item.difficulty}</span>
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1">
              <span className="font-bold text-md text-black">필요 리소스</span>
            </div>
            <span className="text-md text-black">{item.required_resources}</span>
          </div>
        </div>
      ))}
    </>
  )
}

export default RecommendationList
