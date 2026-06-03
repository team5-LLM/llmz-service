import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { error: Error | null }

/** 라우트 단위 렌더 오류 시 흰 화면 대신 메시지 표시 */
export default class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Route render error:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-lg border border-secondary/30 bg-secondary-light p-6 text-secondary">
          <p className="font-bold text-lg mb-2">화면을 불러오지 못했습니다</p>
          <p className="text-sm mb-4">{this.state.error.message}</p>
          <button
            type="button"
            className="px-4 py-2 rounded-sm bg-primary text-white text-sm"
            onClick={() => this.setState({ error: null })}
          >
            다시 시도
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
