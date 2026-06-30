const BASE = '/api';

async function request(url, options) {
  const opts = { headers: { 'Content-Type': 'application/json' }, ...options };
  const res = await fetch(BASE + url, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  getLeads: (params) => {
    const q = params ? new URLSearchParams(params).toString() : '';
    return request('/leads' + (q ? '?' + q : ''));
  },
  getLead: (id) => request('/leads/' + id),
  createLead: (data) => request('/leads', { method: 'POST', body: JSON.stringify(data) }),
  updateLead: (id, data) => request('/leads/' + id, { method: 'PUT', body: JSON.stringify(data) }),
  deleteLead: (id) => request('/leads/' + id, { method: 'DELETE' }),
  getDashboardStats: () => request('/analytics/dashboard'),
  analyzeWebsite: (url) => request('/search/analyze-website?url=' + encodeURIComponent(url)),
  findBusinesses: (city, niche, limit) => {
    let q = 'city=' + encodeURIComponent(city);
    if (niche) q += '&niche=' + encodeURIComponent(niche);
    if (limit) q += '&limit=' + limit;
    return request('/search/find?' + q);
  },
  getNiches: () => request('/search/niches'),
};
