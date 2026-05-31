import { NavLink, useLocation } from 'react-router-dom'

const navItems = [
  { label: '메인 대시보드', icon: 'space_dashboard', path: '/dashboard' },
  { label: '부서별 상세', icon: 'data_table', path: '/department' },
  { label: '자동화 추천', icon: 'lightbulb', path: '/recommendation' },
  { label: '위험도', icon: 'add_moderator', path: '/risk' },
  { label: '데이터 관리', icon: 'action_key', path: '/dataManagement' },
]

const SideBar = () => {
  const location = useLocation()

  const getIsActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + '/')

  const navClass = (path: string) => {
    const active = getIsActive(path)
    return `flex items-center gap-3 px-[16px] py-[13px] rounded-sm text-md font-medium transition-colors ${
      active
        ? 'bg-primary-light text-primary'
        : 'text-black hover:bg-gray-50'
    }`
  }

  return (
    <aside className="w-[240px] h-screen bg-white flex flex-col shrink-0 shadow-md">
      {/* 로고 */}
      <div className="h-[74px] flex justify-center items-center">
        <span className="font-bold text-md text-black">로고</span>
      </div>

      {/* 네비게이션 */}
      <nav className="flex flex-col flex-1 px-6">
        {navItems.map((item) => (
          <NavLink key={item.path} to={item.path} className={() => navClass(item.path)}>
            <span className="material-symbols-outlined text-xl leading-none">
              {item.icon}
            </span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* 설정 */}
      <div className="px-4 pb-4">
        <NavLink to="/settings" className={() => navClass('/settings')}>
          <span className="material-symbols-outlined text-xl leading-none">
            settings
          </span>
          설정
        </NavLink>
      </div>
    </aside>
  )
}

export default SideBar