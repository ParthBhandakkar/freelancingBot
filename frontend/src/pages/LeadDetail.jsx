import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'

const tabs = [
  { id: 'overview', label: 'Overview', icon: '📋' },
  { id: 'analysis', label: 'Deep Analysis', icon: '🔬' },
  { id: 'outreach', label: 'Outreach', icon: '📧' },
  { id: 'sequences', label: 'Sequences', icon: '🔄' },
]

export default function LeadDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [lead, setLead] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    api.getLead(id).then(setLead).catch(console.error).finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="flex justify-center py-16"><div className="animate-spin text-3xl">⏳</div></div>
  if (!lead) return <div className="text-red-500">Lead not found</div>

  return (
    <div>
      <button onClick={() => navigate('/leads')} className="text-blue-600 hover:text-blue-800 mb-4 inline-block">&larr; Back to Leads</button>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">{lead.name}</h1>
            <p className="text-gray-500">{lead.business_name} • <span className="capitalize">{lead.platform}</span>{lead.city ? ` • ${lead.city}` : ''}</p>
            {lead.address && <p className="text-xs text-gray-400">{lead.address}</p>}
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${lead.status === 'converted' ? 'bg-green-100 text-green-800' : lead.status === 'contacted' ? 'bg-blue-100 text-blue-800' : 'bg-yellow-100 text-yellow-800'}`}>
            {lead.status}
          </span>
        </div>
        <div className="flex items-center gap-3 mt-2">
          {lead.lead_score > 0 && (
            <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
              lead.lead_score >= 70 ? 'bg-green-100 text-green-800' :
              lead.lead_score >= 30 ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-600'
            }`}>
              Lead Score: {lead.lead_score}
            </span>
          )}
          {lead.rating > 0 && (
            <span className="text-xs text-gray-600">⭐ {lead.rating} ({lead.total_ratings} reviews)</span>
          )}
          {lead.source && (
            <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">{lead.source}</span>
          )}
        </div>
        {lead.intent_signals && (
          <p className="text-xs text-green-600 mt-2">Signals: {lead.intent_signals}</p>
        )}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mt-4">
          {lead.profile_url && <div><span className="text-gray-500">Profile:</span> <a href={lead.profile_url} target="_blank" className="text-blue-600 hover:underline">View</a></div>}
          {lead.website_url && <div><span className="text-gray-500">Website:</span> <a href={lead.website_url} target="_blank" className="text-blue-600 hover:underline">Visit</a></div>}
          {lead.followers > 0 && <div><span className="text-gray-500">Followers:</span> {lead.followers.toLocaleString()}</div>}
          {lead.niche && <div><span className="text-gray-500">Niche:</span> {lead.niche}</div>}
        </div>
      </div>

      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit flex-wrap">
        {tabs.map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.id ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}>
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && <OverviewTab lead={lead} setLead={setLead} />}
      {activeTab === 'analysis' && <AnalysisTab lead={lead} />}
      {activeTab === 'outreach' && <OutreachTab lead={lead} setLead={setLead} />}
      {activeTab === 'sequences' && <SequenceTab lead={lead} />}
    </div>
  )
}

function OverviewTab({ lead, setLead }) {
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    status: lead.status || 'new',
    response: lead.response || 'pending',
    online_presence_score: lead.online_presence_score || 0,
    flaws: lead.flaws || '',
    analysis_notes: lead.analysis_notes || '',
    asset_generated: lead.asset_generated || false,
    asset_url: lead.asset_url || '',
    outreach_message: lead.outreach_message || '',
    email: lead.email || '',
    phone: lead.phone || '',
  })

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await api.updateLead(lead.id, form)
      setLead(updated)
      alert('Saved!')
    } catch (e) {
      alert('Error saving: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h2 className="font-bold text-gray-700 mb-4">Analysis & Notes</h2>
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
  )
}

function AnalysisTab({ lead }) {
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)

  useEffect(() => {
    api.getLeadAnalysis(lead.id).then(setAnalysis).catch(() => {})
  }, [lead.id])

  const runAnalysis = async () => {
    setAnalyzing(true)
    try {
      const result = await api.analyzeLead(lead.id)
      setAnalysis(result)
    } catch (e) {
      alert('Analysis failed: ' + e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-bold text-gray-700">Deep Lead Analysis</h2>
        <button onClick={runAnalysis} disabled={analyzing}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 text-sm font-medium">
          {analyzing ? 'Analyzing...' : analysis ? 'Re-analyze' : 'Run Analysis'}
        </button>
      </div>

      {!analysis && !analyzing && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
          <p className="text-3xl mb-2">🔬</p>
          <p>Click "Run Analysis" to scan this lead's website for tech stack, social links, and more.</p>
        </div>
      )}

      {analyzing && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
          <p>Analyzing website and enriching data...</p>
        </div>
      )}

      {analysis && !analyzing && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {analysis.tech_stack && Object.keys(analysis.tech_stack).length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-700 mb-3">🛠 Tech Stack</h3>
              {analysis.tech_stack.cms?.length > 0 && (
                <div className="mb-2">
                  <p className="text-xs text-gray-500 mb-1">CMS</p>
                  <div className="flex flex-wrap gap-1">
                    {analysis.tech_stack.cms.map((t) => <span key={t} className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">{t}</span>)}
                  </div>
                </div>
              )}
              {analysis.tech_stack.frameworks?.length > 0 && (
                <div className="mb-2">
                  <p className="text-xs text-gray-500 mb-1">Frameworks</p>
                  <div className="flex flex-wrap gap-1">
                    {analysis.tech_stack.frameworks.map((t) => <span key={t} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{t}</span>)}
                  </div>
                </div>
              )}
              {analysis.tech_stack.ecommerce?.length > 0 && (
                <div className="mb-2">
                  <p className="text-xs text-gray-500 mb-1">E-commerce</p>
                  <div className="flex flex-wrap gap-1">
                    {analysis.tech_stack.ecommerce.map((t) => <span key={t} className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">{t}</span>)}
                  </div>
                </div>
              )}
              {analysis.tech_stack.analytics_tools?.length > 0 && (
                <p className="text-xs text-gray-400 mt-1">📊 {analysis.tech_stack.analytics_tools.join(', ')}</p>
              )}
              {!analysis.tech_stack.cms?.length && !analysis.tech_stack.frameworks?.length && (
                <p className="text-xs text-gray-400">No specific technologies detected</p>
              )}
            </div>
          )}

          {analysis.social_links && Object.keys(analysis.social_links).length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-700 mb-3">🌐 Social Media</h3>
              <div className="space-y-2">
                {Object.entries(analysis.social_links).map(([platform, links]) => (
                  links.length > 0 && (
                    <div key={platform}>
                      <p className="text-sm font-medium text-gray-600 capitalize">{platform}</p>
                      {links.map((link, i) => (
                        <a key={i} href={link} target="_blank" className="text-xs text-blue-600 hover:underline block truncate">{link}</a>
                      ))}
                    </div>
                  )
                ))}
              </div>
            </div>
          )}

          {analysis.social_metrics && Object.keys(analysis.social_metrics).length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-700 mb-3">📊 Social Metrics</h3>
              <div className="space-y-2">
                {analysis.social_metrics.total_platforms > 0 && (
                  <p className="text-sm">Platforms found: <strong>{analysis.social_metrics.total_platforms}</strong></p>
                )}
                {analysis.social_metrics.social_presence_score > 0 && (
                  <p className="text-sm">Social presence score: <strong>{analysis.social_metrics.social_presence_score}/100</strong></p>
                )}
                <div className="flex flex-wrap gap-1 mt-1">
                  {Object.entries(analysis.social_metrics).map(([key, val]) => (
                    val === true && (
                      <span key={key} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                        {key.replace('_presence', '').replace('_', ' ')}
                      </span>
                    )
                  ))}
                </div>
              </div>
            </div>
          )}

          {analysis.competitor_insights?.competitors?.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-700 mb-3">🏢 Competitors ({analysis.competitor_insights.total_found})</h3>
              <div className="space-y-1">
                {analysis.competitor_insights.competitors.slice(0, 5).map((comp, i) => (
                  <div key={i} className="text-xs text-gray-600 flex justify-between">
                    <span>{comp.name}</span>
                    {comp.rating && <span>⭐ {comp.rating}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {analysis.contact_email && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-700 mb-3">📧 Contact Enrichment</h3>
              <p className="text-sm">Email: <strong>{analysis.contact_email}</strong></p>
              {analysis.contact_phone && <p className="text-sm">Phone: <strong>{analysis.contact_phone}</strong></p>}
            </div>
          )}

          {analysis.keyword_signals?.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-700 mb-3">🎯 Intent Signals</h3>
              <div className="space-y-1">
                {analysis.keyword_signals.map((s, i) => (
                  <div key={i} className="text-xs text-gray-600 flex gap-2">
                    <span className={`px-1.5 py-0.5 rounded font-medium ${
                      s.level === 'high' ? 'bg-red-100 text-red-700' :
                      s.level === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'
                    }`}>{s.level}</span>
                    <span>"{s.keyword}"</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function OutreachTab({ lead, setLead }) {
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)
  const [sendResult, setSendResult] = useState(null)
  const [customVars, setCustomVars] = useState({})

  useEffect(() => {
    api.getTemplates().then(setTemplates).catch(() => {})
  }, [])

  useEffect(() => {
    if (lead.outreach_message) {
      const lines = lead.outreach_message.split('\n')
      setSubject(lines[0] || '')
      setBody(lines.slice(1).join('\n') || lines.join('\n'))
    }
  }, [lead])

  const selectTemplate = (tmpl) => {
    setSelectedTemplate(tmpl)
    const vars = {
      business_name: lead.business_name || '',
      contact_name: lead.name || '',
      city: lead.city || '',
      niche: lead.niche || '',
      flaws: lead.flaws || 'Online presence issues detected',
      score: String(lead.online_presence_score || 0),
      website: lead.website_url || '',
      phone: lead.phone || '',
      my_name: 'Your Name',
      my_company: 'Your Company',
    }
    setCustomVars(vars)

    let renderedSubject = tmpl.subject
    let renderedBody = tmpl.body
    for (const [key, val] of Object.entries(vars)) {
      renderedSubject = renderedSubject.replaceAll('{{' + key + '}}', val)
      renderedBody = renderedBody.replaceAll('{{' + key + '}}', val)
    }
    setSubject(renderedSubject)
    setBody(renderedBody)
  }

  const handleSend = async () => {
    if (!lead.email) {
      alert('This lead has no email address. Add one in the Overview tab.')
      return
    }
    setSending(true)
    setSendResult(null)
    try {
      const result = await api.sendEmail(lead.id, subject, body)
      setSendResult(result)
      if (result.success) {
        const updated = await api.getLead(lead.id)
        setLead(updated)
      }
    } catch (e) {
      setSendResult({ success: false, error: e.message })
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1 bg-white rounded-xl shadow-sm border border-gray-100 p-5">
        <h3 className="font-semibold text-gray-700 mb-3">📝 Outreach Templates</h3>
        <div className="space-y-2 mb-4">
          {templates.length === 0 && <p className="text-xs text-gray-400">No templates yet. Go to Outreach page to create some.</p>}
          {templates.map((tmpl) => (
            <button key={tmpl.id} onClick={() => selectTemplate(tmpl)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm border transition-colors ${
                selectedTemplate?.id === tmpl.id
                  ? 'border-blue-300 bg-blue-50 text-blue-700'
                  : 'border-gray-200 hover:border-blue-200 text-gray-600'
              }`}>
              <p className="font-medium">{tmpl.name}</p>
              <p className="text-xs text-gray-400">{tmpl.channel} • {tmpl.description?.slice(0, 60)}</p>
            </button>
          ))}
        </div>

        <h4 className="text-sm font-medium text-gray-600 mb-2">Variable Help</h4>
        <p className="text-xs text-gray-400 mb-1">Use {'{{variable_name}}'} in templates</p>
        <div className="text-xs text-gray-500 space-y-0.5">
          <p>business_name, contact_name, city, niche</p>
          <p>flaws, score, website, phone</p>
          <p>my_name, my_company</p>
        </div>

        {selectedTemplate && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <h4 className="text-sm font-medium text-gray-600 mb-2">Quick Customize</h4>
            {Object.entries(customVars).slice(0, 5).map(([key, val]) => (
              <div key={key} className="mb-2">
                <label className="text-xs text-gray-400">{key}</label>
                <input type="text" value={val} onChange={(e) => {
                  const newVars = { ...customVars, [key]: e.target.value }
                  setCustomVars(newVars)
                  if (selectedTemplate) {
                    let s = selectedTemplate.subject
                    let b = selectedTemplate.body
                    for (const [k, v] of Object.entries(newVars)) {
                      s = s.replaceAll('{{' + k + '}}', v)
                      b = b.replaceAll('{{' + k + '}}', v)
                    }
                    setSubject(s)
                    setBody(b)
                  }
                }}
                  className="w-full px-2 py-1 border border-gray-200 rounded text-xs" />
              </div>
            ))}
          </div>
        )}

        {lead.email && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-500">Sending to: <strong>{lead.email}</strong></p>
          </div>
        )}
      </div>

      <div className="lg:col-span-2 space-y-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-700 mb-3">Email Preview</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-500 mb-1">Subject</label>
              <input type="text" value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-1">Body</label>
              <textarea rows="10" value={body}
                onChange={(e) => setBody(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none font-mono" />
            </div>
            <div className="flex gap-3">
              <button onClick={handleSend} disabled={sending || !subject || !body}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium">
                {sending ? 'Sending...' : '📧 Send Email'}
              </button>
              {lead.website_url && (
                <a href={lead.website_url} target="_blank"
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
                  🌐 Visit Website
                </a>
              )}
              {lead.profile_url && (
                <a href={lead.profile_url} target="_blank"
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
                  👤 View Profile
                </a>
              )}
            </div>
          </div>
        </div>

        {sendResult && (
          <div className={`p-4 rounded-xl text-sm ${sendResult.success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
            {sendResult.success ? '✅ Email sent successfully!' : `❌ Failed: ${sendResult.error}`}
          </div>
        )}

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-700 mb-3">📞 Call Script</h3>
          {lead.flaws ? (
            <div className="text-sm text-gray-600 bg-gray-50 p-4 rounded-lg font-mono whitespace-pre-wrap">
Hi {lead.name}, this is [Your Name]. I was looking at {lead.business_name}'s online presence and found a few things that might be costing you customers.

Specifically:
{lead.flaws.split('\n').map(f => `- ${f}`).join('\n')}

I help {lead.niche || 'local'} businesses fix these issues. I'm calling to see if you'd be open to a quick chat?

If now's not a good time, when would work better?
            </div>
          ) : (
            <p className="text-sm text-gray-400">Add flaws/notes in the Overview tab to generate a call script.</p>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-700 mb-3">📅 Calendly Booking</h3>
          <p className="text-sm text-gray-500 mb-3">Send a Calendly link to let this lead book a meeting with you.</p>
          <div className="flex gap-2">
            <input type="text" placeholder="https://calendly.com/your-link" id="calendlyInput"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            <button onClick={() => {
              const link = document.getElementById('calendlyInput').value
              if (link) {
                const fullUrl = link + (link.includes('?') ? '&' : '?') + 'name=' + encodeURIComponent(lead.name || '') + '&email=' + encodeURIComponent(lead.email || '')
                window.open(fullUrl, '_blank')
              }
            }}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium">
              Open Booking
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function SequenceTab({ lead }) {
  const [sequences, setSequences] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newSeq, setNewSeq] = useState({
    name: `Outreach for ${lead.business_name}`,
    steps: [
      { step_order: 0, action_type: 'email', subject: 'Quick question about {{business_name}}', body: 'Hi {{contact_name}},\n\nI noticed {{business_name}} could use some help with online presence. Would you be open to a quick chat?\n\nBest,\n{{my_name}}', delay_days: 0 },
      { step_order: 1, action_type: 'email', subject: 'Following up - {{business_name}}', body: 'Hi {{contact_name}},\n\nJust following up on my previous message. I\'d love to help {{business_name}} improve its online presence.\n\nBest,\n{{my_name}}', delay_days: 3 },
      { step_order: 2, action_type: 'call', subject: 'Call Script', body: 'Hi {{contact_name}}, this is [Your Name]. I reached out earlier about helping {{business_name}} with your online presence. Have you had a chance to think about it?', delay_days: 7 },
    ],
  })

  const loadSequences = () => {
    setLoading(true)
    api.getSequences({ lead_id: lead.id }).then(setSequences).catch(console.error).finally(() => setLoading(false))
  }

  useEffect(() => { loadSequences() }, [lead.id])

  const handleCreate = async () => {
    try {
      await api.createSequence({ lead_id: lead.id, name: newSeq.name, steps: newSeq.steps })
      setShowCreate(false)
      loadSequences()
    } catch (e) {
      alert('Failed to create sequence: ' + e.message)
    }
  }

  const handleAdvance = async (seqId) => {
    try {
      await api.advanceSequence(seqId)
      loadSequences()
    } catch (e) {
      alert('Failed to advance: ' + e.message)
    }
  }

  const handlePauseResume = async (seq) => {
    try {
      if (seq.active) {
        await api.pauseSequence(seq.id)
      } else {
        await api.resumeSequence(seq.id)
      }
      loadSequences()
    } catch (e) {
      alert('Failed: ' + e.message)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-bold text-gray-700">Outreach Sequences</h2>
        <button onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
          + Create Sequence
        </button>
      </div>

      {loading && <div className="text-center py-8 text-gray-400">Loading...</div>}

      {!loading && sequences.length === 0 && !showCreate && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
          <p className="text-3xl mb-2">🔄</p>
          <p>No outreach sequences yet. Create one to automate follow-ups!</p>
        </div>
      )}

      {showCreate && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
          <h3 className="font-semibold text-gray-700 mb-4">New Sequence</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-500 mb-1">Sequence Name</label>
              <input type="text" value={newSeq.name}
                onChange={(e) => setNewSeq({ ...newSeq, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            {newSeq.steps.map((step, i) => (
              <div key={i} className="bg-gray-50 p-3 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-600">Step {i + 1}</span>
                  <button onClick={() => setNewSeq({ ...newSeq, steps: newSeq.steps.filter((_, j) => j !== i) })}
                    className="text-red-400 hover:text-red-600 text-xs">Remove</button>
                </div>
                <div className="grid grid-cols-3 gap-2 mb-2">
                  <select value={step.action_type}
                    onChange={(e) => {
                      const steps = [...newSeq.steps]
                      steps[i] = { ...steps[i], action_type: e.target.value }
                      setNewSeq({ ...newSeq, steps })
                    }}
                    className="px-2 py-1 border border-gray-300 rounded text-xs">
                    <option value="email">Email</option>
                    <option value="call">Call</option>
                    <option value="linkedin">LinkedIn</option>
                  </select>
                  <input type="number" value={step.delay_days} placeholder="Delay days"
                    onChange={(e) => {
                      const steps = [...newSeq.steps]
                      steps[i] = { ...steps[i], delay_days: +e.target.value }
                      setNewSeq({ ...newSeq, steps })
                    }}
                    className="px-2 py-1 border border-gray-300 rounded text-xs" />
                </div>
                <input type="text" value={step.subject} placeholder="Subject"
                  onChange={(e) => {
                    const steps = [...newSeq.steps]
                    steps[i] = { ...steps[i], subject: e.target.value }
                    setNewSeq({ ...newSeq, steps })
                  }}
                  className="w-full px-2 py-1 border border-gray-300 rounded text-xs mb-1" />
                <textarea rows="2" value={step.body} placeholder="Message body"
                  onChange={(e) => {
                    const steps = [...newSeq.steps]
                    steps[i] = { ...steps[i], body: e.target.value }
                    setNewSeq({ ...newSeq, steps })
                  }}
                  className="w-full px-2 py-1 border border-gray-300 rounded text-xs resize-none" />
              </div>
            ))}
            <button onClick={() => setNewSeq({
              ...newSeq,
              steps: [...newSeq.steps, { step_order: newSeq.steps.length, action_type: 'email', subject: '', body: '', delay_days: 1 }]
            })}
              className="text-sm text-blue-600 hover:text-blue-800">
              + Add Step
            </button>
            <div className="flex gap-2 pt-2">
              <button onClick={handleCreate}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
                Create Sequence
              </button>
              <button onClick={() => setShowCreate(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {sequences.map((seq) => (
        <div key={seq.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mb-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="font-semibold text-gray-700">{seq.name}</h3>
              <p className="text-xs text-gray-400">
                {seq.active ? 'Active' : 'Paused'} • Step {seq.current_step + 1}/{seq.steps.length} • Started {new Date(seq.started_at).toLocaleDateString()}
                {seq.completed_at && ` • Completed ${new Date(seq.completed_at).toLocaleDateString()}`}
              </p>
            </div>
            <div className="flex gap-2">
              {seq.active && seq.current_step < seq.steps.length && (
                <button onClick={() => handleAdvance(seq.id)}
                  className="px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 text-xs font-medium">
                  Advance Step
                </button>
              )}
              <button onClick={() => handlePauseResume(seq)}
                className="px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 text-xs">
                {seq.active ? 'Pause' : 'Resume'}
              </button>
            </div>
          </div>
          <div className="space-y-2">
            {seq.steps.map((step) => (
              <div key={step.id} className={`flex items-center gap-3 p-2 rounded-lg text-sm ${
                step.status === 'sent' ? 'bg-green-50' : 'bg-gray-50'
              }`}>
                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                  step.status === 'sent' ? 'bg-green-500 text-white' : 'bg-gray-300 text-white'
                }`}>{step.step_order + 1}</span>
                <div className="flex-1">
                  <p className="text-xs font-medium text-gray-700 capitalize">{step.action_type} • {step.delay_days}d delay</p>
                  <p className="text-xs text-gray-500 truncate">{step.subject || step.body?.slice(0, 60)}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  step.status === 'sent' ? 'bg-green-100 text-green-700' :
                  step.status === 'pending' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'
                }`}>{step.status}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
