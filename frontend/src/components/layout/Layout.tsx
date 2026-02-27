import { ReactNode, createContext, useContext, useState } from 'react'
import { Sidebar } from './Sidebar'

interface LayoutContextType {
  isSidebarCollapsed: boolean
  setIsSidebarCollapsed: (collapsed: boolean) => void
}

const LayoutContext = createContext<LayoutContextType>({
  isSidebarCollapsed: false,
  setIsSidebarCollapsed: () => {},
})

export const useLayout = () => useContext(LayoutContext)

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)

  return (
    <LayoutContext.Provider value={{ isSidebarCollapsed, setIsSidebarCollapsed }}>
      <div className="min-h-screen bg-gray-50">
        <Sidebar />
        <main
          className="transition-all duration-300 ease-in-out"
          style={{
            marginLeft: isSidebarCollapsed ? '4rem' : '16rem',
          }}
        >
          {children}
        </main>
      </div>
    </LayoutContext.Provider>
  )
}
