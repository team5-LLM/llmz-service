import type { AutomationRecommendation, ClusterRecommendationCard, Recommendation } from "../../api/types"

type Props = {
  data: AutomationRecommendation[]
}

const DECISION_BADGE: Record<string, string> = {
  proceed: 'bg-risk-low',
  review: 'bg-risk-medium',
  low_priority: 'bg-gray-100',
}

const CLUSTER_DECISION_BADGE: Record<string, string> = {
  '우선 도입 후보': 'bg-risk-low',
  '제한적 도입 권장': 'bg-risk-medium',
  '보안 검토 필요': 'bg-risk-high',
}

const isClusterRecommendation = (item: AutomationRecommendation): item is ClusterRecommendationCard =>
  'recommendation_title' in item

const scoreWidth = (score: number) => `${Math.max(0, Math.min(100, score))}%`
const displayValue = (value: unknown) =>
  value === '' || value === null || value === undefined ? '-' : String(value)

const ClusterRecommendationCardView = ({ item }: { item: ClusterRecommendationCard }) => (
  <div className="bg-white rounded-lg p-[30px] flex flex-col gap-4">
    <div className="flex flex-row justify-between items-center gap-3">
      <span className="font-bold text-lg text-black">{item.recommendation_title}</span>
      <span className={`inline-block px-3 py-1 rounded-sm text-sm whitespace-nowrap ${CLUSTER_DECISION_BADGE[item.decision] ?? 'bg-gray-100 text-gray-600'}`}>
        {item.decision}
      </span>
    </div>

    <div className="flex flex-col gap-1">
      <span className="font-bold text-md text-black">Opportunity Score</span>
      <div className="flex flex-row items-center gap-2">
        <div className="flex-1 bg-gray-100 rounded-full h-2">
          <div
            className="bg-primary h-2 rounded-full"
            style={{ width: scoreWidth(item.opportunity_score) }}
          />
        </div>
        <span className="text-md text-black w-8 text-right">{item.opportunity_score}</span>
      </div>
    </div>

    {[
      { label: '클러스터 라벨', value: item.source_cluster_label },
      { label: 'Sub Cluster ID', value: item.sub_cluster_id },
      { label: 'Macro Category', value: item.macro_category },
      { label: 'Risk Score', value: item.risk_score },
      { label: '도입 판단', value: item.decision },
      { label: 'Method', value: item.method },
    ].map(({ label, value }) => (
      <div key={label} className="flex flex-col gap-1">
        <span className="font-bold text-md text-black">{label}</span>
        <span className="text-md text-black">{displayValue(value)}</span>
      </div>
    ))}
  </div>
)

const LegacyRecommendationCardView = ({ item }: { item: Recommendation }) => (
  <div className="bg-white rounded-lg p-[30px] flex flex-col gap-4">
    <div className="flex flex-row justify-between items-center gap-3">
      <span className="font-bold text-lg text-black">{item.service_name}</span>
      <span className={`inline-block px-3 py-1 rounded-sm text-sm whitespace-nowrap ${DECISION_BADGE[item.decision_level] ?? 'bg-gray-100 text-gray-600'}`}>
        {item.decision}
      </span>
    </div>

    <div className="flex flex-col gap-1">
      <span className="font-bold text-md text-black">Opportunity Score</span>
      <div className="flex flex-row items-center gap-2">
        <div className="flex-1 bg-gray-100 rounded-full h-2">
          <div
            className="bg-primary h-2 rounded-full"
            style={{ width: scoreWidth(item.opportunity_score) }}
          />
        </div>
        <span className="text-md text-black w-8 text-right">{item.opportunity_score}</span>
      </div>
    </div>

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
      <span className="text-md text-black">{item.required_resources.join(', ')}</span>
    </div>

    <div className="flex flex-col gap-1">
      <span className="font-bold text-md text-black">추천 이유</span>
      {item.reason.map((r, i) => (
        <span key={i} className="text-md text-black">{r.description}</span>
      ))}
    </div>

    <div className="flex flex-col gap-1">
      <span className="font-bold text-md text-black">보안 조치</span>
      <span className="text-md text-black">{item.required_action}</span>
    </div>
  </div>
)

const RecommendationDetailList = ({ data }: Props) => {
  return (
    <>
      {data.map((item, index) => (
        isClusterRecommendation(item)
          ? <ClusterRecommendationCardView key={index} item={item} />
          : <LegacyRecommendationCardView key={index} item={item} />
      ))}
    </>
  )
}

export default RecommendationDetailList
