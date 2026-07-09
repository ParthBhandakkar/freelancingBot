import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useToast } from '../components/Toast'

const columns = [
  { key: 'new', label: 'New', color: 'bg-yellow-100 text-yellow-800 border-yellow-200', icon: '🆕' },
  { key: 'contacted', label: 'Contacted', color: 'bg-blue-100 text-blue-800 border-blue-200', icon: '📞' },
  { key: 'qualified', label: 'Qualified', color: 'bg-purple-100 text-purple-800 border-purple-200', icon: '⭐' },
  { key: 'converted', label: 'Converted', color: 'bg-green-100 text-green-800 border-green-200', icon: '✅' },
  { key: 'lost', label: 'Lost', color: 'bg-red-100 text-red-800 border-red-200', icon: '❌' },
]

const channelMeta = {
  email: { icon: '📧', label: 'Email' },
  call: { icon: '📞', label: 'Call' },
  dm: { icon: '💬', label: 'DM' },
  research: { icon: '🔍', label: 'Research' },
}

export default function Pipeline() {
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [dragging, setDragging] = useState(null)
  const toast = useToast()

  useEffect(() => {
    api.getLeads({ limit: '200' }).then(setLeads).catch(console.error).finally(() => setLoading(false))
  }, [])

  const grouped = {}
  columns.forEach((col) => { grouped[col.key] = [] })
  leads.forEach((lead) => {
    const status = lead.status || 'new'
    if (grouped[status]) grouped[status].push(lead)
    else grouped['new'].push(lead)
  })

  const handleDrop = async (leadId, newStatus) => {
    setDragging(null)
    setLeads((prev) => prev.map((l) => l.id === leadId ? { ...l, status: newStatus } : l))
    try {
      await api.updateLead(leadId, { status: newStatus })
      toast.success(`Moved to ${newStatus}`)
    } catch (e) {
      toast.error(e.message)
      setLeads((prev) => prev.map((l) => l.id === leadId ? { ...l, status: prev.find((x) => x.id === leadId)?.status || l.status } : l))
    }
  }

  if (loading) return <div className="flex justify-center py-16"><div className="animate-spin text-3xl">⏳</div></div>

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Pipeline</h1>
      <div className="flex gap-4 overflow-x-auto pb-4" style={{ minHeight: '60vh' }}>
        {columns.map((col) => (
          <div
            key={col.key}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              const id = e.dataTransfer.getData('leadId')
              if (id) handleDrop(+id, col.key)
            }}
            className="flex-1 min-w-[220px] bg-gray-50 rounded-xl border border-gray-200"
          >
            <div className={`px-4 py-3 border-b border-gray-200 rounded-t-xl ${col.color.split(' ')[0]} bg-opacity-30`}>
              <h3 className="font-semibold text-sm flex items-center gap-2">
                {col.icon} {col.label}
                <span className="ml-auto text-xs text-gray-500 bg-white px-2 py-0.5 rounded-full">{grouped[col.key].length}</span>
              </h3>
            </div>
            <div className="p-2 space-y-2 min-h-[200px]">
              {grouped[col.key].map((lead) => {
                const ch = channelMeta[lead.channel] || channelMeta.research
                return (
                  <div
                    key={lead.id}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData('leadId', lead.id)
                      setDragging(lead.id)
                    }}
                    className={`bg-white rounded-lg border border-gray-200 p-3 cursor-grab active:cursor-grabbing hover:shadow-md transition-shadow ${dragging === lead.id ? 'opacity-50' : ''}`}
                  >
                    <Link to={`/leads/${lead.id}`} className="font-medium text-blue-600 hover:text-blue-800 text-sm block">
                      {lead.business_name}
                    </Link>
                    <p className="text-xs text-gray-500 mt-1">{lead.name}{lead.city ? ` · ${lead.city}` : ''}</p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="text-xs">{ch.icon} {ch.label}</span>
                      {lead.lead_score > 0 && (
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                          lead.lead_score >= 70 ? 'bg-green-100 text-green-700' :
                          lead.lead_score >= 30 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
                        }`}>
                          {lead.lead_score}
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
