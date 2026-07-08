/**
 * @talentmatch/tracker — 多站点隐式行为采集 SDK v1.0
 * 
 * 设计目标：
 *   1. 零依赖 — 纯 JS，不依赖 React/Vue/任何框架
 *   2. 多站点 — 通过 app_id 区分不同产品/站点
 *   3. 离线安全 — sendBeacon + sessionStorage 队列，页面关闭也不丢数据
 *   4. 隐私优先 — 不采集 IP/UA，只记录行为信号
 * 
 * 学术权重依据（内嵌到后端聚合）：
 *   0-1s  快速跳过 → -0.15      Lagun et al. 2014 (WSDM)
 *   1-3s  中性浏览 → 0          基线
 *   3-10s 中度兴趣 → +0.2       Yi et al. 2008
 *   10s+  高兴趣   → +0.5       Joachims et al. 2005 (SIGIR)
 *   查看原文      → +0.6        Buscher et al. 2009 (CIKM)
 *   匹配/联系     → +0.7~+1.0   行为信号
 * 
 * 使用方式：
 *   import { initTracker } from './tracker';
 *   const t = initTracker({ app_id: 'talentmatch', endpoint: '/api/tracking/batch' });
 *   t.track('candidate', 'C001', 'view', 5);
 *   
 *   多站点：
 *   const t1 = initTracker({ app_id: 'product_a', endpoint: 'https://a.com/api/t' });
 *   const t2 = initTracker({ app_id: 'product_b', endpoint: 'https://b.com/api/t' });
 */

const Q_PREFIX = '__tm_tq_';
const FLUSH_MS = 5000;
const MAX_Q = 100;

let _instances = {};

function _skey(appId) { return Q_PREFIX + appId; }

function _uid() {
  try {
    const k = 'talentmatch_auth_user';
    const raw = localStorage.getItem(k) || sessionStorage.getItem(k);
    if (!raw) return '';
    const u = JSON.parse(raw);
    return u?.username || u?.open_id || u?.feishu_user_id || '';
  } catch { return ''; }
}

function _enq(appId, event) {
  try {
    const key = _skey(appId);
    const q = JSON.parse(sessionStorage.getItem(key) || '[]');
    q.push({ ...event, ts: Date.now() });
    while (q.length > MAX_Q) q.shift();
    sessionStorage.setItem(key, JSON.stringify(q));
  } catch {}
}

function _flushOne(appId, endpoint) {
  try {
    const key = _skey(appId);
    const q = JSON.parse(sessionStorage.getItem(key) || '[]');
    if (!q.length) return;
    sessionStorage.removeItem(key);
    const body = JSON.stringify(q.map(e => ({ ...e, user_id: e.user_id || _uid() })));
    if (navigator.sendBeacon) {
      navigator.sendBeacon(endpoint, new Blob([body], { type: 'application/json' }));
    } else {
      fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true }).catch(() => {});
    }
  } catch {}
}

export function initTracker(opts = {}) {
  const appId = opts.app_id || 'default';
  const endpoint = opts.endpoint || '/api/tracking/batch';
  const flushMs = opts.flushMs || FLUSH_MS;

  if (_instances[appId]) return _instances[appId];

  const interval = setInterval(() => _flushOne(appId, endpoint), flushMs);
  if (Object.keys(_instances).length === 0) {
    window.addEventListener('beforeunload', () => Object.values(_instances).forEach(i => _flushOne(i.app_id, i.endpoint)));
  }

  const inst = {
    app_id: appId,
    endpoint,

    track(entityType, entityId, eventType, duration = 0, detail = {}) {
      _enq(appId, { entity_type: entityType, entity_id: String(entityId || ''), event_type: eventType, duration, detail });
    },

    trackDwell(entityType, entityId) {
      let start = null, reported = false;
      return {
        onMouseEnter: () => { start = Date.now(); reported = false; },
        onMouseLeave: () => {
          if (!start || reported) return;
          const dur = Math.round((Date.now() - start) / 1000);
          if (dur >= 1) { _enq(appId, { entity_type: entityType, entity_id: String(entityId), event_type: 'dwell', duration: dur }); reported = true; }
          start = null;
        }
      };
    },

    trackView(entityType, entityId) {
      return {
        start: () => { this._vs = Date.now(); },
        end: () => {
          if (!this._vs) return;
          const dur = Math.round((Date.now() - this._vs) / 1000);
          if (dur >= 1) _enq(appId, { entity_type: entityType, entity_id: String(entityId), event_type: 'view', duration: dur });
          this._vs = null;
        }
      };
    },

    trackClick(entityType, entityId, eventType = 'click') {
      _enq(appId, { entity_type: entityType, entity_id: String(entityId), event_type: eventType });
    },

    flush() { _flushOne(appId, endpoint); },
    destroy() { clearInterval(interval); this.flush(); delete _instances[appId]; }
  };

  _instances[appId] = inst;
  return inst;
}

export default initTracker;
