import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  TrendingUp,
  Search,
  DollarSign,
  Cloud,
  Settings as SettingsIcon,
  Zap,
  ChevronLeft,
  ChevronRight,
  BarChart3,
  Target,
  Users,
  Gauge,
} from 'lucide-react'

export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [isCollapsed, setIsCollapsed] = useState(false)

  const menuItems = [
    {
      name: 'Dashboard',
      icon: BarChart3,
      path: '/dashboard',
      color: 'text-modernGray-700 hover:bg-white',
    },
    {
      name: 'Analytics',
      icon: TrendingUp,
      path: '/analytics',
      color: 'text-modernTeal-700 hover:bg-white',
    },
    {
      name: 'KPI Dashboard',
      icon: Target,
      path: '/kpi',
      color: 'text-brandRed-700 hover:bg-white',
    },
    {
      name: 'Unit Costs',
      icon: Users,
      path: '/unit-costs',
      color: 'text-modernTeal-700 hover:bg-white',
    },
    {
      name: 'Right-Sizing',
      icon: Gauge,
      path: '/rightsizing',
      color: 'text-modernGreen-700 hover:bg-white',
    },
    {
      name: 'FinOps Audit',
      icon: Search,
      path: '/finops-audit',
      color: 'text-brandRed-700 hover:bg-white',
    },
    {
      name: 'Automation',
      icon: Zap,
      path: '/automation',
      color: 'text-modernGreen-700 hover:bg-white',
    },
    {
      name: 'Budgets',
      icon: DollarSign,
      path: '/budgets',
      color: 'text-modernYellow-700 hover:bg-white',
    },
    {
      name: 'Accounts',
      icon: Cloud,
      path: '/aws-accounts',
      color: 'text-modernGray-700 hover:bg-white',
    },
    {
      name: 'Settings',
      icon: SettingsIcon,
      path: '/settings',
      color: 'text-modernGray-700 hover:bg-white',
    },
  ]

  const isActive = (path: string) => {
    return location.pathname === path
  }

  return (
    <div
      className={`fixed left-0 top-0 h-full bg-modernGray-50 border-r border-modernGray-200 transition-all duration-300 ease-in-out ${
        isCollapsed ? 'w-16' : 'w-64'
      } flex flex-col shadow-lg z-40`}
    >
      {/* Header */}
      <div className="p-4 border-b border-modernGray-200 bg-white flex items-center justify-between">
        {!isCollapsed && (
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-8 h-8 bg-gradient-to-br from-brandRed-600 to-brandRed-800 rounded-lg flex items-center justify-center shadow-md">
                <span className="text-white font-bold text-sm">AC</span>
              </div>
              <div className="absolute -left-1 top-1 w-1.5 h-6 bg-brandRed-700 rounded-r"></div>
            </div>
            <div>
              <h1 className="font-bold text-brandRed-700 text-sm tracking-tight">AWS Cost</h1>
              <p className="text-xs text-modernGray-600">Dashboard</p>
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="p-1.5 hover:bg-modernGray-100 rounded-lg transition-all duration-200"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? (
            <ChevronRight className="w-4 h-4 text-modernGray-600" />
          ) : (
            <ChevronLeft className="w-4 h-4 text-modernGray-600" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4">
        <ul className="space-y-1 px-3">
          {menuItems.map((item) => {
            const Icon = item.icon
            const active = isActive(item.path)

            return (
              <li key={item.path} className="group">
                <button
                  type="button"
                  onClick={() => navigate(item.path)}
                  className={`w-full flex items-center gap-3 px-3 py-3 rounded-card transition-all duration-200 ${
                    active
                      ? 'bg-white border-l-2 border-brandRed-700 text-brandRed-700 font-semibold shadow-md translate-x-1'
                      : `${item.color} border-l-2 border-transparent hover:translate-x-1`
                  } ${isCollapsed ? 'justify-center' : ''} hover:shadow-md`}
                  title={isCollapsed ? item.name : ''}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  {!isCollapsed && <span className="text-sm font-medium">{item.name}</span>}
                </button>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Footer */}
      {!isCollapsed && (
        <div className="p-4 border-t border-modernGray-200 bg-white">
          <div className="text-xs text-modernGray-600 text-center">
            <p className="font-semibold text-modernGray-800">AWS Cost Dashboard</p>
            <p className="mt-1">v1.0.0</p>
          </div>
        </div>
      )}
    </div>
  )
}
