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
  task_distribution: { label: string; label_display?: string; count: number; ratio: number }[]
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
  task_label_display?: string
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
  recommendation_source?: 'cluster' | 'task'
  cluster_label?: string
  summary?: string
}

export interface AnalysisResult {
  summary: Summary
  department_stats: DepartmentStat[]
  recommendations: Recommendation[]
  sample_masked_logs: Record<string, unknown>[]
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

export type SensitiveCategory =
  | 'personal_info'
  | 'customer_info'
  | 'confidential'
  | 'source_code'
  | 'finance_legal'

export interface DashboardPeriod {
  from_date: string
  to_date: string
}

export interface DepartmentRiskItem {
  department: string
  avg_risk_score: number
  risk_level: RiskLevel
}

export interface RiskOverviewSummary {
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  total_departments: number
}

export interface RiskOverviewResponse {
  period: DashboardPeriod
  summary: RiskOverviewSummary
  all_departments: DepartmentRiskItem[]
  critical_departments: DepartmentRiskItem[]
  high_departments: DepartmentRiskItem[]
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

export interface SensitiveBreakdownItem {
  category: SensitiveCategory
  label: string
  count: number
  ratio: number
}

export interface RiskDepartmentDetailResponse {
  department: string
  period: DashboardPeriod
  risk_score: number
  risk_level: RiskLevel
  high_critical_ratio: number
  sensitive_breakdown: SensitiveBreakdownItem[]
}
