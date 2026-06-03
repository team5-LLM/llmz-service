import type { Recommendation } from '../../api/types'

type Props = {
  data: Recommendation[]
}

const DECISION_BADGE: Record<string, string> = {
  proceed: 'bg-risk-low text-[#2d6a2d]',
  review: 'bg-risk-medium text-[#856c00]',
  low_priority: 'bg-gray-100 text-gray-600',
  green: 'bg-risk-low text-[#2d6a2d]',
  yellow: 'bg-risk-medium text-[#856c00]',
  red: 'bg-risk-high text-[#8b0000]',
}

const RecommendationDetailList = ({ data }: Props) => {
  const items = data ?? []

  return (
    <>
      {items.map((item, index) => (
        <div key={`${item.task_label}-${index}`} className="bg-white rounded-lg p-[30px] flex flex-col gap-4">
          <div className="flex flex-row justify-between items-center gap-2">
            <div className="flex flex-col min-w-0">
              <span className="font-bold text-lg text-black">{item.service_name}</span>
              <span className="text-sm text-gray-500">{item.task_label}</span>
            </div>
            <span
              className={`inline-block shrink-0 px-3 py-1 rounded-sm text-sm ${DECISION_BADGE[item.decision_level] ?? 'bg-gray-100 text-gray-600'}`}
            >
              {item.decision}
            </span>
          </div>

          <div className="flex flex-col gap-1">
            <span className="font-bold text-md text-black">Opportunity Score</span>
            <div className="flex flex-row items-center gap-2">
              <div className="flex-1 bg-gray-100 rounded-full h-2">
                <div
                  className="bg-primary h-2 rounded-full"
                  style={{ width: `${Math.min(100, Math.max(0, item.opportunity_score))}%` }}
                />
              </div>
              <span className="text-md text-black w-8 text-right">{item.opportunity_score}</span>
            </div>
          </div>

          {item.decision_message ? (
            <p className="text-sm text-primary">{item.decision_message}</p>
          ) : null}

          <div className="flex flex-col gap-1">
            <span className="font-bold text-md text-black">기대 효과</span>
            <span className="text-md text-black">{item.expected_effect}</span>
          </div>

          <div className="flex flex-col gap-1">
            <span className="font-bold text-md text-black">구현 난이도</span>
            <span className="text-md text-black">{item.difficulty}</span>
          </div>

          <div className="flex flex-col gap-1">
            <span className="font-bold text-md text-black">필요 리소스</span>
            <span className="text-md text-black">
              {item.required_resources.length > 0
                ? item.required_resources.join(', ')
                : '-'}
            </span>
          </div>

          <div className="flex flex-col gap-2">
            <span className="font-bold text-md text-black">추천 이유</span>
            {item.reason.length > 0 ? (
              <ul className="list-disc pl-5 flex flex-col gap-1">
                {item.reason.map((factor) => (
                  <li key={`${factor.factor}-${factor.description}`} className="text-md text-black">
                    {factor.description}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="text-md text-gray-500">-</span>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <span className="font-bold text-md text-black">보안 조치</span>
            <span className="text-md text-black">{item.required_action}</span>
          </div>
        </div>
      ))}
    </>
  )
}

export default RecommendationDetailList
