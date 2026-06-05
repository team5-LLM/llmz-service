import type { Recommendation } from "../../api/types"

type Props = {
  data: Recommendation[]
}

const DECISION_LEVEL_ALIASES: Record<string, string> = {
  recommended: 'proceed',
  conditional: 'review',
  security_review: 'review',
  later: 'review',
  hold: 'review',
}

const DECISION_BADGE: Record<string, string> = {
  proceed: 'bg-risk-low',
  review: 'bg-risk-medium',
  low_priority: 'bg-risk-high',
}

const resolveDecisionLevel = (level: string) =>
  DECISION_LEVEL_ALIASES[level] ?? level

const RecommendationDetailList = ({ data }: Props) => {
  return (
    <>
      {data.map((item, index) => (
        <div key={index} className="bg-white rounded-lg p-[30px] flex flex-col gap-4">
          <div className="flex flex-row justify-between items-center">
            <div className="flex flex-col gap-1">
              <span className="font-bold text-lg text-black">{item.service_name}</span>
              {(item.task_label_display ?? item.cluster_label) && (
                <span className="text-sm text-gray-500">
                  업무유형: {item.task_label_display ?? item.cluster_label}
                </span>
              )}
            </div>
            <span className={`inline-block px-3 py-1 rounded-sm text-sm ${DECISION_BADGE[resolveDecisionLevel(item.decision_level)] ?? 'bg-gray-100 text-gray-600'}`}>
              {item.decision}
            </span>
          </div>

          {/* Opportunity Score */}
          <div className="flex flex-col gap-1">
            <span className="font-bold text-md text-black">Opportunity Score</span>
            <div className="flex flex-row items-center gap-2">
              <div className="flex-1 bg-gray-100 rounded-full h-2">
                <div
                  className="bg-primary h-2 rounded-full"
                  style={{ width: `${item.opportunity_score}%` }}
                />
              </div>
              <span className="text-md text-black w-8 text-right">{item.opportunity_score}</span>
            </div>
          </div>

          {/* 기대 효과 */}
          <div className="flex flex-col gap-1">
            <span className="font-bold text-md text-black">기대 효과</span>
            <span className="text-md text-black">{item.expected_effect}</span>
          </div>
          {/* 구현 난이도 */}
          <div className="flex flex-col gap-1">
            <span className="font-bold text-md text-black">구현 난이도</span>
            <span className="text-md text-black">{item.difficulty}</span>
          </div>
          {/* 필요 리소스 */}
          <div className="flex flex-col gap-1">
            <span className="font-bold text-md text-black">필요 리소스</span>
            <span className="text-md text-black">{item.required_resources.join(', ')}</span>
          </div>

          {/* 추천 이유 */}
          <div className="flex flex-col gap-1">
            <span className="font-bold text-md text-black">추천 이유</span>
            {item.reason.map((r, i) => (
              <span key={i} className="text-md text-black">{r.description}</span>
            ))}
          </div>

          {/* 보안 조치 */}
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
