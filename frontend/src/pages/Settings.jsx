import { useState, useEffect } from 'react'
import { api } from '../api'
import { useToast } from '../components/Toast'

export default function Settings() {
  const [settings, setSettings] = useState({})
  const [integrationStatus, setIntegrationStatus] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const toast = useToast()

  useEffect(() => {
    Promise.all([
      api.getSettings().catch(() => ({})),
      api.getIntegrationStatus().catch(() => ({})),
    ]).then(([s, status]) => {
      setSettings(s)
      setIntegrationStatus(status)
    }).catch(console.error).finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      const result = await api.updateSettings(settings)
      setSettings(result.settings)
      toast.success('Settings saved')
    } catch (e) {
      toast.error('Error saving: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  const updateField = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
  }

  if (loading) return <div className="flex justify-center py-16"><div className="animate-spin text-3xl">⏳</div></div>

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Settings</h1>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <h2 className="font-semibold text-gray-700 mb-4">Your Identity</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-500 mb-1">Your Name</label>
            <input type="text" value={settings.my_name || ''}
              onChange={(e) => updateField('my_name', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="John Doe" />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">Company Name</label>
            <input type="text" value={settings.my_company || ''}
              onChange={(e) => updateField('my_company', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="My Web Studio" />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">Your Website / Portfolio</label>
            <input type="url" value={settings.my_website || ''}
              onChange={(e) => updateField('my_website', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="https://yoursite.com" />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">Calendly Booking Link</label>
            <input type="url" value={settings.calendly_link || ''}
              onChange={(e) => updateField('calendly_link', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="https://calendly.com/your-link" />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">Email Signature</label>
            <textarea rows="2" value={settings.email_signature || ''}
              onChange={(e) => updateField('email_signature', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none" placeholder="Best,&#10;John Doe" />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">Services Offered</label>
            <input type="text" value={settings.services_offered || ''}
              onChange={(e) => updateField('services_offered', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="website design, redesign, SEO..." />
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <h2 className="font-semibold text-gray-700 mb-4">Sending Behavior</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-500 mb-1">Daily Send Limit</label>
            <input type="number" value={settings.daily_send_limit || '25'}
              onChange={(e) => updateField('daily_send_limit', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" min="1" max="100" />
            <p className="text-xs text-gray-400 mt-1">Max emails sent per day across auto and manual sends.</p>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={settings.auto_send_followups === 'true'}
                onChange={(e) => updateField('auto_send_followups', e.target.checked ? 'true' : 'false')} />
              Auto-send follow-up emails
            </label>
            <span className="text-xs text-gray-400">(Call/DM steps always stay in your Today queue)</span>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <h2 className="font-semibold text-gray-700 mb-4">Integration Status</h2>
        <div className="space-y-2 text-sm">
          {Object.entries(integrationStatus).length === 0 ? (
            <p className="text-gray-400">Could not load status.</p>
          ) : (
            Object.entries(integrationStatus).map(([key, configured]) => (
              <div key={key} className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${configured ? 'bg-green-500' : 'bg-red-400'}`}></span>
                <span className="capitalize text-gray-600">{key.replace(/_/g, ' ')}</span>
                <span className={`text-xs ${configured ? 'text-green-600' : 'text-red-400'}`}>
                  {configured ? 'Configured' : 'Not configured'}
                </span>
              </div>
            ))
          )}
        </div>
        <p className="text-xs text-gray-400 mt-3">API keys are read from backend/.env. Restart the backend after changing them.</p>
      </div>

      <button onClick={handleSave} disabled={saving}
        className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
        {saving ? 'Saving...' : 'Save Settings'}
      </button>
    </div>
  )
}
