import { useState, useEffect } from 'react'
import { api } from '../api'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

function StatCard({ label, value, color }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getDashboardStats().then(setStats).catch(console.error).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin text-4xl">⏳</div></div>
  if (!stats) return <div className="text-red-500">Failed to load dashboard</div>

  const platformData = Object.entries(stats.leads_by_platform).map(([name, value]) => ({ name, value }))
  const statusData = Object.entries(stats.leads_by_status).map(([name, value]) => ({ name, value }))

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
        <StatCard label="Total Leads" value={stats.total_leads} color="text-blue-600" />
        <StatCard label="New" value={stats.new_leads} color="text-yellow-600" />
        <StatCard label="Contacted" value={stats.contacted} color="text-purple-600" />
        <StatCard label="Responded" value={stats.responded} color="text-green-600" />
        <StatCard label="Converted" value={stats.converted} color="text-emerald-600" />
        <StatCard label="Assets Made" value={stats.assets_generated} color="text-indigo-600" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Avg. Presence Score</h3>
          <div className="flex items-center gap-3">
            <div className="relative w-24 h-24">
              <svg className="w-24 h-24 -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15.5" fill="none" stroke="#e5e7eb" strokeWidth="3" />
                <circle cx="18" cy="18" r="15.5" fill="none" stroke="#3b82f6" strokeWidth="3"
                  strokeDasharray={`${stats.avg_presence_score}, 100`} strokeLinecap="round" />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-xl font-bold text-blue-600">
                {stats.avg_presence_score}
              </span>
            </div>
            <p className="text-sm text-gray-500">out of 100</p>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Leads by Platform</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={platformData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                {platformData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Leads by Status</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={statusData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {statusData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {stats.leads_by_city.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Top Cities</h3>
          <div className="flex flex-wrap gap-3">
            {stats.leads_by_city.map((item) => (
              <span key={item.city} className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-full text-sm font-medium">
                {item.city} ({item.count})
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
