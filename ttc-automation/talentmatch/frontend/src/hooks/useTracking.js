/**
 * useTracking — 兼容层，底层已迁移到 @talentmatch/tracker SDK
 * 现有 import 无需修改，但建议逐步迁移到 '../tracker/useTracker'
 */
import { initTracker } from '../tracker/index';

let _tracker = null;
function _t() {
  if (!_tracker) _tracker = initTracker({ app_id: 'talentmatch', endpoint: '/api/tracking/batch' });
  return _tracker;
}

// ── 兼容旧 API ──────────────────────────────────────
export function initTracking() {
  const t = _t();
  const iv = setInterval(() => t.flush(), 5000);
  const onLeave = () => t.flush();
  window.addEventListener('beforeunload', onLeave);
  window.addEventListener('pagehide', onLeave);
  return () => {
    clearInterval(iv);
    window.removeEventListener('beforeunload', onLeave);
    window.removeEventListener('pagehide', onLeave);
    onLeave();
  };
}

export function trackEvent(ty, id, ev, dur = 0, detail = {}) {
  _t().track(ty, id, ev, dur, detail);
}

export function useDwell(ty, id) {
  const ref = { current: null, reported: false };
  const enter = () => { ref.current = Date.now(); ref.reported = false; };
  const leave = () => {
    if (!ref.current || ref.reported) return;
    const s = Math.round((Date.now() - ref.current) / 1000);
    if (s >= 1) { ref.reported = true; _t().track(ty, id, 'dwell', s); }
    ref.current = null;
  };
  return { onMouseEnter: enter, onMouseLeave: leave };
}

export function useView(ty, id, visible) {
  const ref = { current: null };
  if (visible) ref.current = Date.now();
  else if (ref.current) {
    const s = Math.round((Date.now() - ref.current) / 1000);
    if (s >= 1) _t().track(ty, id, 'view', s);
    ref.current = null;
  }
}

export function useClickCb(ty, id, ev = 'click') {
  return () => _t().track(ty, id, ev);
}

export function implicitWeight(s) {
  if (s >= 10) return { weight: '+0.4~+0.6', label: '高兴趣', color: '#52c41a', ref: 'Joachims 2005' };
  if (s >= 5) return { weight: '+0.1~+0.3', label: '中度兴趣', color: '#1677ff', ref: 'Yi et al. 2008' };
  if (s >= 2) return { weight: '0', label: '中性浏览', color: '#8c8c8c', ref: '基线' };
  return { weight: '-0.2~0', label: '跳过', color: '#ff4d4f', ref: 'Lagun 2014' };
}
