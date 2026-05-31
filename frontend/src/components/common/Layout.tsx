import { type ReactNode } from 'react'
import Header from './Header'
import SideBar from './SideBar'

interface LayoutProps {
  children: ReactNode
}

const Layout = ({ children }: LayoutProps) => {
  return (
    <div className="flex h-screen bg-bg">
      <SideBar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto p-[30px]">
          <div className="min-w-[900px]">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}

export default Layout
