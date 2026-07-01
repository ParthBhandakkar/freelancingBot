import { useState, useEffect } from 'react'
import { api } from '../api'
import { Link } from 'react-router-dom'

export default function Outreach() {
  const [activeTab, setActiveTab] = useState('templates')
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Outreach Management</h1>
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit">
        <button onClick={() => setActiveTab('templates')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'templates' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
          📝 Templates
        </button>
        <button onClick={() => setActiveTab('sequences')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'sequences' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
          🔄 All Sequences
        </button>
      </div>
      {activeTab === 'templates' && <TemplateManager />}
      {activeTab === 'sequences' && <SequenceManager />}
    </div>
  )
}

function TemplateManager() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ name: '', description: '', subject: '', body: '', channel: 'email', variables: [] })

  const load = () => {
    setLoading(true)
    api.getTemplates().then(setTemplates).catch(console.error).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const seedDefaults = async () => {
    await api.seedDefaultTemplates()
    load()
  }

  const handleSave = async (e) => {
    e.preventDefault()
    try {
      if (editing) {
        await api.updateTemplate(editing.id, form)
      } else {
        await api.createTemplate(form)
      }
      setShowForm(false)
      setEditing(null)
      setForm({ name: '', description: '', subject: '', body: '', channel: 'email', variables: [] })
      load()
    } catch (e) {
      alert('Error: ' + e.message)
    }
  }

  const handleEdit = (tmpl) => {
    setEditing(tmpl)
    setForm({
      name: tmpl.name,
      description: tmpl.description || '',
      subject: tmpl.subject,
      body: tmpl.body,
      channel: tmpl.channel,
      variables: tmpl.variables || [],
    })
    setShowForm(true)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this template?')) return
    await api.deleteTemplate(id)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">{templates.length} templates</p>
        <div className="flex gap-2">
          <button onClick={seedDefaults} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
            Seed Defaults
          </button>
          <button onClick={() => { setEditing(null); setForm({ name: '', description: '', subject: '', body: '', channel: 'email', variables: [] }); setShowForm(true) }}
            className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            + New Template
          </button>
        </div>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => { setShowForm(false); setEditing(null) }}>
          <div className="bg-white rounded-xl p-6 w-full max-w-2xl mx-4 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold mb-4">{editing ? 'Edit Template' : 'New Template'}</h2>
            <form onSubmit={handleSave} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <input required placeholder="Template name" value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
                <select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
                  <option value="email">Email</option>
                  <option value="linkedin">LinkedIn</option>
                  <option value="call">Call</option>
                </select>
              </div>
              <input placeholder="Description" value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <input required placeholder="Subject line (use {{variable}})" value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
              <textarea required rows="8" placeholder="Template body (use {{variable}})..."
                value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none font-mono" />
              <p className="text-xs text-gray-400">Available variables: {'{{business_name}}, {{contact_name}}, {{city}}, {{niche}}, {{flaws}}, {{score}}, {{website}}, {{phone}}, {{my_name}}, {{my_company}}'}</p>
              <div className="flex gap-2 pt-2">
                <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium">
                  {editing ? 'Update' : 'Create'}
                </button>
                <button type="button" onClick={() => { setShowForm(false); setEditing(null) }}
                  className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-8 text-gray-400">Loading...</div>
      ) : templates.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
          <p className="text-3xl mb-2">📝</p>
          <p>No templates yet. Click "Seed Defaults" to get started or create your own.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {templates.map((tmpl) => (
            <div key={tmpl.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="font-semibold text-gray-700 text-sm">{tmpl.name}</h3>
                  <span className="text-xs text-gray-400 capitalize">{tmpl.channel}</span>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleEdit(tmpl)} className="text-blue-500 hover:text-blue-700 text-xs">Edit</button>
                  <button onClick={() => handleDelete(tmpl.id)} className="text-red-400 hover:text-red-600 text-xs">Delete</button>
                </div>
              </div>
              {tmpl.description && <p className="text-xs text-gray-500 mb-2">{tmpl.description}</p>}
              <p className="text-xs text-gray-400 bg-gray-50 p-2 rounded truncate">{tmpl.subject}</p>
              <p className="text-xs text-gray-400 mt-1 line-clamp-2">{tmpl.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SequenceManager() {
  const [sequences, setSequences] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getSequences().then(setSequences).catch(console.error).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-8 text-gray-400">Loading...</div>

  if (sequences.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
        <p className="text-3xl mb-2">🔄</p>
        <p>No sequences yet. Go to a lead's detail page to create one.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {sequences.map((seq) => (
        <div key={seq.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
          <div className="flex items-center justify-between mb-2">
            <div>
              <Link to={`/leads/${seq.lead_id}`} className="font-semibold text-blue-600 hover:text-blue-800 text-sm">{seq.name}</Link>
              <p className="text-xs text-gray-400">
                {seq.active ? '🟢 Active' : '⏸ Paused'} • Step {seq.current_step}/{seq.steps.length} • Lead #{seq.lead_id}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {seq.steps.map((step, i) => (
              <div key={step.id} className={`flex-1 p-2 rounded text-xs text-center ${
                i < seq.current_step ? 'bg-green-100 text-green-700' :
                i === seq.current_step ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-400'
              }`}>
                <p className="font-medium capitalize">{step.action_type}</p>
                <p className="text-[10px]">{step.delay_days}d</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
