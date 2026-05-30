import { useState, useRef, useEffect } from 'react'
import { uploadCsv, getUploadHistory } from '../api'
import type { UploadHistoryItem } from '../api/types'
import KpiCard from '../components/common/KpiCard'

type UploadState = 'idle' | 'processing' | 'success' | 'error'

const statusStyle: Record<UploadHistoryItem['status'], { bg: string; color: string }> = {
  '성공':   { bg: 'var(--color-primary)', color: 'var(--color-white)' },
  '처리중': { bg: '#FFB83E', color: 'var(--color-white)' },
  '실패':   { bg: 'var(--color-secondary)', color: 'var(--color-white)' },
}

function mapStatus(apiStatus: string): UploadHistoryItem['status'] {
  if (apiStatus === 'completed') return '성공'
  if (apiStatus === 'failed') return '실패'
  return '처리중'
}

const getFileExt = (filename: string) =>
  (filename.split('.').pop() ?? 'FILE').toUpperCase()

let localIdCounter = 1

const DataManagement = () => {
  const [files, setFiles] = useState<UploadHistoryItem[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [uploaderFilter, setUploaderFilter] = useState('')
  const [uploadState, setUploadState] = useState<UploadState>('idle')
  const [uploadErrorMsg, setUploadErrorMsg] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const nextIdRef = useRef(1000)

  useEffect(() => {
    getUploadHistory()
      .then(res => {
        const mapped: UploadHistoryItem[] = res.items.map((item, i) => ({
          id: i + 1,
          name: item.filename,
          date: item.uploaded_at.slice(0, 10),
          uploader: item.uploaded_by,
          status: mapStatus(item.status),
        }))
        setFiles(mapped)
        nextIdRef.current = mapped.length + 1
        localIdCounter = mapped.length + 1
      })
      .catch(() => {
        setFiles([])
      })
  }, [])

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (uploadState === 'idle') processFiles(Array.from(e.dataTransfer.files))
  }

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    processFiles(Array.from(e.target.files ?? []))
    e.target.value = ''
  }

  const processFiles = (picked: File[]) => {
    if (picked.length === 0) return

    const allCsv = picked.every(f => f.name.toLowerCase().endsWith('.csv'))

    const newItems: UploadHistoryItem[] = picked.map((f, i) => ({
      id: nextIdRef.current + i,
      name: f.name,
      date: new Date().toISOString().slice(0, 10),
      uploader: 'anonymous',
      status: '처리중',
    }))
    nextIdRef.current += picked.length
    setFiles(prev => [...prev, ...newItems])

    if (!allCsv) {
      setUploadState('error')
      setUploadErrorMsg('CSV 파일만 업로드할 수 있습니다.')
      const ids = new Set(newItems.map(item => item.id))
      setFiles(prev => prev.map(f => ids.has(f.id) ? { ...f, status: '실패' } : f))
      return
    }

    setUploadState('processing')

    uploadCsv(picked[0])
      .then(() => {
        const ids = new Set(newItems.map(item => item.id))
        setFiles(prev => prev.map(f => ids.has(f.id) ? { ...f, status: '성공' } : f))
        setUploadState('success')
      })
      .catch((err: Error) => {
        const ids = new Set(newItems.map(item => item.id))
        setFiles(prev => prev.map(f => ids.has(f.id) ? { ...f, status: '실패' } : f))
        setUploadState('error')
        setUploadErrorMsg(err.message)
      })
  }

  const filtered = files.filter(f => {
    const matchName = f.name.toLowerCase().includes(search.toLowerCase())
    const matchStatus = statusFilter ? f.status === statusFilter : true
    const matchUploader = f.uploader.includes(uploaderFilter)
    return matchName && matchStatus && matchUploader
  })

  const counts = {
    total:      files.length,
    success:    files.filter(f => f.status === '성공').length,
    failure:    files.filter(f => f.status === '실패').length,
    processing: files.filter(f => f.status === '처리중').length,
  }

  const renderUploadContent = () => {
    if (uploadState === 'processing') {
      return (
        <>
          <span className="material-symbols-outlined text-4xl animate-spin text-primary">
            progress_activity
          </span>
          <p className="text-sm font-medium text-primary">업로드 진행중...</p>
          <p className="text-xs" style={{ color: 'var(--color-gray-500)' }}>파일을 서버에 업로드하고 있습니다</p>
        </>
      )
    }
    if (uploadState === 'success') {
      return (
        <>
          <p className="text-sm font-bold text-primary">분석 완료</p>
          <div className="w-10 h-10 rounded-full flex items-center justify-center bg-primary">
            <span className="material-symbols-outlined text-xl text-white">check</span>
          </div>
          <p className="text-xs" style={{ color: 'var(--color-gray-500)' }}>대시보드가 성공적으로 업데이트 되었습니다.</p>
          <button
            className="mt-2 px-4 py-1.5 rounded-md text-xs font-medium border text-primary border-primary"
            onClick={(e) => { e.stopPropagation(); setUploadState('idle') }}
          >
            새 파일 업로드
          </button>
        </>
      )
    }
    if (uploadState === 'error') {
      return (
        <>
          <span className="material-symbols-outlined text-4xl text-secondary">
            error
          </span>
          <p className="text-sm font-medium text-secondary">업로드 실패</p>
          <p className="text-xs text-center" style={{ color: 'var(--color-gray-500)' }}>{uploadErrorMsg}</p>
          <button
            className="mt-2 px-4 py-1.5 rounded-md text-sm font-medium bg-secondary-light text-secondary"
            onClick={(e) => { e.stopPropagation(); setUploadState('idle') }}
          >
            다시 시도
          </button>
        </>
      )
    }
    return (
      <>
        <span className="material-symbols-outlined text-4xl text-gray-500">
          upload_file
        </span>
        <p className="text-sm" style={{ color: 'var(--color-gray-500)' }}>
          Drag &amp; Drop 또는 클릭하여 파일을 업로드하세요
        </p>
        <p className="text-xs" style={{ color: 'var(--color-gray-500)' }}>지원 형식: CSV</p>
        <button
          className="mt-2 px-5 py-2 rounded-md text-sm font-medium text-white transition-opacity hover:opacity-90 bg-primary"
          onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click() }}
        >
          업로드
        </button>
      </>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-bold text-xxl text-black">데이터 업로드</h1>

      {/* 업로드 영역 */}
      <div className="bg-white rounded-lg p-6">
        <div
          className="rounded-lg p-12 flex flex-col items-center justify-center gap-3 transition-colors"
          style={{
            border: `2px dashed ${isDragging ? 'var(--color-primary)' : 'var(--color-gray-500)'}`,
            backgroundColor: isDragging ? 'var(--color-primary-light)' : 'var(--color-bg)',
            cursor: uploadState === 'idle' ? 'pointer' : 'default',
            minHeight: '200px',
          }}
          onDragOver={(e) => { if (uploadState === 'idle') { e.preventDefault(); setIsDragging(true) } }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => { if (uploadState === 'idle') fileInputRef.current?.click() }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={handleFileInput}
          />
          {renderUploadContent()}
        </div>
      </div>

      {/* 데이터 입력 이력 */}
      <div className="flex flex-col gap-4">
        <h2 className="font-bold text-xl text-black">데이터 입력 이력</h2>

        <div className="grid grid-cols-4 gap-4">
          <KpiCard label="전체 수집 건수" value={`${counts.total}건`} />
          <KpiCard label="성공" value={`${counts.success}건`} />
          <KpiCard label="실패" value={`${counts.failure}건`} />
          <KpiCard label="처리중" value={`${counts.processing}건`} />
        </div>

        {/* 수집 이력 목록 */}
        <div className="bg-white rounded-lg p-6">
          <p className="text-sm font-medium text-black mb-4">수집 이력 목록</p>

          {/* 필터 행 */}
          <div className="flex gap-3 mb-5">
            <div className="flex items-center gap-2 px-4 py-2 rounded-full flex-1 max-w-xs bg-bg border border-gray-100">
              <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-gray-500)' }}>search</span>
              <input
                type="text"
                placeholder="파일명 검색"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="bg-transparent text-sm outline-none w-full"
              />
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-bg border border-gray-100">
              <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-gray-500)' }}>filter_list</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-transparent text-sm outline-none"
              >
                <option value="">전체 상태</option>
                <option value="성공">성공</option>
                <option value="실패">실패</option>
                <option value="처리중">처리중</option>
              </select>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-bg border border-gray-100">
              <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-gray-500)' }}>person</span>
              <input
                type="text"
                placeholder="업로더"
                value={uploaderFilter}
                onChange={(e) => setUploaderFilter(e.target.value)}
                className="bg-transparent text-sm outline-none w-20"
              />
            </div>
          </div>

          {/* 테이블 */}
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {['유형', '파일명', '수집일시', '업로더', '처리상태', '비고'].map((h) => (
                  <th key={h} className="py-2 pr-4 text-left font-medium text-xs" style={{ color: 'var(--color-gray-500)' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((file) => {
                const s = statusStyle[file.status]
                return (
                  <tr key={file.id} className="border-b border-bg">
                    <td className="py-3 pr-4">
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-primary-light text-primary">
                        {getFileExt(file.name)}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-sm text-black">{file.name}</td>
                    <td className="py-3 pr-4 text-sm" style={{ color: 'var(--color-gray-500)' }}>{file.date}</td>
                    <td className="py-3 pr-4 text-sm text-black">{file.uploader}</td>
                    <td className="py-3 pr-4">
                      <span
                        className="px-3 py-0.5 rounded-full text-xs font-medium"
                        style={{ backgroundColor: s.bg, color: s.color }}
                      >
                        {file.status}
                      </span>
                    </td>
                    <td className="py-3 text-sm" style={{ color: 'var(--color-gray-500)' }}>
                      {file.status === '성공' ? '—' : ''}
                    </td>
                  </tr>
                )
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-sm" style={{ color: 'var(--color-gray-500)' }}>
                    {files.length === 0 ? '업로드 이력이 없습니다.' : '검색 결과가 없습니다.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default DataManagement
