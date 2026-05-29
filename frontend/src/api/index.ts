import type { AnalysisResult, UploadHistoryListResponse } from './types'

const BASE_URL = 'http://localhost:8000'

export async function analyzeSample(): Promise<AnalysisResult> {
  const res = await fetch(`${BASE_URL}/api/analyze-sample`)
  if (!res.ok) throw new Error('분석 데이터를 불러오지 못했습니다.')
  return res.json()
}

export async function uploadCsv(file: File): Promise<AnalysisResult & { upload_id: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE_URL}/api/upload`, { method: 'POST', body: formData })
  if (!res.ok) throw new Error('파일 업로드에 실패했습니다.')
  return res.json()
}

export async function getUploadHistory(limit = 50, skip = 0): Promise<UploadHistoryListResponse> {
  const res = await fetch(`${BASE_URL}/api/uploads/history?limit=${limit}&skip=${skip}`)
  if (!res.ok) throw new Error('업로드 이력을 불러오지 못했습니다.')
  return res.json()
}
