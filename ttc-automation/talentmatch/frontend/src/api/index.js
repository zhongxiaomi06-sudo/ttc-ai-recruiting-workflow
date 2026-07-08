// TalentMatch API · 统一请求封装
const API_BASE = '/api';

function parseError(res, errBody) {
  let msg = `请求失败 (${res.status})`;
  try {
    const j = JSON.parse(errBody);
    if (j.detail) {
      msg = Array.isArray(j.detail) 
        ? j.detail.map(d => typeof d === 'string' ? d : (d.msg || '')).join('; ')
        : j.detail;
    }
  } catch {}
  return { status: res.status, message: msg };
}

async function request(path, options = {}) {
  const url = API_BASE + path;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };
  try {
    const res = await fetch(url, config);
    if (!res.ok) {
      const errBody = await res.text().catch(() => '');
      const err = parseError(res, errBody);
      throw err;
    }
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    if (!e.status) {
      throw { status: 0, message: '网络连接失败，请检查服务是否运行' };
    }
    throw e;
  }
}

async function ttcRequest(path, options = {}) {
  const token = localStorage.getItem('ttc_workflow_token') || '';
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers['X-TTC-Token'] = token;
  const res = await fetch('/api/ttc' + path, { ...options, headers });
  if (!res.ok) {
    const errBody = await res.text().catch(() => '');
    throw parseError(res, errBody);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

async function getHealth() {
  const res = await fetch('/health');
  if (!res.ok) throw { status: res.status, message: '系统服务连接失败' };
  return res.json();
}

let _authToken = localStorage.getItem('talentmatch_auth_token') || '';

function setAuthToken(token) {
  _authToken = token;
  localStorage.setItem('talentmatch_auth_token', token);
}

function getAuthToken() {
  return _authToken || localStorage.getItem('talentmatch_auth_token') || '';
}

export const api = {
  getHealth,
  setAuthToken,
  getAuthToken: () => getAuthToken(),

  // 通用请求（给需要自定义路径的页面使用）
  request: (path, options) => request(path, options),

  // ── 认证 ──
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  register: (username, password, display_name = '', role = '猎头顾问') =>
    request('/auth/register', { method: 'POST', body: JSON.stringify({ username, password, display_name, role }) }),
  getProfile: () => request('/auth/me'),

  // ── 候选人 ──
  getCandidates: (query) =>
    request(query ? `/candidates/search/${encodeURIComponent(query)}` : '/candidates'),
  getCandidate: (id) => request(`/candidates/${id}`),
  deleteCandidate: (id) => request(`/candidates/${id}`, { method: 'DELETE' }),
  updateCandidate: (id, data) => request(`/candidates/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  getCandidateStats: () => request('/candidates/stats'),

  // ── 职位 ──
  getJobs: (status) => request(`/jobs?status=${status || 'active'}`),
  createJob: (data) => request('/jobs', { method: 'POST', body: JSON.stringify(data) }),
  getJob: (id) => request(`/jobs/${id}`),
  getJobMatches: (id) => request(`/jobs/${id}/matches`),
  getJobStats: () => request('/jobs/stats'),

  // ── 匹配 ──
  fastMatch: (jdText, limit = 20) =>
    request('/fast-match', { method: 'POST', body: JSON.stringify({ jd_text: jdText, limit }) }),
  compareCandidates: (candidateIds, jdText) =>
    request('/compare', { method: 'POST', body: JSON.stringify({ candidate_ids: candidateIds, jd_text: jdText }) }),
  explainMatch: (candidateId, jdText) =>
    request(`/explain/${candidateId}?jd_text=${encodeURIComponent(jdText)}`),
  getMatchHistory: (limit = 20) => request(`/history?limit=${limit}`),
  getMatchRules: () => request('/match-rules'),

  // ── 统计 ──
  getStats: () => request('/stats'),
  getTrackingStats: () => request('/tracking/stats'),

  // ── TTC AI 工作流子系统 ──
  ttcHealth: () => ttcRequest('/health'),
  ttcMissions: (limit = 50) => ttcRequest(`/api/missions?limit=${limit}`),
  ttcHumanTasks: (status = '', limit = 100) =>
    ttcRequest(`/human/tasks?limit=${limit}${status ? `&status=${encodeURIComponent(status)}` : ''}`),
  ttcCallList: (status = '', limit = 100) =>
    ttcRequest(`/api/call-list?limit=${limit}${status ? `&status=${encodeURIComponent(status)}` : ''}`),
  ttcIngestJD: (payload) =>
    ttcRequest('/ingest/feishu', { method: 'POST', body: JSON.stringify(payload) }),
  ttcReadLink: (url) =>
    ttcRequest(`/ingest/read-link?url=${encodeURIComponent(url)}`),
  ttcCompleteTask: (taskId, result) =>
    ttcRequest(`/api/human/task/${taskId}/complete`, { method: 'POST', body: JSON.stringify(result) }),

  // ── 批量上传 ──
  uploadFile: async (file) => {
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await fetch(API_BASE + '/parse', { method: 'POST', body: fd });
      if (!res.ok) {
        const errBody = await res.text().catch(() => '');
        const err = parseError(res, errBody);
        throw err;
      }
      return res.json();
    } catch (e) {
      if (e.name === 'AbortError') throw e;
      if (!e.status) throw { status: 0, message: '上传请求异常，请检查网络' };
      throw e;
    }
  },
};
