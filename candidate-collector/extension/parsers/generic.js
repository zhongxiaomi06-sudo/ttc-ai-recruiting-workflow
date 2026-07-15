/**
 * Generic fallback parser for supported recruiting sites.
 */

import { candidateUrlFrom, looksLikeCandidateText, looksLikeNonCandidateLabel, makeLinkCollector, CARD_SELECTORS } from './common.js';

export function findGenericCandidateLinks(maxItems) {
  const {add, links} = makeLinkCollector();

  const positive = /(geek|candidate|resume|talent|recommend|jobhunter|profile|user|resume-detail|cview|resumeview)/i;
  const evidence = /(\d+\s*岁|\d+\s*年|本科|硕士|博士|咨询|战略|品牌|产品|渠道)/;
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.href || '';
    const text = (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim();
    if (!href || href === location.href || !href.startsWith(location.origin)) continue;
    if (looksLikeNonCandidateLabel(text)) continue;
    const card = a.closest('[class*=candidate],[class*=resume],[class*=geek],[class*=talent],[class*=card],[class*=item],li');
    const cardText = card ? (card.innerText || '').replace(/\s+/g, ' ').trim() : text;
    if (!looksLikeCandidateText(cardText) && !positive.test(href)) continue;
    let score = 0;
    if (positive.test(href)) score += 5;
    if (evidence.test(cardText || text)) score += 3;
    if (text.length >= 2 && text.length <= 160) score += 1;
    if (card) score += 3;
    if (score < 5) continue;
    add(href, text || cardText.slice(0, 80), score);
  }

  const cards = Array.from(document.querySelectorAll(CARD_SELECTORS)).slice(0, 300);
  for (const card of cards) {
    const cardText = (card.innerText || card.textContent || '').replace(/\s+/g, ' ').trim();
    if (cardText.length < 8 || cardText.length > 2500) continue;
    if (looksLikeNonCandidateLabel(cardText)) continue;
    if (!looksLikeCandidateText(cardText)) continue;
    const href = candidateUrlFrom(card);
    if (!href || !href.startsWith(location.origin)) continue;
    let score = 4;
    if (positive.test(href)) score += 4;
    if (evidence.test(cardText)) score += 4;
    if (/工作经历|教育经历|求职|期望|在职|离职/.test(cardText)) score += 2;
    if (score < 6) continue;
    add(href, cardText.slice(0, 80), score);
  }

  return links(maxItems);
}

if (typeof window !== 'undefined') {
  window.__TTC_PARSERS = window.__TTC_PARSERS || {};
  window.__TTC_PARSERS.generic = { findGenericCandidateLinks };
}
