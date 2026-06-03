import type { AnalysisResult, UploadHistoryListResponse, Summary, DepartmentStat, Recommendation } from './types'
import { normalizeRecommendation } from './normalize'

/** Azure App Service (기본 우선) */
export const DEPLOYED_API_URL = 'https://llmz-team05.azurewebsites.net'

/** 로컬 uvicorn — 배포 API 실패 시 fallback */
export const LOCAL_API_URL = 'http://127.0.0.1:8000'

const envOverride = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '')

/** 마지막으로 성공한 API 베이스 (표시·디버깅용) */
let resolvedApiBase: string | null = null

export function getApiBaseUrl(): string {
  return resolvedApiBase ?? envOverride ?? DEPLOYED_API_URL
}

/** @deprecated getApiBaseUrl() 사용 */
export const API_BASE_URL = DEPLOYED_API_URL

const LAST_LOG_MONTH_KEY = 'llmz:lastLogMonth'
const HEALTH_PATH = '/api/health'
const PROBE_MS = 6000

function apiBaseCandidates(): string[] {
  if (envOverride) return [envOverride]
  return [DEPLOYED_API_URL, LOCAL_API_URL]
}

async function probeHealth(base: string): Promise<boolean> {
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), PROBE_MS)
    const res = await fetch(`${base}${HEALTH_PATH}`, {
      signal: controller.signal,
      method: 'GET',
    })
    clearTimeout(timer)
    return res.ok
  } catch {
    return false
  }
}

/** 배포 → 로컬 순으로 health 확인 후 베이스 URL 확정 */
export async function ensureApiBase(): Promise<string> {
  if (envOverride) {
    resolvedApiBase = envOverride
    return envOverride
  }
  if (resolvedApiBase) return resolvedApiBase

  for (const base of apiBaseCandidates()) {
    if (await probeHealth(base)) {
      resolvedApiBase = base
      return base
    }
  }

  resolvedApiBase = DEPLOYED_API_URL
  return DEPLOYED_API_URL
}

export function monthQuery(month?: string): string {
  return month ? `?month=${encodeURIComponent(month)}` : ''
}

/** 업로드 응답 log_months 또는 최근 12개월 스캔으로 데이터가 있는 YYYY-MM */
export async function resolveDashboardMonth(preferred?: string | null): Promise<string | undefined> {
  const candidates: string[] = []
  if (preferred?.match(/^\d{4}-\d{2}$/)) candidates.push(preferred)

  try {
    const stored = sessionStorage.getItem(LAST_LOG_MONTH_KEY)
    if (stored?.match(/^\d{4}-\d{2}$/) && !candidates.includes(stored)) {
      candidates.push(stored)
    }
  } catch {
    /* private mode 등 */
  }

  const now = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    if (!candidates.includes(key)) candidates.push(key)
  }

  for (const month of candidates) {
    const res = await getDashboardSummary(month)
    if (res.summary.total_logs > 0) return month
  }
  return preferred?.match(/^\d{4}-\d{2}$/) ? preferred : candidates[0]
}

export function rememberLogMonths(logMonths?: string[]) {
  if (!logMonths?.length) return
  try {
    sessionStorage.setItem(LAST_LOG_MONTH_KEY, logMonths[logMonths.length - 1])
  } catch {
    /* ignore */
  }
}

function shouldTryNextBase(error: unknown, res?: Response): boolean {
  if (apiBaseCandidates().length <= 1) return false
  if (error instanceof TypeError) return true
  if (error instanceof DOMException && error.name === 'AbortError') return true
  if (!res) return true
  return res.status === 403 || res.status >= 502
}

async function fetchJsonAtBase<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* non-json */
    }
    const err = new Error(detail || `요청 실패 (${res.status})`)
    ;(err as Error & { response?: Response }).response = res
    throw err
  }
  return res.json() as Promise<T>
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const bases = apiBaseCandidates()
  let lastError: Error | null = null

  for (let i = 0; i < bases.length; i++) {
    const base = bases[i]
    try {
      const data = await fetchJsonAtBase<T>(base, path, init)
      resolvedApiBase = base
      return data
    } catch (error) {
      const res = (error as Error & { response?: Response }).response
      lastError = error instanceof Error ? error : new Error(String(error))
      if (i < bases.length - 1 && shouldTryNextBase(error, res)) {
        continue
      }
      throw lastError
    }
  }

  throw lastError ?? new Error('API 연결 실패')
}

export async function analyzeSample(): Promise<AnalysisResult> {
  const res = await fetchJson<AnalysisResult & { recommendations?: Record<string, unknown>[] }>(
    '/api/analyze-sample',
  )
  const rawRecs = res.recommendations as unknown
  const recs = Array.isArray(rawRecs)
    ? rawRecs.map((row) => normalizeRecommendation(row as Record<string, unknown>))
    : []
  return { ...res, recommendations: recs }
}

export async function uploadCsv(
  file: File,
): Promise<AnalysisResult & { upload_id: string; log_months?: string[] }> {
  const formData = new FormData()
  formData.append('file', file)
  const result = await fetchJson<
    AnalysisResult & { upload_id: string; log_months?: string[]; recommendations?: Record<string, unknown>[] }
  >('/api/upload', { method: 'POST', body: formData })
  rememberLogMonths(result.log_months)
  const rawRecs = result.recommendations as unknown
  const recs = Array.isArray(rawRecs)
    ? rawRecs.map((row) => normalizeRecommendation(row as Record<string, unknown>))
    : []
  return { ...result, recommendations: recs }
}

export async function getUploadHistory(limit = 50, skip = 0): Promise<UploadHistoryListResponse> {
  return fetchJson(`/api/uploads/history?limit=${limit}&skip=${skip}`)
}

export async function getDashboardSummary(month?: string): Promise<{ summary: Summary }> {
  return fetchJson(`/api/dashboard/summary${monthQuery(month)}`)
}

export async function getDashboardDepartments(
  month?: string,
): Promise<{ department_stats: DepartmentStat[] }> {
  return fetchJson(`/api/dashboard/departments${monthQuery(month)}`)
}

export async function getDepartmentDetail(department: string, month?: string) {
  return fetchJson(
    `/api/dashboard/departments/${encodeURIComponent(department)}${monthQuery(month)}`,
  )
}

export async function getRecommendationsByDepartment(
  department: string,
  month?: string,
): Promise<{ department: string; count: number; recommendations: Recommendation[] }> {
  const res = await fetchJson<{
    department?: string
    count?: number
    recommendations?: Record<string, unknown>[]
  }>(`/api/recommendations/${encodeURIComponent(department)}${monthQuery(month)}`)

  const items = Array.isArray(res.recommendations) ? res.recommendations : []
  return {
    department: res.department ?? department,
    count: res.count ?? items.length,
    recommendations: items.map((row) => normalizeRecommendation(row)),
  }
}
