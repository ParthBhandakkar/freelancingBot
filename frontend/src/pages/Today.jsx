import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useToast } from '../components/Toast'

const channelMeta = {
  email: { icon: '📧', label: 'Email', color: 'bg-blue-100 text-blue-800 border-blue-200' },
  call: { icon: '📞', label: 'Call', color: 'bg-green-100 text-green-800 border-green-200' },
  dm: { icon: '💬', label: 'DM', color: 'bg-purple-100 text-purple-800 border-purple-200' },
  research: { icon: '🔍', label: 'Research', color: 'bg-yellow-100 text-yellow-800 border-yellow-200' },
}

const statusColors = {
  new: 'bg-yellow-100 text-yellow-800',
  contacted: 'bg-blue-100 text-blue-800',
  qualified: 'bg-purple-100 text-purple-800',
  converted: 'bg-green-100 text-green-800',
  lost: 'bg-red-100 text-red-800',
}

export default function Today() {
  const [dueFollowups, setDueFollowups] = useState([])
  const [hotLeads, setHotLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [logNote, setLogNote] = useState({})
  const toast = useToast()

  useEffect(() => {
    Promise.all([
      api.getDueSequences().catch(() => ({ due: [] })),
      api.getLeads({ status: 'new', sort_by: 'lead_score', sort_dir: 'desc', limit: '50' }).catch(() => []),
    ]).then(([due, leads]) => {
      setDueFollowups(due.due || [])
      setHotLeads(leads)
    }).catch(console.error).finally(() => setLoading(false))
  }, [])

  const handleLogTouch = async (leadId, channel) => {
    try {
      await api.logTouch(leadId, channel, logNote[leadId] || '')
      toast.success(`Logged ${channel} touch`)
      setLogNote((prev) => ({ ...prev, [leadId]: '' }))
      setHotLeads((prev) => prev.filter((l) => l.id !== leadId))
    } catch (e) {
      toast.error(e.message)
    }
  }

  const channelGroups = { email: [], call: [], dm: [], research: [] }
  hotLeads.forEach((lead) => {
    const ch = lead.channel || 'research'
    if (channelGroups[ch]) channelGroups[ch].push(lead)
  })

  if (loading) return <div className="flex justify-center py-16"><div className="animate-spin text-3xl">⏳</div></div>

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Today</h1>

      {dueFollowups.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-gray-700 mb-3 flex items-center gap-2">
            <span className="w-2 h-2 bg-orange-500 rounded-full"></span>
            Follow-ups Due ({dueFollowups.length})
          </h2>
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            {dueFollowups.map((item) => (
              <div key={item.step_id} className="px-4 py-3 border-b border-gray-100 last:border-0 flex items-center justify-between">
                <div>
                  <Link to={`/leads/${item.lead_id}`} className="font-medium text-blue-600 hover:text-blue-800">
                    {item.business_name}
                  </Link>
                  <p className="text-xs text-gray-500">
                    Step {item.step_order + 1} · {item.action_type}
                    {item.subject && ` · ${item.subject}`}
                  </p>
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${channelMeta[item.lead_channel]?.color || 'bg-gray-100 text-gray-600'}`}>
                  {channelMeta[item.lead_channel]?.icon} {channelMeta[item.lead_channel]?.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-6">
        {Object.entries(channelGroups).map(([channel, leads]) => {
          if (leads.length === 0) return null
          const meta = channelMeta[channel]
          return (
            <div key={channel}>
              <h2 className="text-lg font-semibold text-gray-700 mb-3 flex items-center gap-2">
                {meta.icon} {meta.label} Queue ({leads.length})
              </h2>
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                {leads.map((lead) => (
                  <div key={lead.id} className="px-4 py-3 border-b border-gray-100 last:border-0">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <Link to={`/leads/${lead.id}`} className="font-medium text-blue-600 hover:text-blue-800">
                            {lead.business_name}
                          </Link>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[lead.status] || 'bg-gray-100'}`}>
                            {lead.status}
                          </span>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${meta.color}`}>
                            {meta.icon} {meta.label}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          {lead.city && <span>{lead.city} · </span>}
                          {lead.niche && <span>{lead.niche} · </span>}
                          Score: {lead.online_presence_score || '-'}
                          {lead.lead_score > 0 && ` · Lead: ${lead.lead_score}`}
                        </p>
                        {lead.analysis_notes && <p className="text-xs text-gray-400 mt-1 line-clamp-1">{lead.analysis_notes}</p>}
                        {lead.flaws && <p className="text-xs text-gray-400 mt-1 line-clamp-1">{lead.flaws}</p>}
                      </div>
                      <div className="flex flex-col gap-1.5 shrink-0">
                        <Link to={`/leads/${lead.id}`}
                          className="px-3 py-1 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-xs font-medium text-center">
                          Open
                        </Link>
                        <button onClick={() => handleLogTouch(lead.id, channel)}
                          className="px-3 py-1 border border-gray-300 rounded-lg hover:bg-gray-50 text-xs">
                          Mark Contacted
                        </button>
                      </div>
                    </div>
                    <div className="mt-2">
                      <input
                        type="text" placeholder="Quick note (optional)..."
                        value={logNote[lead.id] || ''}
                        onChange={(e) => setLogNote((prev) => ({ ...prev, [lead.id]: e.target.value }))}
                        className="w-full px-2 py-1 border border-gray-200 rounded text-xs"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}

        {dueFollowups.length === 0 && hotLeads.filter((l) => (l.channel || 'research') !== 'research').length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-5xl mb-3">✅</p>
            <p className="text-lg font-medium">Nothing to do right now</p>
            <p className="text-sm">Import some leads on the Find Leads page to get started.</p>
          </div>
        )}
      </div>
    </div>
  )
}
