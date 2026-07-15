/**
 * BOSS 直聘 (zhipin.com) parser.
 */

import { candidateUrlFrom, looksLikeCandidateText, looksLikeNonCandidateLabel, extractSections, makeLinkCollector, CARD_SELECTORS } from './common.js';

export function isBossPage(url) {
  return /zhipin\.com/.test(new URL(url).hostname) && /geek|jobhunter|candidate|resume/i.test(url);
}

export function isBossManagementPage(url) {
  return /zhipin\.com/.test(new URL(url).hostname) &&
    /\/chat\/|\/manage\/|\/tools\/|\/prop\/|\/vip\/|\/data\/|\/job_list\/| ka=action/.test(url);
}

const BOSS_HEADINGS = ['个人优势', '工作经历', '项目经历', '教育经历', '技能专长', '求职期望'];

export function extractBossSections() {
  return extractSections(BOSS_HEADINGS, {
    basicSelectors: '.info-label, .base-info, .job-info, [class*="info"] .text, [class*="base"] .text, .name-box .label'
  });
}

export function findBossCandidateLinks(maxItems) {
  const {add, links} = makeLinkCollector();

  const bossNegative = /(\/chat\/|\/message\/|\/manage\/|\/tools\/|\/prop\/|\/vip\/|\/data\/|\/company\/|\/job_detail\/)/i;
  for (const a of document.querySelectorAll('a[href*="/geek/"], a[href*="/jobhunter/"]')) {
    const href = a.href ? a.href.split('#')[0] : '';
    if (!href || bossNegative.test(href)) continue;
    const pathMatch = href.match(/\/(geek|jobhunter)\/([^/]+)/);
    if (!pathMatch) continue;
    const segment = pathMatch[2];
    if (/^(manage|recommend|tools|prop|data|vip|setting|help)$/i.test(segment)) continue;
    const text = (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim();
    const card = a.closest('[class*="card"], [class*="item"], [class*="geek"], [class*="recommend"], li');
    const cardText = card ? (card.innerText || '').replace(/\s+/g, ' ').trim() : '';
    if (!looksLikeCandidateText(cardText || text)) continue;
    let score = 10;
    if (/\d+岁/.test(cardText || text)) score += 3;
    if (/\d+年/.test(cardText || text)) score += 3;
    if (/(本科|硕士|博士)/.test(cardText || text)) score += 2;
    add(href, text || cardText.slice(0, 60), score);
  }

  // Fallback to generic card selectors.
  const cards = Array.from(document.querySelectorAll(CARD_SELECTORS)).slice(0, 300);
  for (const card of cards) {
    const cardText = (card.innerText || card.textContent || '').replace(/\s+/g, ' ').trim();
    if (cardText.length < 8 || cardText.length > 2500) continue;
    if (looksLikeNonCandidateLabel(cardText)) continue;
    if (!looksLikeCandidateText(cardText)) continue;
    const href = candidateUrlFrom(card);
    if (!href || !href.startsWith(location.origin)) continue;
    let score = 4;
    if (/geek|jobhunter|candidate|resume/i.test(href)) score += 4;
    if (/\d+\s*岁|\d+\s*年|本科|硕士|博士/.test(cardText)) score += 4;
    if (/工作经历|教育经历|求职|期望|在职|离职/.test(cardText)) score += 2;
    if (score < 6) continue;
    add(href, cardText.slice(0, 80), score);
  }

  return links(maxItems);
}

if (typeof window !== 'undefined') {
  window.__TTC_PARSERS = window.__TTC_PARSERS || {};
  window.__TTC_PARSERS.boss = {
    isBossPage,
    isBossManagementPage,
    extractBossSections,
    findBossCandidateLinks
  };
}
