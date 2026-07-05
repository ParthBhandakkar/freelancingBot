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
  getLeadScoreSummary: () => request('/analytics/lead-score-summary'),

  analyzeWebsite: (url, deep) => {
    let q = 'url=' + encodeURIComponent(url);
    if (deep) q += '&deep=true';
    return request('/search/analyze-website?' + q);
  },
  findBusinesses: (city, niche, limit, source) => {
    let q = 'city=' + encodeURIComponent(city);
    if (niche) q += '&niche=' + encodeURIComponent(niche);
    if (limit) q += '&limit=' + limit;
    if (source) q += '&source=' + source;
    return request('/search/find?' + q);
  },
  getNiches: () => request('/search/niches'),
  findCompetitors: (niche, city, exclude, limit) => {
    let q = 'niche=' + encodeURIComponent(niche) + '&city=' + encodeURIComponent(city);
    if (exclude) q += '&exclude=' + encodeURIComponent(exclude);
    if (limit) q += '&limit=' + limit;
    return request('/search/find-competitors?' + q);
  },

  analyzeLead: (id) => request('/analysis/analyze-lead/' + id, { method: 'POST' }),
  getLeadAnalysis: (id) => request('/analysis/lead/' + id),
  deleteLeadAnalysis: (id) => request('/analysis/lead/' + id, { method: 'DELETE' }),

  getTemplates: (params) => {
    const q = params ? new URLSearchParams(params).toString() : '';
    return request('/outreach/templates' + (q ? '?' + q : ''));
  },
  getTemplate: (id) => request('/outreach/templates/' + id),
  createTemplate: (data) => request('/outreach/templates', { method: 'POST', body: JSON.stringify(data) }),
  updateTemplate: (id, data) => request('/outreach/templates/' + id, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTemplate: (id) => request('/outreach/templates/' + id, { method: 'DELETE' }),
  seedDefaultTemplates: () => request('/outreach/templates/defaults'),
  getTemplateVariables: () => request('/outreach/variables'),

  getSequences: (params) => {
    const q = params ? new URLSearchParams(params).toString() : '';
    return request('/outreach/sequences' + (q ? '?' + q : ''));
  },
  getSequence: (id) => request('/outreach/sequences/' + id),
  createSequence: (data) => request('/outreach/sequences', { method: 'POST', body: JSON.stringify(data) }),
  advanceSequence: (id) => request('/outreach/sequences/' + id + '/advance', { method: 'POST' }),
  pauseSequence: (id) => request('/outreach/sequences/' + id + '/pause', { method: 'POST' }),
  resumeSequence: (id) => request('/outreach/sequences/' + id + '/resume', { method: 'POST' }),

  sendEmail: (leadId, subject, body) => {
    let q = 'subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
    return request('/outreach/send-email/' + leadId + '?' + q, { method: 'POST' });
  },

  exportToSheets: () => request('/leads/export/sheets', { method: 'POST' }),
};
