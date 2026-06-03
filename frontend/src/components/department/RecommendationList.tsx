import type { Recommendation } from "../../api/types"

type Props = {
  data: Recommendation[]
}

type Field = {
  label: string
  value: string
}

const fields = (item: Recommendation): Field[] => [
  { label: '기대 효과',   value: item.expected_effect },
  { label: '구현 난이도', value: item.difficulty },
  { label: '필요 리소스', value: item.required_resources.join(', ') || '-' },
]

const RecommendationList = ({ data }: Props) => {
  return (
    <>
      {data.map((item, index) => (
        <div key={index} className="bg-white rounded-lg p-[30px] flex flex-col gap-4">
          <span className="font-bold text-xl text-black">{item.service_name}</span>

          {fields(item).map(({ label, value }) => (
            <div key={label} className="flex flex-col gap-1">
              <span className="font-bold text-md text-black">{label}</span>
              <span className="text-md text-black">{value}</span>
            </div>
          ))}
        </div>
      ))}
    </>
  )
}

export default RecommendationList
