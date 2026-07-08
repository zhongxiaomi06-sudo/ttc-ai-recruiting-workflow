// ==UserScript==
// @name         TTC-ChatGPT Reader
// @name:zh-CN   TTC ChatGPT 对话读取器
// @namespace    https://github.com/zhongxiaomi06-sudo
// @version      0.1.0
// @description  打开 ChatGPT share link 后自动提取对话文本，发送到本地 TTC Daemon。
// @author       TTC AI Team
// @match        *://chatgpt.com/share/*
// @match        *://chat.openai.com/share/*
// @grant        GM_xmlhttpRequest
// @grant        GM_notification
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @run-at       document-idle
// @license      MIT
// ==/UserScript==

(function () {
  'use strict';

  const DEFAULT_DAEMON_URL = 'http://127.0.0.1:8766';
  const CONFIG_KEY = 'ttc_chatgpt_reader_config';

  function loadConfig() {
    const saved = GM_getValue(CONFIG_KEY, null);
    const defaults = { daemonUrl: DEFAULT_DAEMON_URL, apiToken: '', autoSend: true };
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
      console.log('[TTC-ChatGPT]', title, text);
    }
  }

  function sendToDaemon(payload) {
    const url = config.daemonUrl.replace(/\/$/, '') + '/ingest/link';
    const headers = { 'Content-Type': 'application/json' };
    if (config.apiToken) headers['X-TTC-Token'] = config.apiToken;
    GM_xmlhttpRequest({
      method: 'POST',
      url: url,
      headers: headers,
      data: JSON.stringify(payload),
      onload: (res) => {
        if (res.status >= 200 && res.status < 300) {
          notify('TTC', 'ChatGPT 对话已发送到本地 Daemon');
        } else {
          notify('TTC 发送失败', `HTTP ${res.status}: ${res.responseText}`);
        }
      },
      onerror: () => {
        notify('TTC 发送失败', '请确认本地 Daemon 已启动');
      },
    });
  }

  function extractConversation() {
    // OpenAI ChatGPT share 页通常使用 data-testid="conversation-turn" 和 data-message-author-role
    const turns = document.querySelectorAll('[data-testid="conversation-turn"]');
    const messages = [];
    turns.forEach((turn) => {
      const roleEl = turn.querySelector('[data-message-author-role]');
      const role = roleEl ? roleEl.getAttribute('data-message-author-role') : 'unknown';
      const text = turn.innerText.trim();
      if (text) {
        messages.push({ role, text });
      }
    });

    if (messages.length === 0) {
      // 兜底：按 article 提取
      document.querySelectorAll('article').forEach((article) => {
        const text = article.innerText.trim();
        if (text) messages.push({ role: 'unknown', text });
      });
    }

    return messages;
  }

  function buildPayload(messages) {
    const markdown = messages
      .map((m) => `**${m.role}**:\n${m.text}`)
      .join('\n\n---\n\n');
    return {
      source_type: 'chatgpt_share',
      source_url: location.href,
      title: document.title,
      raw_text: markdown,
      markdown: markdown,
      captured_at: new Date().toISOString(),
      access_basis: 'public_share_page',
    };
  }

  function sendConversation() {
    const messages = extractConversation();
    if (!messages.length) {
      notify('TTC', '未提取到对话内容，请等待页面加载完成');
      return;
    }
    sendToDaemon(buildPayload(messages));
  }

  function waitAndExtract(maxWaitMs = 30000) {
    const start = Date.now();
    const interval = setInterval(() => {
      const messages = extractConversation();
      if (messages.length > 0) {
        clearInterval(interval);
        if (config.autoSend) {
          sendToDaemon(buildPayload(messages));
        } else {
          notify('TTC', `已提取 ${messages.length} 条对话，点击面板发送`);
        }
        return;
      }
      if (Date.now() - start > maxWaitMs) {
        clearInterval(interval);
        notify('TTC', '等待对话加载超时，请尝试手动发送');
      }
    }, 1000);
  }

  function createPanel() {
    const panel = document.createElement('div');
    panel.id = 'ttc-chatgpt-panel';
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
      minWidth: '150px',
    });

    const title = document.createElement('div');
    title.textContent = 'TTC ChatGPT';
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

    panel.appendChild(btn('发送对话 → TTC', sendConversation));
    panel.appendChild(btn('设置 Daemon 地址', () => {
      const newUrl = prompt('TTC Daemon 地址', config.daemonUrl);
      if (newUrl) {
        config.daemonUrl = newUrl;
        saveConfig(config);
        notify('TTC', 'Daemon 地址已保存');
      }
    }));
    panel.appendChild(btn('设置 API Token', () => {
      const newToken = prompt('TTC API Token（未启用可留空）', config.apiToken || '');
      if (newToken !== null) {
        config.apiToken = newToken;
        saveConfig(config);
        notify('TTC', 'API Token 已保存');
      }
    }));

    const toggle = document.createElement('label');
    toggle.style.display = 'flex';
    toggle.style.alignItems = 'center';
    toggle.style.gap = '6px';
    toggle.style.cursor = 'pointer';
    toggle.style.marginTop = '4px';
    toggle.innerHTML = `<input type="checkbox" ${config.autoSend ? 'checked' : ''}> 自动发送`;
    toggle.querySelector('input').addEventListener('change', (e) => {
      config.autoSend = e.target.checked;
      saveConfig(config);
    });
    panel.appendChild(toggle);

    document.body.appendChild(panel);
  }

  function init() {
    if (document.getElementById('ttc-chatgpt-panel')) return;
    createPanel();
    GM_registerMenuCommand('发送 ChatGPT 对话到 TTC', sendConversation);
    waitAndExtract();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
