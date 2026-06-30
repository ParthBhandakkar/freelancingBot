import { useState, useEffect } from 'react'
import { api } from '../api'
import { useNavigate } from 'react-router-dom'

const tabs = [
  { id: 'finder', label: 'Business Finder', icon: '🔍' },
  { id: 'analyzer', label: 'Website Analyzer', icon: '🌐' },
  { id: 'manual', label: 'Add Manually', icon: '✏️' },
]

export default function Search() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('finder')

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Find & Add Leads</h1>

      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.id ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'finder' && <FinderTab navigate={navigate} />}
      {activeTab === 'analyzer' && <AnalyzerTab navigate={navigate} />}
      {activeTab === 'manual' && <ManualTab navigate={navigate} />}
    </div>
  )
}

function FinderTab({ navigate }) {
  const [city, setCity] = useState('')
  const [niche, setNiche] = useState('')
  const [suggestedNiches, setSuggestedNiches] = useState([])
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [importing, setImporting] = useState(null)

  useEffect(() => {
    api.getNiches().then((data) => setSuggestedNiches(data.default_niches || [])).catch(() => {})
  }, [])

  const handleSearch = async () => {
    if (!city.trim()) return
    setSearching(true)
    setError('')
    setResults(null)
    try {
      const data = await api.findBusinesses(city, niche)
      setResults(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setSearching(false)
    }
  }

  const handleImport = async (biz) => {
    setImporting(biz.name)
    try {
      const lead = await api.createLead({
        name: biz.name.split(' ')[0],
        business_name: biz.business_name || biz.name,
        platform: 'website',
        profile_url: biz.profile_url || '',
        website_url: biz.website_url || '',
        email: biz.email || '',
        phone: biz.phone || '',
        city: biz.city || city,
        niche: biz.niche || niche || 'general',
        flaws: '',
        analysis_notes: biz.address ? `Address: ${biz.address}` : '',
      })
      navigate(`/leads/${lead.id}`)
    } catch (e) {
      alert('Import failed: ' + e.message)
    } finally {
      setImporting(null)
    }
  }

  const handleImportAll = async () => {
    if (!results?.results?.length) return
    let count = 0
    for (const biz of results.results) {
      try {
        await api.createLead({
          name: biz.name.split(' ')[0],
          business_name: biz.business_name || biz.name,
          platform: 'website',
          website_url: biz.website_url || '',
          phone: biz.phone || '',
          city: biz.city || city,
          niche: biz.niche || niche || 'general',
        })
        count++
      } catch (e) {}
    }
    alert(`Imported ${count} leads!`)
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Search Local Businesses</h2>
        <p className="text-sm text-gray-500 mb-4">
          Enter a city and business type to find leads in your area.
        </p>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-gray-500 mb-1">City *</label>
            <input type="text" value={city} onChange={(e) => setCity(e.target.value)}
              placeholder="e.g. Mumbai, New York, London"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">Business Type (optional)</label>
            <input type="text" value={niche} onChange={(e) => setNiche(e.target.value)}
              placeholder="e.g. bakery, salon, gym"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {suggestedNiches.map((n) => (
                <button key={n} onClick={() => setNiche(n)}
                  className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                    niche === n ? 'bg-blue-100 border-blue-300 text-blue-700' : 'border-gray-200 text-gray-500 hover:border-blue-300'
                  }`}>
                  {n}
                </button>
              ))}
            </div>
          </div>
          <button onClick={handleSearch} disabled={searching || !city.trim()}
            className="w-full px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
            {searching ? 'Searching...' : 'Find Businesses'}
          </button>
        </div>
      </div>

      <div className="lg:col-span-2">
        {error && <div className="bg-red-50 text-red-600 p-4 rounded-xl text-sm mb-4">{error}</div>}

        {searching && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
            <p className="text-3xl mb-2">🔎</p>
            <p>Searching for businesses in {city}...</p>
          </div>
        )}

        {results && !searching && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">
                  Found <span className="font-bold text-gray-800">{results.total}</span> businesses
                  {results.niche ? ` matching "${results.niche}"` : ''} in <strong>{results.city}</strong>
                </p>
                {results.source_type === 'sample_data' && (
                  <p className="text-xs text-amber-600 mt-1">
                    Showing sample data. Set <code className="bg-amber-100 px-1 rounded">GOOGLE_API_KEY</code> in backend/.env for real businesses.
                  </p>
                )}
              </div>
              {results.total > 0 && (
                <button onClick={handleImportAll}
                  className="shrink-0 px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium">
                  Import All
                </button>
              )}
            </div>
            {results.total === 0 ? (
              <div className="p-12 text-center text-gray-400">
                <p className="text-3xl mb-2">📭</p>
                <p>No businesses found. Try a different city or niche.</p>
                <p className="text-xs mt-1">Tip: Use a larger city or broader niche term</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100 max-h-[500px] overflow-y-auto">
                {results.results.map((biz, i) => (
                  <div key={i} className="px-4 py-3 hover:bg-gray-50 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800">{biz.name}</p>
                      <div className="text-xs text-gray-500 space-y-0.5 mt-0.5">
                        {biz.niche && <span className="inline-block px-1.5 py-0.5 bg-gray-100 rounded text-xs mr-1">{biz.niche}</span>}
                        {biz.address && <p>{biz.address}</p>}
                        {biz.phone && <p>📞 {biz.phone}</p>}
                        {biz.website_url && (
                          <a href={biz.website_url} target="_blank" className="text-blue-600 hover:underline block truncate">
                            🌐 {biz.website_url}
                          </a>
                        )}
                        {biz.rating && <p>⭐ {biz.rating} ({biz.total_ratings} reviews)</p>}
                      </div>
                    </div>
                    <button onClick={() => handleImport(biz)} disabled={importing === biz.name}
                      className="shrink-0 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
                      {importing === biz.name ? '...' : 'Import'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function AnalyzerTab({ navigate }) {
  const [url, setUrl] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [analysisError, setAnalysisError] = useState('')
  const [form, setForm] = useState({ name: '', business_name: '', city: '', niche: '' })
  const [adding, setAdding] = useState(false)

  const handleAnalyze = async () => {
    if (!url.trim()) return
    setAnalyzing(true)
    setAnalysisError('')
    setAnalysis(null)
    try {
      const result = await api.analyzeWebsite(url)
      setAnalysis(result)
      setForm((prev) => ({
        ...prev,
        business_name: result.title?.replace(/\s*[-|].*$/, '').trim() || prev.business_name,
      }))
    } catch (e) {
      setAnalysisError(e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setAdding(true)
    try {
      const lead = await api.createLead({
        name: form.name || 'Unknown',
        business_name: form.business_name || url,
        platform: 'website',
        website_url: url,
        city: form.city,
        niche: form.niche,
        flaws: analysis?.issues?.join('\n') || '',
        analysis_notes: analysis?.meta_description || '',
        online_presence_score: analysis?.score || 0,
      })
      navigate(`/leads/${lead.id}`)
    } catch (e) {
      alert('Error: ' + e.message)
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Analyze a Website</h2>
        <p className="text-sm text-gray-500 mb-4">Enter a business URL to scan for issues and get a score.</p>
        <div className="flex gap-2 mb-4">
          <input type="url" value={url} onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          <button onClick={handleAnalyze} disabled={analyzing || !url.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium text-sm">
            {analyzing ? '...' : 'Analyze'}
          </button>
        </div>
        {analyzing && <div className="text-center py-8 text-gray-400">Analyzing...</div>}
        {analysisError && <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm mb-4">{analysisError}</div>}
        {analysis && (
          <div>
            <div className="flex items-center gap-3 mb-3">
              <div className="relative w-16 h-16">
                <svg className="w-16 h-16 -rotate-90" viewBox="0 0 36 36">
                  <circle cx="18" cy="18" r="15.5" fill="none" stroke="#e5e7eb" strokeWidth="3" />
                  <circle cx="18" cy="18" r="15.5" fill="none"
                    stroke={analysis.score >= 70 ? '#10b981' : analysis.score >= 40 ? '#f59e0b' : '#ef4444'}
                    strokeWidth="3" strokeDasharray={`${analysis.score}, 100`} strokeLinecap="round" />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-sm font-bold">{analysis.score}</span>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700">{analysis.title}</p>
                <p className="text-xs text-gray-400">Presence Score</p>
              </div>
            </div>
            {analysis.issues.length > 0 ? (
              <div>
                <p className="text-sm font-medium text-red-600 mb-2">Issues ({analysis.issues.length})</p>
                <ul className="space-y-1">
                  {analysis.issues.map((issue, i) => (
                    <li key={i} className="text-xs text-gray-600 flex gap-2"><span className="text-red-400 mt-0.5">•</span>{issue}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-sm text-green-600">No issues found! Great website.</p>
            )}
          </div>
        )}
      </div>
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Save as Lead</h2>
        <form onSubmit={handleSave} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input required placeholder="Contact name" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            <input required placeholder="Business name" value={form.business_name}
              onChange={(e) => setForm({ ...form, business_name: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          </div>
          <input placeholder="City" value={form.city}
            onChange={(e) => setForm({ ...form, city: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          <input placeholder="Niche (bakery, salon, etc.)" value={form.niche}
            onChange={(e) => setForm({ ...form, niche: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          <p className="text-xs text-gray-400">Score: {analysis?.score || 0} | Issues: {analysis?.issues?.length || 0}</p>
          <button type="submit" disabled={adding}
            className="w-full px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
            {adding ? 'Saving...' : 'Save as Lead'}
          </button>
        </form>
      </div>
    </div>
  )
}

function ManualTab({ navigate }) {
  const [form, setForm] = useState({
    name: '', business_name: '', platform: 'instagram',
    profile_url: '', website_url: '', city: '', niche: '',
  })
  const [adding, setAdding] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setAdding(true)
    try {
      const lead = await api.createLead(form)
      navigate(`/leads/${lead.id}`)
    } catch (e) {
      alert('Error: ' + e.message)
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="max-w-xl">
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Manually Add a Lead</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input required placeholder="Contact name" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            <input required placeholder="Business name" value={form.business_name}
              onChange={(e) => setForm({ ...form, business_name: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
              <option value="instagram">Instagram</option>
              <option value="linkedin">LinkedIn</option>
              <option value="facebook">Facebook</option>
              <option value="website">Website</option>
              <option value="other">Other</option>
            </select>
            <input placeholder="City" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          </div>
          <input placeholder="Profile / Social URL" value={form.profile_url}
            onChange={(e) => setForm({ ...form, profile_url: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          <input placeholder="Website URL" value={form.website_url}
            onChange={(e) => setForm({ ...form, website_url: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          <input placeholder="Niche (e.g. bakery, salon)" value={form.niche}
            onChange={(e) => setForm({ ...form, niche: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
          <button type="submit" disabled={adding}
            className="w-full px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
            {adding ? 'Adding...' : 'Add Lead'}
          </button>
        </form>
      </div>
    </div>
  )
}
