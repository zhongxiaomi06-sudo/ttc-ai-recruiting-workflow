/**
 * TTC 自动单页导入 content script.
 *
 * 当用户在 TTC 网站点击候选人进入详情页（/app/talent/{id}）时，此脚本
 * 自动读取当前页面文本并通过 background.js 写入飞书人才库。
 * 无需点击浏览器插件图标。
 */

(function () {
  'use strict';

  const STATUS_ID = 'ttc-auto-import-status';

  function isTtcCandidateDetail(url) {
    return /^https:\/\/app\.ttcadvisory\.com\/app\/talent\/\d+/.test(url || location.href);
  }

  function candidateIdFromUrl(url) {
    try {
      const u = new URL(url || location.href);
      const match = u.pathname.match(/\/app\/talent\/(\d+)/);
      return match ? match[1] : '';
    } catch {
      return '';
    }
  }

  function alreadyImported(candidateId) {
    const key = 'ttc_auto_imported_' + candidateId;
    return sessionStorage.getItem(key) === '1';
  }

  function markImported(candidateId) {
    try {
      sessionStorage.setItem('ttc_auto_imported_' + candidateId, '1');
    } catch {
      // ignore
    }
  }

  function showStatus(message, type) {
    let el = document.getElementById(STATUS_ID);
    if (!el) {
      el = document.createElement('div');
      el.id = STATUS_ID;
      el.style.cssText = [
        'position: fixed',
        'right: 24px',
        'bottom: 24px',
        'z-index: 2147483640',
        'max-width: 280px',
        'padding: 12px 16px',
        'border-radius: 10px',
        'background: #172026',
        'color: #fff',
        'font-size: 13px',
        'line-height: 1.5',
        'box-shadow: 0 4px 12px rgba(0,0,0,0.15)',
        'transition: opacity .3s ease',
      ].join(';');
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.style.background = type === 'error' ? '#a34734' : type === 'success' ? '#0d6f63' : '#3e7bf4';
    el.style.opacity = '1';
    setTimeout(() => { el.style.opacity = '0'; }, type === 'error' ? 8000 : 5000);
  }

  function sendMessage(message) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(message, response => {
        if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
        if (!response || !response.ok) return reject(new Error((response && response.error) || '导入失败'));
        resolve(response);
      });
    });
  }

  async function autoImportCurrentDetail() {
    const cid = candidateIdFromUrl(location.href);
    if (!cid) return;
    if (alreadyImported(cid)) return;

    showStatus('正在自动导入当前候选人...', 'info');
    try {
      const result = await sendMessage({type: 'autoImportCurrentDetail'});
      markImported(cid);
      if (result.action === 'created') {
        showStatus('已自动导入飞书：' + (result.candidate && result.candidate.name), 'success');
      } else if (result.action && result.action.includes('duplicate')) {
        showStatus('已存在，跳过：' + (result.candidate && result.candidate.name), 'success');
      } else {
        showStatus('导入结果：' + (result.action || 'ok'), 'success');
      }
    } catch (error) {
      showStatus('自动导入失败：' + error.message, 'error');
    }
  }

  function checkAndImport() {
    if (isTtcCandidateDetail(location.href)) {
      // Give the SPA a moment to render the detail content.
      setTimeout(autoImportCurrentDetail, 1500);
    }
  }

  // React SPA navigation detection.
  let lastUrl = location.href;
  const observer = new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      checkAndImport();
    }
  });
  observer.observe(document.documentElement, {childList: true, subtree: true});

  checkAndImport();
})();
