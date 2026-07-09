import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'

const navItems = [
  { to: '/today', label: 'Today', icon: '📋' },
  { to: '/dashboard', label: 'Dashboard', icon: '📊' },
  { to: '/leads', label: 'Leads', icon: '👥' },
  { to: '/pipeline', label: 'Pipeline', icon: '🏗️' },
  { to: '/search', label: 'Find Leads', icon: '🔍' },
  { to: '/outreach', label: 'Outreach', icon: '📧' },
  { to: '/settings', label: 'Settings', icon: '⚙️' },
]

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className={`${collapsed ? 'w-16' : 'w-60'} bg-slate-900 text-white transition-all duration-200 flex flex-col shrink-0`}>
        <div className="p-4 border-b border-slate-700 flex items-center gap-2">
          <span className="text-xl">🚀</span>
          {!collapsed && <span className="font-bold text-lg">LeadFinder</span>}
        </div>
        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/today'}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                item.to === '/today'
                  ? location.pathname === '/today'
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  : location.pathname.startsWith(item.to)
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <span>{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-3 border-t border-slate-700 text-slate-400 hover:text-white text-sm shrink-0"
        >
          {collapsed ? '→' : '← Collapse'}
        </button>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
