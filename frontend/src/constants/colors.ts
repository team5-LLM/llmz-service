// index.css @theme 의 색상값과 동일하게 유지
// CSS 변수를 지원하지 않는 곳(recharts 등)에서 사용

export const COLORS = {
  // 메인
  primary: '#165EFF',
  primaryLight: '#DFE7FF',
  secondary: '#F14E3C',
  secondaryLight: '#F8EAE7',

  // 차트
  chartPink: '#FFCEDF',
  chartCoral: '#FEB7A7',
  chartGreen: '#C4DEC8',
  chartBlue: '#9CB5FF',
  chartPurple: '#BDADEC',

  // 위험도
  riskLow: '#D8F1CF',
  riskMedium: '#FFF2C9',
  riskHigh: '#FFC9C9',
  riskCritical: '#E0D2F8',

  // 뉴트럴
  gray100: '#E0E0E0',
  gray500: '#CCCCCC',
  bg: '#F5F6FA',
  white: '#FFFFFF',
  black: '#2C2C2C',
} as const

// 차트 색상
export const CHART_COLORS = [
  COLORS.chartBlue,
  COLORS.chartPink,
  COLORS.chartGreen,
  COLORS.chartCoral,
  COLORS.chartPurple,
  COLORS.gray100,
] as const

// 업무 유형별 색상
export const WORK_TYPE_COLORS: Record<string, string> = {
  '보고서 작성형': COLORS.chartPink,
  '코드 생성형': COLORS.chartCoral,
  '문서 요약형': COLORS.chartGreen,
  '고객 응대형': COLORS.chartBlue,
  '단순 검색/질문형': COLORS.chartPurple,
}

// 위험도별 색상
export const RISK_COLORS: Record<string, string> = {
  Low: COLORS.riskLow,
  Medium: COLORS.riskMedium,
  High: COLORS.riskHigh,
  Critical: COLORS.riskCritical,
}
