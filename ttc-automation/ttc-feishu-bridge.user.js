// ==UserScript==
// @name         TTC-Feishu Bridge
// @name:zh-CN   TTC 飞书桥接器
// @namespace    https://github.com/zhongxiaomi06-sudo
// @version      0.1.0
// @description  将飞书页面内容一键发送到本地 TTC Daemon，作为 AI 猎头工作流的输入源。
// @author       TTC AI Team
// @match        *://*.feishu.cn/*
// @match        *://*.larksuite.com/*
// @match        *://*.larkoffice.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_notification
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @run-at       document-end
// @license      MIT
// ==/UserScript==

(function () {
  'use strict';

  const DEFAULT_DAEMON_URL = 'http://127.0.0.1:8766';
  const CONFIG_KEY = 'ttc_feishu_bridge_config';

  function loadConfig() {
    const saved = GM_getValue(CONFIG_KEY, null);
    const defaults = { daemonUrl: DEFAULT_DAEMON_URL, apiToken: '', autoDetect: false };
    return saved ? Object.assign(defaults, saved) : defaults;
  }

  function saveConfig(cfg) {
    GM_setValue(CONFIG_KEY, cfg);
  }

  let config = loadConfig();

  function notify(title, text) {
    try {
      GM_notification({ title, text });
    } catch (e) {
      console.log('[TTC-Feishu]', title, text);
    }
  }

  function sendToDaemon(payload) {
    const url = config.daemonUrl.replace(/\/$/, '') + '/ingest/feishu';
    const headers = { 'Content-Type': 'application/json' };
    if (config.apiToken) headers['X-TTC-Token'] = config.apiToken;
    GM_xmlhttpRequest({
      method: 'POST',
      url: url,
      headers: headers,
      data: JSON.stringify(payload),
      onload: (res) => {
        if (res.status >= 200 && res.status < 300) {
          notify('TTC', '已发送到本地 Daemon');
        } else {
          notify('TTC 发送失败', `HTTP ${res.status}: ${res.responseText}`);
        }
      },
      onerror: (err) => {
        notify('TTC 发送失败', '请确认本地 Daemon 已启动：python ttc_daemon.py');
      },
    });
  }

  function extractPageContent() {
    // 优先尝试飞书文档正文容器，降级为页面可见文本
    const selectors = [
      '[class*="doc-content"]',
      '[class*="wiki-content"]',
      '[class*="sheet-grid"]',
      '[role="document"]',
      'article',
      '.body',
      'main',
    ];
    let el = null;
    for (const s of selectors) {
      el = document.querySelector(s);
      if (el && el.innerText.trim().length > 100) break;
    }
    if (!el || el.innerText.trim().length < 50) {
      el = document.body;
    }
    return el.innerText.trim();
  }

  function extractSelection() {
    const sel = window.getSelection();
    return sel ? sel.toString().trim() : '';
  }

  function buildPayload(content, isSelection) {
    return {
      source_type: 'feishu_web',
      source_url: location.href,
      title: document.title,
      raw_text: content,
      markdown: content,
      selected: isSelection,
      user_agent: navigator.userAgent,
      captured_at: new Date().toISOString(),
    };
  }

  function sendPage() {
    const content = extractPageContent();
    sendToDaemon(buildPayload(content, false));
  }

  function sendSelection() {
    const content = extractSelection();
    if (!content) {
      notify('TTC', '请先选中页面上的文本');
      return;
    }
    sendToDaemon(buildPayload(content, true));
  }

  function createPanel() {
    const panel = document.createElement('div');
    panel.id = 'ttc-feishu-panel';
    Object.assign(panel.style, {
      position: 'fixed',
      right: '20px',
      bottom: '20px',
      zIndex: '999999',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      fontSize: '13px',
      color: '#e8e8f0',
      background: '#13131a',
      border: '1px solid #1e1e2e',
      borderRadius: '10px',
      padding: '10px',
      boxShadow: '0 4px 12px rgba(0,0,0,.4)',
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
      minWidth: '140px',
    });

    const title = document.createElement('div');
    title.textContent = 'TTC';
    Object.assign(title.style, { fontWeight: '700', color: '#00cec9', marginBottom: '4px' });
    panel.appendChild(title);

    function btn(text, onClick) {
      const b = document.createElement('button');
      b.textContent = text;
      Object.assign(b.style, {
        background: '#1a1a2e',
        border: '1px solid #2e2e3e',
        color: '#c8c8d4',
        borderRadius: '6px',
        padding: '6px 10px',
        cursor: 'pointer',
        textAlign: 'left',
      });
      b.addEventListener('mouseenter', () => (b.style.background = '#252536'));
      b.addEventListener('mouseleave', () => (b.style.background = '#1a1a2e'));
      b.addEventListener('click', onClick);
      return b;
    }

    panel.appendChild(btn('发送整页 → TTC', sendPage));
    panel.appendChild(btn('发送选中 → TTC', sendSelection));

    const cfgBtn = btn('设置 Daemon 地址', () => {
      const newUrl = prompt('TTC Daemon 地址', config.daemonUrl);
      if (newUrl) {
        config.daemonUrl = newUrl;
        saveConfig(config);
        notify('TTC', 'Daemon 地址已保存');
      }
    });
    panel.appendChild(cfgBtn);

    const tokenBtn = btn('设置 API Token', () => {
      const newToken = prompt('TTC API Token（未启用可留空）', config.apiToken || '');
      if (newToken !== null) {
        config.apiToken = newToken;
        saveConfig(config);
        notify('TTC', 'API Token 已保存');
      }
    });
    panel.appendChild(tokenBtn);

    const toggle = document.createElement('label');
    toggle.style.display = 'flex';
    toggle.style.alignItems = 'center';
    toggle.style.gap = '6px';
    toggle.style.cursor = 'pointer';
    toggle.style.marginTop = '4px';
    toggle.innerHTML = `<input type="checkbox" ${config.autoDetect ? 'checked' : ''}> 自动识别 JD`;
    toggle.querySelector('input').addEventListener('change', (e) => {
      config.autoDetect = e.target.checked;
      saveConfig(config);
    });
    panel.appendChild(toggle);

    document.body.appendChild(panel);
  }

  function maybeAutoDetect() {
    if (!config.autoDetect) return;
    const text = document.body.innerText;
    const keywords = ['JD', '职位描述', '招聘', '猎头', '简历', '候选人', '岗位要求'];
    const matched = keywords.some((k) => text.includes(k));
    if (matched) {
      notify('TTC', '检测到招聘相关页面，3 秒后自动发送');
      setTimeout(sendPage, 3000);
    }
  }

  function init() {
    if (document.getElementById('ttc-feishu-panel')) return;
    createPanel();
    GM_registerMenuCommand('发送整页到 TTC', sendPage);
    GM_registerMenuCommand('发送选中到 TTC', sendSelection);
    setTimeout(maybeAutoDetect, 2000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
