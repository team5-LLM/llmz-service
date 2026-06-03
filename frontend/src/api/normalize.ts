import type { Recommendation, RecommendationReasonFactor } from './types'

function asReasonFactors(value: unknown): RecommendationReasonFactor[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      factor: String(item.factor ?? ''),
      value: Number(item.value ?? 0),
      unit: String(item.unit ?? ''),
      description: String(item.description ?? ''),
    }))
    .filter((item) => item.description.length > 0)
}

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((v) => String(v)).filter(Boolean)
  }
  if (typeof value === 'string' && value.trim()) {
    return [value]
  }
  return []
}

/** BE recommendations 응답 → FE 표시용 정규화 */
export function normalizeRecommendation(raw: Record<string, unknown>): Recommendation {
  const reasonFactors = asReasonFactors(raw.reason)
  const resources = asStringList(raw.required_resources)

  return {
    department: String(raw.department ?? ''),
    task_label: String(raw.task_label ?? ''),
    service_name: String(raw.service_name ?? ''),
    expected_effect: String(raw.expected_effect ?? ''),
    difficulty: String(raw.difficulty ?? ''),
    required_resources: resources,
    opportunity_score: Number(raw.opportunity_score ?? 0),
    risk_score: Number(raw.risk_score ?? 0),
    risk_level: (raw.risk_level as Recommendation['risk_level']) ?? 'Low',
    decision: String(raw.decision ?? ''),
    decision_level: String(raw.decision_level ?? ''),
    decision_message: String(raw.decision_message ?? ''),
    required_action: String(raw.required_action ?? ''),
    reason: reasonFactors,
  }
}
