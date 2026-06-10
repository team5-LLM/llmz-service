export type RiskLevel = 'Low' | 'Medium' | 'High' | 'Critical'

export interface DepartmentStat {
  department: string
  total_requests: number
  total_tokens: number
  total_cost: number
  user_count: number
  avg_risk_score: number
  risk_level: RiskLevel
  high_critical_ratio: number
  task_distribution: { label: string; label_display: string; count: number; ratio: number }[]
}

export interface Summary {
  total_logs: number
  departments: number
  total_tokens: number
  total_cost: number
  avg_risk_score: number
}

export interface Recommendation {
  department: string
  task_label: string
  service_name: string
  expected_effect: string
  difficulty: string
  required_resources: string[]
  opportunity_score: number
  risk_score: number
  risk_level: RiskLevel
  decision: string
  decision_level: string
  decision_message: string
  required_action: string
  reason: { factor: string; value: number; unit: string; description: string }[]
}

export interface ClusterRecommendationCard {
  department: string
  sub_cluster_id: string
  recommendation_title: string
  automation_candidate_type: string
  macro_category: string
  opportunity_score: number
  risk_score: number
  decision: string
  summary: string
  expected_effect: string[]
  security_guardrails: string[]
  implementation_difficulty: string
  priority_reason: string
  source_cluster_label: string
  method: string
}

export type AutomationRecommendation = Recommendation | ClusterRecommendationCard

export interface AnalysisResult {
  summary: Summary
  department_stats: DepartmentStat[]
  recommendations: Recommendation[]
  cluster_profiles?: Record<string, unknown>[]
  cluster_recommendations?: ClusterRecommendationCard[]
  recommendation_cards?: ClusterRecommendationCard[]
  sample_masked_logs: Record<string, unknown>[]
}

export interface RecommendationResponse {
  department?: string
  count: number
  recommendations: Recommendation[]
  cluster_profiles?: Record<string, unknown>[]
  cluster_recommendations?: ClusterRecommendationCard[]
  recommendation_cards?: ClusterRecommendationCard[]
}

export interface UploadHistoryItem {
  id: number
  name: string
  date: string
  uploader: string
  status: '성공' | '실패' | '처리중'
  note?: string
}

export interface ApiUploadHistoryItem {
  upload_id: string
  filename: string
  uploaded_at: string
  uploaded_by: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  total_rows: number
  valid_rows: number
  invalid_rows: number
  duration_ms?: number
  completed_at?: string
  error_message?: string
  summary?: Summary
}

export interface UploadHistoryListResponse {
  items: ApiUploadHistoryItem[]
  total: number
  limit: number
  skip: number
}

// -- Risk 화면 --

export type SensitiveCategory = 'personal_info' | 'customer_info' | 'confidential' | 'source_code' | 'finance_legal'

export interface SensitiveBreakdownItem {
  category: SensitiveCategory
  label: string
  count: number
  ratio: number
}

export interface DepartmentRiskItem {
  department: string
  avg_risk_score: number
  risk_level: RiskLevel
}

export interface DepartmentRiskWithBreakdown extends DepartmentRiskItem {
  sensitive_breakdown: SensitiveBreakdownItem[]
}

export interface RiskOverviewSummary {
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  total_departments: number
}

export interface RiskOverviewResponse {
  period: { from_date: string; to_date: string }
  summary: RiskOverviewSummary
  critical_departments: DepartmentRiskItem[]
  high_departments: DepartmentRiskItem[]
  all_departments: DepartmentRiskWithBreakdown[]
}

export interface RiskLevelDefinition {
  level: RiskLevel
  score_range: string
  meaning: string
  recommended_action: string
}

export interface RiskLevelsResponse {
  levels: RiskLevelDefinition[]
}
