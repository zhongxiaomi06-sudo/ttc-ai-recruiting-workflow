/**
 * Shared parsers utilities for the TTC candidate collector extension.
 *
 * These helpers are used across all platform-specific parsers to identify
 * candidate cards vs. UI noise, normalize URLs, and detect anti-bot pages.
 */

export const RISK_WORDS = [
  '安全验证', '请输入验证码', '访问过于频繁', '操作过于频繁',
  '异常访问', '请完成验证', '登录后查看', '账号登录', '登录后使用',
  '请登录', '滑块验证', '人机验证', '验证身份', '访问验证',
  'captcha', 'verify you are human'
];

export const NON_CANDIDATE_LABELS = [
  '桌面客户端', '下载APP', '下载 App', '下载客户端', '手机扫码',
  '打开APP', '打开 App', '登录', '注册', '帮助中心', '隐私政策',
  '用户协议', '职位管理', '招聘者', '企业服务'
];

export const CANDIDATE_EVIDENCE = /(\d+\s*岁|\d+\s*年|本科|硕士|博士|大专|统招|在职|离职|求职|期望|工作经历|教育经历|咨询|战略|品牌|产品|渠道|运营|市场|经理|总监|负责人)/;

export const SUPPORTED_HOSTS = [
  'zhipin.com', 'liepin.com', 'maimai.cn',
  'linkedin.com', '51job.com', 'zhaopin.com',
  'app.ttcadvisory.com'
];

export function supportedHost(url) {
  try {
    const host = new URL(url).hostname;
    return SUPPORTED_HOSTS.some(domain => host === domain || host.endsWith('.' + domain));
  } catch {
    return false;
  }
}

export function looksLikeNonCandidateLabel(label) {
  const text = (label || '').replace(/\s+/g, '');
  return !text || NON_CANDIDATE_LABELS.some(word => text.includes(word.replace(/\s+/g, '')));
}

export function looksLikeCandidateText(text) {
  return CANDIDATE_EVIDENCE.test(text || '');
}

export function detectRisk(text, title, url) {
  const t = (text || '').toLowerCase();
  const titleL = (title || '').toLowerCase();
  const urlL = (url || '').toLowerCase();
  return RISK_WORDS.find(word =>
    t.includes(word.toLowerCase()) ||
    titleL.includes(word.toLowerCase()) ||
    urlL.includes(word.toLowerCase())
  ) || '';
}

export function normalizeUrl(url, base) {
  try {
    return new URL(url, base).href;
  } catch (_error) {
    return '';
  }
}

// 链接采集时统一排除的导航/下载/登录类噪音（各平台共用，取并集，宁多勿漏）。
const NEG_LABEL = /(桌面客户端|下载APP|下载App|下载客户端|打开APP|打开App|登录|注册|帮助|隐私|协议|企业服务|职位管理|招聘者)/;
const NEG_URL = /(download|desktop|client|app-download|appdownload|login|register|privacy|terms|help|about|contact|company|job\/detail|chat|message|setting|job_list|app\.html|\/app\/)/i;

/**
 * 候选人链接收集器：去重 + 过滤噪音 + 保留最高分。
 * 各平台 parser 共用，避免 5 份相同的 add() 闭包。
 * 用法: const c = makeLinkCollector(); c.add(url,label,score); ... c.links(maxItems)
 */
export function makeLinkCollector() {
  const seen = new Map();
  const add = (url, label, score) => {
    if (!url) return;
    const clean = normalizeUrl(url, location.href);
    if (!clean || clean === location.href) return;
    const compactLabel = (label || '').replace(/\s+/g, '');
    if (NEG_LABEL.test(compactLabel) || NEG_URL.test(clean)) return;
    const old = seen.get(clean);
    if (!old || score > old.score) seen.set(clean, {url: clean, label: String(label || clean).slice(0, 80), score});
  };
  const links = (maxItems) => Array.from(seen.values()).sort((a, b) => b.score - a.score).slice(0, maxItems);
  return {add, links, size: () => seen.size};
}

// 卡片兜底扫描时统一用的选择器与按钮噪音词。
export const CARD_SELECTORS = [
  '[class*=candidate]', '[class*=resume]', '[class*=geek]', '[class*=talent]',
  '[class*=jobhunter]', '[class*=recommend]', '[class*=profile]', '[class*=person]',
  '[class*=user]', '[class*=card]', '[class*=item]', '[role=link]', '[data-url]',
  '[data-href]', '[data-link]', '[data-path]'
].join(',');

const SKIP_LINE = /^(展开|收起|查看全部|更多|编辑|删除|举报|分享|收藏|投递|立即沟通|聊一聊|发简历|下载|导出)$/;

/**
 * 按分节标题把简历正文聚合成 {sections:[{heading,text}]}。
 * 统一了 boss/ttc/liepin/maimai 四份逐行雷同的 TreeWalker 逻辑；
 * 各平台只传 headings 与少量差异开关，行为与原实现一致。
 * opts.scanLines   正文前几行用于扫基础信息(默认60;ttc 用 80)
 * opts.basicMax    基础信息最多保留行数(默认12;ttc 用 15)
 * opts.withPhone   基础信息是否额外识别手机号(ttc 用 true)
 * opts.basicSelectors 额外的顶部信息选择器(boss 用)
 */
export function extractSections(headings, opts = {}) {
  const text = document.body ? document.body.innerText : '';
  const sections = [];
  const addSection = (heading, lines) => {
    if (!heading || !lines.length) return;
    sections.push({heading, text: lines.join('\n')});
  };

  // 1. 顶部基础信息
  const basic = [];
  const h1 = document.querySelector('h1');
  if (h1) basic.push(h1.innerText.trim());
  const nameEl = document.querySelector('[class*=name]');
  if (nameEl) {
    const t = nameEl.innerText.trim();
    if (t && t.length <= 40 && !basic.includes(t)) basic.push(t);
  }
  if (opts.basicSelectors) {
    for (const el of document.querySelectorAll(opts.basicSelectors)) {
      const t = (el.innerText || '').trim();
      if (t && t.length <= 80 && !basic.includes(t)) basic.push(t);
    }
  }
  const bodyStart = text.split('\n').slice(0, opts.scanLines || 60);
  for (const line of bodyStart) {
    const t = line.trim();
    const hit = /\d+岁/.test(t) || /\d+年经验/.test(t) || /本科|硕士|博士|大专/.test(t) ||
      (opts.withPhone && /1[3-9]\d{9}/.test(t));
    if (hit && !basic.includes(t)) basic.push(t);
  }
  if (basic.length) {
    sections.push({heading: '基础信息', text: basic.slice(0, opts.basicMax || 12).join('\n')});
  }

  // 2. 按分节标题聚合
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  let currentHeading = '';
  let currentLines = [];
  const pushCurrent = () => {
    if (currentHeading && currentLines.length) addSection(currentHeading, currentLines);
    currentHeading = '';
    currentLines = [];
  };
  while (walker.nextNode()) {
    const el = walker.currentNode;
    if (!el.innerText) continue;
    const t = el.innerText.trim();
    if (!t || t.length > 3000) continue;
    const isHeading = headings.includes(t) || headings.some(h => t.startsWith(h + ' '));
    if (isHeading && t.length <= 20) {
      pushCurrent();
      currentHeading = t.replace(/\s+/g, '');
      continue;
    }
    if (currentHeading) {
      if (SKIP_LINE.test(t)) continue;
      if (t.length >= 8 && !currentLines.includes(t)) currentLines.push(t);
    }
  }
  pushCurrent();

  if (sections.length <= 1) return {sections: [{heading: '全文', text}]};
  return {sections};
}

export function candidateUrlFrom(el) {
  if (!el) return '';
  const direct = el.matches && el.matches('a[href]') ? el : el.querySelector && el.querySelector('a[href]');
  if (direct && direct.href) return normalizeUrl(direct.href, location.href);
  const closest = el.closest && el.closest('a[href]');
  if (closest && closest.href) return normalizeUrl(closest.href, location.href);
  const attrs = ['data-url', 'data-href', 'data-link', 'data-path', 'data-target-url'];
  for (const attr of attrs) {
    const value = el.getAttribute && el.getAttribute(attr);
    if (value) return normalizeUrl(value, location.href);
  }
  if (el.dataset) {
    for (const value of Object.values(el.dataset)) {
      if (typeof value === 'string' && /\/|https?:|#/.test(value)) {
        const url = normalizeUrl(value, location.href);
        if (url) return url;
      }
    }
  }
  return '';
}

export function platformFromUrl(url) {
  try {
    const host = new URL(url).hostname;
    if (host.includes('zhipin.com')) return 'boss';
    if (host.includes('liepin.com')) return 'liepin';
    if (host.includes('maimai.cn')) return 'maimai';
    if (host.includes('linkedin.com')) return 'linkedin';
    if (host.includes('51job.com')) return '51job';
    if (host.includes('zhaopin.com')) return 'zhaopin';
    if (host.includes('app.ttcadvisory.com')) return 'ttc';
  } catch {
    return 'generic';
  }
  return 'generic';
}

// Expose helpers on window so injected page scripts can use them.
if (typeof window !== 'undefined') {
  window.__TTC_PARSERS = window.__TTC_PARSERS || {};
  window.__TTC_PARSERS.common = {
    RISK_WORDS,
    NON_CANDIDATE_LABELS,
    CANDIDATE_EVIDENCE,
    SUPPORTED_HOSTS,
    supportedHost,
    looksLikeNonCandidateLabel,
    looksLikeCandidateText,
    detectRisk,
    normalizeUrl,
    candidateUrlFrom,
    platformFromUrl,
    makeLinkCollector,
    extractSections,
    CARD_SELECTORS
  };
}
