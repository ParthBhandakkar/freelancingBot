import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useToast } from '../components/Toast'

const statusColors = {
  new: 'bg-yellow-100 text-yellow-800',
  contacted: 'bg-blue-100 text-blue-800',
  qualified: 'bg-purple-100 text-purple-800',
  converted: 'bg-green-100 text-green-800',
  lost: 'bg-red-100 text-red-800',
}

const channelMeta = {
  email: { icon: '📧', label: 'Email', color: 'bg-blue-100 text-blue-700' },
  call: { icon: '📞', label: 'Call', color: 'bg-green-100 text-green-700' },
  dm: { icon: '💬', label: 'DM', color: 'bg-purple-100 text-purple-700' },
  research: { icon: '🔍', label: 'Research', color: 'bg-yellow-100 text-yellow-700' },
}

export default function Leads() {
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [platformFilter, setPlatformFilter] = useState('')
  const [minScore, setMinScore] = useState('')
  const [sortBy, setSortBy] = useState('created_at')
  const [sortDir, setSortDir] = useState('desc')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', business_name: '', platform: 'instagram', profile_url: '', website_url: '', city: '', niche: '', phone: '', email: '' })
  const [selected, setSelected] = useState(new Set())
  const toast = useToast()

  const loadLeads = () => {
    setLoading(true)
    const params = { search, status: statusFilter, platform: platformFilter, sort_by: sortBy, sort_dir: sortDir }
    if (minScore) params.min_score = minScore
    api.getLeads(params).then(setLeads).catch(console.error).finally(() => setLoading(false))
  }

  useEffect(() => { loadLeads() }, [search, statusFilter, platformFilter, minScore, sortBy, sortDir])

  const handleCreate = async (e) => {
    e.preventDefault()
    await api.createLead(form)
    setShowForm(false)
    setForm({ name: '', business_name: '', platform: 'instagram', profile_url: '', website_url: '', city: '', niche: '', phone: '', email: '' })
    toast.success('Lead created')
    loadLeads()
  }

  const handleDelete = async (id) => {
    await api.deleteLead(id)
    toast.success('Lead deleted')
    loadLeads()
  }

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selected.size === leads.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(leads.map((l) => l.id)))
    }
  }

  const bulkDelete = async () => {
    if (selected.size === 0) return
    let count = 0
    for (const id of selected) {
      try {
        await api.deleteLead(id)
        count++
      } catch (e) { /* skip */ }
    }
    toast.success(`Deleted ${count} lead(s)`)
    setSelected(new Set())
    loadLeads()
  }

  const bulkStatusChange = async (newStatus) => {
    if (selected.size === 0) return
    let count = 0
    for (const id of selected) {
      try {
        await api.updateLead(id, { status: newStatus })
        count++
      } catch (e) { /* skip */ }
    }
    toast.success(`Moved ${count} lead(s) to ${newStatus}`)
    setSelected(new Set())
    loadLeads()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Leads</h1>
        <div className="flex gap-2">
          <button onClick={async () => {
            const result = await api.exportToSheets().catch(e => ({ error: e.message, success: false }));
            if (result.success) {
              toast.success(`Exported ${result.total_leads} leads to Google Sheets`);
            } else {
              toast.error('Export failed: ' + (result.error || 'Unknown error'));
            }
          }} className="px-4 py-2 border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50 transition-colors font-medium text-sm">
            📤 Export to Sheets
          </button>
          <button onClick={() => setShowForm(true)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium">
            + Add Lead
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-5">
        <input
          type="text" placeholder="Search name, business, city..."
          value={search} onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm flex-1 min-w-[200px]"
        />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
          <option value="">All Status</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="qualified">Qualified</option>
          <option value="converted">Converted</option>
          <option value="lost">Lost</option>
        </select>
        <select value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
          <option value="">All Platforms</option>
          <option value="instagram">Instagram</option>
          <option value="linkedin">LinkedIn</option>
          <option value="facebook">Facebook</option>
          <option value="website">Website</option>
          <option value="google_maps">Google Maps</option>
          <option value="yelp">Yelp</option>
          <option value="other">Other</option>
        </select>
        <select value={minScore} onChange={(e) => setMinScore(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
          <option value="">Min Lead Score</option>
          <option value="70">High (70+)</option>
          <option value="30">Medium (30+)</option>
          <option value="1">Any score</option>
        </select>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
          <option value="created_at">Newest</option>
          <option value="lead_score">Lead Score</option>
          <option value="online_presence_score">Presence Score</option>
          <option value="business_name">Name A-Z</option>
        </select>
        <button onClick={() => setSortDir(sortDir === 'desc' ? 'asc' : 'desc')}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
          {sortDir === 'desc' ? '↓ Desc' : '↑ Asc'}
        </button>
      </div>

      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
          <span className="text-sm text-blue-700 font-medium">{selected.size} selected</span>
          <button onClick={bulkDelete} className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs hover:bg-red-700">Delete All</button>
          {['contacted', 'qualified', 'converted', 'lost'].map((s) => (
            <button key={s} onClick={() => bulkStatusChange(s)}
              className="px-3 py-1.5 border border-blue-300 text-blue-700 rounded-lg text-xs hover:bg-blue-100 capitalize">
              Move to {s}
            </button>
          ))}
          <button onClick={() => setSelected(new Set())} className="text-xs text-gray-500 hover:text-gray-700">Clear</button>
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowForm(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold mb-4">Add New Lead</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <input required placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
                <input required placeholder="Business Name" value={form.business_name} onChange={(e) => setForm({ ...form, business_name: e.target.value })} className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
                  <option value="instagram">Instagram</option>
                  <option value="linkedin">LinkedIn</option>
                  <option value="facebook">Facebook</option>
                  <option value="website">Website</option>
                  <option value="google_maps">Google Maps</option>
                  <option value="yelp">Yelp</option>
                  <option value="other">Other</option>
                </select>
                <input placeholder="City" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <input placeholder="Phone" type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
                <input placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
              <input placeholder="Profile URL" value={form.profile_url} onChange={(e) => setForm({ ...form, profile_url: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <input placeholder="Website URL" value={form.website_url} onChange={(e) => setForm({ ...form, website_url: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <input placeholder="Niche (e.g. bakery, salon)" value={form.niche} onChange={(e) => setForm({ ...form, niche: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <div className="flex gap-2 pt-2">
                <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium">Create</button>
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><div className="animate-spin text-3xl">⏳</div></div>
      ) : leads.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-5xl mb-3">📭</p>
          <p className="text-lg font-medium">No leads yet</p>
          <p className="text-sm">Add a lead or use the Find Leads page to discover businesses.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-x-auto">
          <table className="w-full text-sm min-w-[900px]">
            <thead>
              <tr className="bg-gray-50 text-gray-600 text-left">
                <th className="px-2 py-3 w-8">
                  <input type="checkbox" checked={selected.size === leads.length && leads.length > 0}
                    onChange={toggleSelectAll} className="rounded" />
                </th>
                <th className="px-4 py-3 font-medium">Name / Business</th>
                <th className="px-4 py-3 font-medium">Contact</th>
                <th className="px-4 py-3 font-medium">Description</th>
                <th className="px-4 py-3 font-medium">Channel</th>
                <th className="px-4 py-3 font-medium">Platform</th>
                <th className="px-4 py-3 font-medium">City / Address</th>
                <th className="px-4 py-3 font-medium">Rating</th>
                <th className="px-4 py-3 font-medium">Score</th>
                <th className="px-4 py-3 font-medium">Lead Score</th>
                <th className="px-4 py-3 font-medium">Signals</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => {
                const ch = channelMeta[lead.channel] || channelMeta.research
                return (
                  <tr key={lead.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-2 py-3">
                      <input type="checkbox" checked={selected.has(lead.id)}
                        onChange={() => toggleSelect(lead.id)} className="rounded" />
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/leads/${lead.id}`} className="font-medium text-blue-600 hover:text-blue-800">{lead.name}</Link>
                      <p className="text-gray-500 text-xs">{lead.business_name}</p>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600">
                      {lead.phone ? (
                        <a href={`tel:${lead.phone}`} className="text-blue-600 hover:underline">{lead.phone}</a>
                      ) : lead.email ? (
                        <a href={`mailto:${lead.email}`} className="text-blue-600 hover:underline truncate block max-w-[140px]">{lead.email}</a>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 max-w-[180px]">
                      {lead.analysis_notes ? (
                        <p className="truncate" title={lead.analysis_notes}>{lead.analysis_notes}</p>
                      ) : lead.flaws ? (
                        <p className="truncate text-gray-400" title={lead.flaws}>{lead.flaws}</p>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${ch.color}`}>
                        {ch.icon} {ch.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600 capitalize">{lead.platform}</td>
                    <td className="px-4 py-3 text-gray-600 text-xs">
                      <p>{lead.city || '-'}</p>
                      {lead.address && <p className="text-gray-400 truncate max-w-[150px]">{lead.address}</p>}
                    </td>
                    <td className="px-4 py-3">
                      {lead.rating > 0 ? (
                        <span className="text-sm">⭐ {lead.rating} <span className="text-gray-400">({lead.total_ratings})</span></span>
                      ) : <span className="text-gray-300">-</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`font-medium ${lead.online_presence_score >= 70 ? 'text-green-600' : lead.online_presence_score >= 40 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {lead.online_presence_score || '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {lead.lead_score > 0 ? (
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          lead.lead_score >= 70 ? 'bg-green-100 text-green-800' :
                          lead.lead_score >= 30 ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-600'
                        }`}>
                          {lead.lead_score}
                        </span>
                      ) : <span className="text-gray-300">-</span>}
                    </td>
                    <td className="px-4 py-3">
                      {lead.intent_signals ? (
                        <div className="flex flex-wrap gap-1">
                          {lead.intent_signals.split(', ').slice(0, 3).map((s, j) => (
                            <span key={j} className={`text-xs px-1.5 py-0.5 rounded ${
                              s.includes('No website') ? 'bg-red-100 text-red-700' :
                              s.includes('No contact') ? 'bg-orange-100 text-orange-700' :
                              s.includes('Established') || s.includes('Growing') ? 'bg-green-100 text-green-700' :
                              s.includes('Highly rated') ? 'bg-yellow-100 text-yellow-700' :
                              'bg-blue-50 text-blue-600'
                            }`}>{s}</span>
                          ))}
                        </div>
                      ) : <span className="text-gray-300">-</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[lead.status] || 'bg-gray-100'}`}>{lead.status}</span>
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => handleDelete(lead.id)} className="text-red-400 hover:text-red-600 text-xs">Delete</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
