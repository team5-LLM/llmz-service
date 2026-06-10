import type { AutomationRecommendation, ClusterRecommendationCard, Recommendation } from "../../api/types"

type Props = {
  data: AutomationRecommendation[]
}

type Field = {
  label: string
  value: string
}

const fields = (item: Recommendation): Field[] => [
  { label: '기대 효과',   value: item.expected_effect },
  { label: '구현 난이도', value: item.difficulty },
  { label: '필요 리소스', value: item.required_resources.join(', ') },
]

const isClusterRecommendation = (item: AutomationRecommendation): item is ClusterRecommendationCard =>
  'recommendation_title' in item

const clusterFields = (item: ClusterRecommendationCard): Field[] => [
  { label: '클러스터 라벨', value: item.source_cluster_label },
  { label: 'Sub Cluster ID', value: item.sub_cluster_id },
  { label: 'Macro Category', value: item.macro_category },
  { label: 'Opportunity Score', value: String(item.opportunity_score) },
  { label: 'Risk Score', value: String(item.risk_score) },
  { label: '도입 판단', value: item.decision },
  { label: 'Method', value: item.method },
]

const RecommendationList = ({ data }: Props) => {
  return (
    <>
      {data.map((item, index) => {
        const title = isClusterRecommendation(item)
          ? item.recommendation_title
          : item.service_name
        const visibleFields = isClusterRecommendation(item)
          ? clusterFields(item)
          : fields(item)

        return (
          <div key={index} className="bg-white rounded-lg p-[30px] flex flex-col gap-4">
            <span className="font-bold text-xl text-black">{title}</span>

            {visibleFields.map(({ label, value }) => (
              <div key={label} className="flex flex-col gap-1">
                <span className="font-bold text-md text-black">{label}</span>
                <span className="text-md text-black">{value || '-'}</span>
              </div>
            ))}
          </div>
        )
      })}
    </>
  )
}

export default RecommendationList
