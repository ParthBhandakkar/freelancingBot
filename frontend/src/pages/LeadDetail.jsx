import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function LeadDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [lead, setLead] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({})

  useEffect(() => {
    api.getLead(id).then((data) => {
      setLead(data)
      setForm({
        status: data.status || 'new',
        response: data.response || 'pending',
        online_presence_score: data.online_presence_score || 0,
        flaws: data.flaws || '',
        analysis_notes: data.analysis_notes || '',
        asset_generated: data.asset_generated || false,
        asset_url: data.asset_url || '',
        outreach_message: data.outreach_message || '',
        email: data.email || '',
        phone: data.phone || '',
      })
    }).catch(console.error).finally(() => setLoading(false))
  }, [id])

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await api.updateLead(id, form)
      setLead(updated)
      alert('Saved!')
    } catch (e) {
      alert('Error saving: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="flex justify-center py-16"><div className="animate-spin text-3xl">⏳</div></div>
  if (!lead) return <div className="text-red-500">Lead not found</div>

  return (
    <div>
      <button onClick={() => navigate('/leads')} className="text-blue-600 hover:text-blue-800 mb-4 inline-block">&larr; Back to Leads</button>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">{lead.name}</h1>
            <p className="text-gray-500">{lead.business_name} • <span className="capitalize">{lead.platform}</span>{lead.city ? ` • ${lead.city}` : ''}</p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${lead.status === 'converted' ? 'bg-green-100 text-green-800' : lead.status === 'contacted' ? 'bg-blue-100 text-blue-800' : 'bg-yellow-100 text-yellow-800'}`}>
            {lead.status}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-4">
          {lead.profile_url && <div><span className="text-gray-500">Profile:</span> <a href={lead.profile_url} target="_blank" className="text-blue-600 hover:underline">View</a></div>}
          {lead.website_url && <div><span className="text-gray-500">Website:</span> <a href={lead.website_url} target="_blank" className="text-blue-600 hover:underline">Visit</a></div>}
          {lead.followers > 0 && <div><span className="text-gray-500">Followers:</span> {lead.followers.toLocaleString()}</div>}
          {lead.niche && <div><span className="text-gray-500">Niche:</span> {lead.niche}</div>}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="font-bold text-gray-700 mb-4">Analysis & Outreach</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-500 mb-1">Online Presence Score (0-100)</label>
              <input type="number" min="0" max="100" value={form.online_presence_score}
                onChange={(e) => setForm({ ...form, online_presence_score: +e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-1">Identified Flaws</label>
              <textarea rows="3" value={form.flaws}
                onChange={(e) => setForm({ ...form, flaws: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none" placeholder="e.g. No mobile optimization, blurry logo..."/>
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-1">Analysis Notes</label>
              <textarea rows="3" value={form.analysis_notes}
                onChange={(e) => setForm({ ...form, analysis_notes: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none" placeholder="Detailed notes about their online presence..."/>
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-1">Outreach Message</label>
              <textarea rows="4" value={form.outreach_message}
                onChange={(e) => setForm({ ...form, outreach_message: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none" placeholder="Your message to send to this lead..."/>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="font-bold text-gray-700 mb-4">Status & Assets</h2>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-gray-500 mb-1">Status</label>
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                  <option value="new">New</option>
                  <option value="contacted">Contacted</option>
                  <option value="qualified">Qualified</option>
                  <option value="converted">Converted</option>
                  <option value="lost">Lost</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-500 mb-1">Response</label>
                <select value={form.response} onChange={(e) => setForm({ ...form, response: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                  <option value="pending">Pending</option>
                  <option value="responded">Responded</option>
                  <option value="converted">Converted</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-gray-500 mb-1">Email</label>
                <input type="email" value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm text-gray-500 mb-1">Phone</label>
                <input type="text" value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.asset_generated}
                  onChange={(e) => setForm({ ...form, asset_generated: e.target.checked })} />
                Asset Generated
              </label>
            </div>
            {form.asset_generated && (
              <div>
                <label className="block text-sm text-gray-500 mb-1">Asset URL</label>
                <input type="url" value={form.asset_url}
                  onChange={(e) => setForm({ ...form, asset_url: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="Link to the asset you created..."/>
              </div>
            )}
            <button onClick={handleSave} disabled={saving}
              className="w-full px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
