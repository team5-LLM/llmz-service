import { useEffect, useState } from 'react'
import { analyzeSample } from '../api'
import type { DepartmentStat, RiskLevel } from '../api/types'


const levelStyle: Record<RiskLevel, { bg: string; color: string }> = {
  Low:      { bg: '#D8F1CF', color: '#2d6a2d' },
  Medium:   { bg: '#FFF2C9', color: '#856c00' },
  High:     { bg: '#FFC9C9', color: '#8b0000' },
  Critical: { bg: '#E0D2F8', color: '#4b0082' },
}

const legendItems = [
  { label: '개인정보', color: '#FFCEDF' },
  { label: '고객정보', color: '#FEB7A7' },
  { label: '기밀정보', color: '#C4DEC8' },
  { label: '소스코드', color: '#9CB5FF' },
  { label: '재무/법무', color: '#BDADEC' },
]

const BAR_COLORS = ['#FFCEDF', '#FEB7A7', '#C4DEC8', '#9CB5FF', '#BDADEC']

// task_distribution 비율을 5개 색상 세그먼트에 분배 (시각적 표현용)
function deriveBars(stat: DepartmentStat): { ratio: number; color: string }[] {
  const dist = stat.task_distribution
  const ratios = dist.slice(0, 5).map(t => t.ratio)
  while (ratios.length < 5) ratios.push(0)
  const sum = ratios.reduce((a, b) => a + b, 0)
  const normalized = sum > 0 ? ratios.map(r => (r / sum) * 100) : [20, 20, 20, 20, 20]
  return normalized
    .map((ratio, i) => ({ ratio, color: BAR_COLORS[i] }))
    .sort((a, b) => b.ratio - a.ratio)
}

