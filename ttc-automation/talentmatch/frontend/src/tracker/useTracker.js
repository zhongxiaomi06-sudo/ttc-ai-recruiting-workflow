/**
 * React Hook 封装 — 基于 @talentmatch/tracker SDK
 *
 * 使用:
 *   import { useDwell, useView, useClickCb } from '../tracker/useTracker';
 *   
 *   function CandidateRow({ candidate }) {
 *     const dwell = useDwell('candidate', candidate.id);
 *     const clickMatch = useClickCb('candidate', candidate.id, 'match_click');
 *     return <tr {...dwell}><td>{candidate.name}<Button onClick={clickMatch}>匹配</Button></td></tr>;
 *   }
 */
import { useCallback, useRef, useEffect } from 'react';
import { initTracker } from './index';

// 全局单例
let _tracker = null;
function getTracker() {
  if (!_tracker) {
    _tracker = initTracker({ app_id: 'talentmatch', endpoint: '/api/tracking/batch' });
  }
  return _tracker;
}

/** 行级悬停追踪: 返回 {onMouseEnter,onMouseLeave} 加到行元素上 */
export function useDwell(entityType, entityId) {
  const tRef = useRef(null);
  const rRef = useRef(false);
  const enter = useCallback(() => { tRef.current = Date.now(); rRef.current = false; }, [entityType, entityId]);
  const leave = useCallback(() => {
    if (!tRef.current || rRef.current) return;
    const s = Math.round((Date.now() - tRef.current) / 1000);
    if (s >= 1) { rRef.current = true; getTracker().track(entityType, entityId, 'dwell', s); }
    tRef.current = null;
  }, [entityType, entityId]);
  return { onMouseEnter: enter, onMouseLeave: leave };
}

/** 弹窗/详情停留追踪: visible=true开始, false上报 */
export function useView(entityType, entityId, visible) {
  const tRef = useRef(null);
  useEffect(() => {
    if (visible) { tRef.current = Date.now(); }
    else if (tRef.current) {
      const s = Math.round((Date.now() - tRef.current) / 1000);
      if (s >= 1) getTracker().track(entityType, entityId, 'view', s);
      tRef.current = null;
    }
  }, [visible, entityType, entityId]);
}

/** 点击追踪: 返回一个 onClick 回调 */
export function useClickCb(entityType, entityId, eventType = 'click') {
  return useCallback(() => getTracker().track(entityType, entityId, eventType), [entityType, entityId, eventType]);
}

/** 快捷方法: 直接发送事件 */
export function trackEvent(entityType, entityId, eventType, duration = 0, detail = {}) {
  getTracker().track(entityType, entityId, eventType, duration, detail);
}

export default { useDwell, useView, useClickCb, trackEvent };
