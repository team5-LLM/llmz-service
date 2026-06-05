import type {
  AnalysisResult,
  UploadHistoryListResponse,
  Summary,
  DepartmentStat,
  Recommendation,
  RiskDepartmentDetailResponse,
  RiskLevelsResponse,
  RiskOverviewResponse,
} from './types'

const DEFAULT_API_BASE_URL = 'https://llmz-team05.azurewebsites.net'

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL
).replace(/\/$/, '')

export async function analyzeSample(): Promise<AnalysisResult> {
  const res = await fetch(`${BASE_URL}/api/analyze-sample`)
  if (!res.ok) throw new Error('분석 데이터를 불러오지 못했습니다.')
  return res.json()
}

export async function uploadCsv(file: File): Promise<AnalysisResult & { upload_id: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE_URL}/api/upload`, { method: 'POST', body: formData })
  if (!res.ok) {
    if (res.status === 409) {
      const body = await res.json().catch(() => ({}))
      const err = new Error(body?.detail?.message ?? 'Duplicate file already processed')
      ;(err as Error & { isDuplicate: boolean }).isDuplicate = true
      throw err
    }
    throw new Error('파일 업로드에 실패했습니다.')
  }
  return res.json()
}

export async function getUploadHistory(limit = 50, skip = 0): Promise<UploadHistoryListResponse> {
  const res = await fetch(`${BASE_URL}/api/uploads/history?limit=${limit}&skip=${skip}`)
  if (!res.ok) throw new Error('업로드 이력을 불러오지 못했습니다.')
  return res.json()
}

// -- Dashboard 화면 --

// KPI 카드 데이터(총 프롬프트 수, 총 토큰, 총 비용)
// GET /api/dashboard/summary?month=YYYY-MM
export async function getDashboardSummary(month?: string): Promise<{ summary: Summary }> {
  const params = month ? `?month=${month}` : ''
  const res = await fetch(`${BASE_URL}/api/dashboard/summary${params}`)
  if (!res.ok) throw new Error('대시보드 요약 데이터를 불러오지 못했습니다.')
  return res.json()
}

// 부서별 업무 유형 차트, 토큰 도넛차트, 위험도 바차트
// GET /api/dashboard/departments?month=YYYY-MM 
export async function getDashboardDepartments(month?: string): Promise<{ department_stats: DepartmentStat[] }> {
  const params = month ? `?month=${month}` : ''
  const res = await fetch(`${BASE_URL}/api/dashboard/departments${params}`)
  if (!res.ok) throw new Error('부서 데이터를 불러오지 못했습니다.')
    return res.json()
}

// -- DepartmentDetail 화면 --

// 부서별 상세 - KPI 카드, 업무 유형 분포
// GET /api/dashboard/departments/{department}?month=YYYY-MM
export async function getDepartmentDetail(department: string, month?: string) {
  const params = month ? `?month=${month}` : ''
  const res = await fetch(`${BASE_URL}/api/dashboard/departments/${encodeURIComponent(department)}${params}`)
  if (!res.ok) throw new Error('부서 상세 데이터를 불러오지 못했습니다.')
  return res.json()
}

// 부서별 자동화 추천 리스트
// GET /api/recommendations/{department}
export async function getRecommendationsByDepartment(department: string, month?: string): Promise<{ recommendations: Recommendation[] }> {
  const params = month ? `?month=${month}` : ''
  const res = await fetch(`${BASE_URL}/api/recommendations/${encodeURIComponent(department)}${params}`)
  if (!res.ok) throw new Error('추천 데이터를 불러오지 못했습니다.')
  return res.json()
}

// -- Recommendation 화면 --
// 위의 getDashboardDepartments, getRecommendationByDepartment 사용

// -- Risk 화면 --

function monthQuery(month?: string): string {
  return month ? `?month=${encodeURIComponent(month)}` : ''
}

// GET /api/risk/overview?month=YYYY-MM
export async function getRiskOverview(month?: string): Promise<RiskOverviewResponse> {
  const res = await fetch(`${BASE_URL}/api/risk/overview${monthQuery(month)}`)
  if (!res.ok) throw new Error('위험도 요약 데이터를 불러오지 못했습니다.')
  return res.json()
}

// GET /api/risk/levels
export async function getRiskLevels(): Promise<RiskLevelsResponse> {
  const res = await fetch(`${BASE_URL}/api/risk/levels`)
  if (!res.ok) throw new Error('위험도 등급 정의를 불러오지 못했습니다.')
  return res.json()
}

// GET /api/risk/departments/{department}?month=YYYY-MM
export async function getRiskDepartmentDetail(
  department: string,
  month?: string,
): Promise<RiskDepartmentDetailResponse> {
  const res = await fetch(
    `${BASE_URL}/api/risk/departments/${encodeURIComponent(department)}${monthQuery(month)}`,
  )
  if (!res.ok) throw new Error(`부서 위험도 데이터를 불러오지 못했습니다. (${department})`)
  return res.json()
}
