// ==UserScript==
// @name         TTC-ChatGPT Reader
// @name:zh-CN   TTC ChatGPT 对话读取器
// @namespace    http://ttc.ai/
// @version      0.1.0
// @description  Auto-extract ChatGPT share conversation and send to TTC Daemon.
// @description:zh-CN 自动提取 ChatGPT 分享页面对话内容并推送到 TTC Daemon。
// @author       TTC
// @match        *://chatgpt.com/share/*
// @match        *://chat.openai.com/share/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @connect      *
// @license      GPL-3.0-only
// ==/UserScript==

(function () {
    'use strict';

    const SCRIPT_NAME = 'TTC-ChatGPT Reader';
    const DEFAULT_DAEMON_URL = 'http://127.0.0.1:8766';
    const CONFIG_KEY = 'ttc_chatgpt_reader_config';

    const GM = {
        get: (k, d) => {
            try { return typeof GM_getValue !== 'undefined' ? GM_getValue(k, d) : (JSON.parse(localStorage.getItem(k) ?? 'null') ?? d); }
            catch (e) { return d; }
        },
        set: (k, v) => {
            try { return typeof GM_setValue !== 'undefined' ? GM_setValue(k, v) : localStorage.setItem(k, JSON.stringify(v)); }
            catch (e) {}
        },
        xhr: (opts) => {
            if (typeof GM_xmlhttpRequest !== 'undefined') return GM_xmlhttpRequest(opts);
            fetch(opts.url, { method: opts.method || 'GET', headers: opts.headers, body: opts.data })
                .then(r => r.text().then(body => opts.onload && opts.onload({ status: r.status, responseText: body })))
                .catch(e => opts.onerror && opts.onerror(e));
        },
    };

    function loadConfig() {
        const def = { daemonUrl: DEFAULT_DAEMON_URL, apiToken: '', autoSend: true, debug: false };
        return Object.assign({}, def, GM.get(CONFIG_KEY, {}));
    }
    function saveConfig(cfg) { GM.set(CONFIG_KEY, cfg); }
    let config = loadConfig();

    function log(...args) {
        if (config.debug) console.log(`%c[${SCRIPT_NAME}]`, 'color:#6c5ce7;font-weight:bold', ...args);
    }

    function $el(tag, attrs = {}, children = []) {
        const el = document.createElement(tag);
        for (const [k, v] of Object.entries(attrs)) {
            if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
            else if (k === 'class') el.className = v;
            else if (k === 'onclick') el.addEventListener('click', v);
            else el.setAttribute(k, v);
        }
        for (const c of [].concat(children)) {
            if (typeof c === 'string') el.appendChild(document.createTextNode(c));
            else if (c) el.appendChild(c);
        }
        return el;
    }

    function showToast(text, duration = 2500) {
        let t = document.getElementById('ttc-chatgpt-toast');
        if (!t) {
            t = $el('div', { id: 'ttc-chatgpt-toast' });
            document.body.appendChild(t);
        }
        t.textContent = text;
        t.classList.add('show');
        setTimeout(() => t.classList.remove('show'), duration);
    }

    function extractTurns() {
        // ChatGPT 分享页常见 DOM 特征（会随前端改版变化）
        const turns = [];
        const nodes = document.querySelectorAll('[data-testid*="conversation-turn"], [data-testid*="chat-turn"]');
        if (nodes.length) {
            nodes.forEach((node, idx) => {
                const isUser = node.textContent.includes('You said') ||
                               node.innerHTML.includes('user') ||
                               node.querySelector('[class*="user"]') !== null;
                const text = (node.innerText || '').replace(/You said\n?/i, '').trim();
                if (text) turns.push({ role: isUser ? 'user' : 'assistant', text });
            });
        }
        if (turns.length) return turns;

        // 兜底：提取整个对话区域文本
        const main = document.querySelector('main, article, [class*="conversation"], [class*="chat-content"]');
        if (main) {
            return [{ role: 'raw', text: main.innerText.trim() }];
        }
        return [{ role: 'raw', text: document.body.innerText.trim() }];
    }

    function buildPayload() {
        const turns = extractTurns();
        return {
            source_type: 'chatgpt_share',
            source_url: location.href,
            title: document.title.trim(),
            raw_text: turns.map(t => `[${t.role}]\n${t.text}`).join('\n\n---\n\n'),
            markdown: turns.map(t => `**${t.role}**\n\n${t.text}`).join('\n\n---\n\n'),
            turns: turns,
            collected_at: new Date().toISOString(),
            user_agent: navigator.userAgent,
        };
    }

    function sendToDaemon(payload, silent = false) {
        const url = (config.daemonUrl || DEFAULT_DAEMON_URL).replace(/\/$/, '') + '/ingest/link';
        const headers = { 'Content-Type': 'application/json' };
        if (config.apiToken) headers['X-TTC-Token'] = config.apiToken;
        log('Sending to', url, payload);
        if (!silent) showToast('正在读取并发送 ChatGPT 对话...');
        GM.xhr({
            method: 'POST',
            url: url,
            headers: headers,
            data: JSON.stringify(payload),
            onload: (res) => {
                log('Response', res.status, res.responseText);
                if (res.status >= 200 && res.status < 300) {
                    if (!silent) showToast('✓ ChatGPT 对话已发送到 TTC Daemon');
                } else {
                    if (!silent) showToast('✗ 发送失败：' + res.status);
                }
            },
            onerror: (err) => {
                log('Error', err);
                if (!silent) showToast('✗ 无法连接 TTC Daemon');
            },
        });
    }

    function addStyles() {
        const css = `
            #ttc-chatgpt-fab {
                position: fixed; right: 24px; bottom: 24px; z-index: 2147483646;
                width: 56px; height: 56px; border-radius: 50%;
                background: linear-gradient(135deg, #6c5ce7, #74b9ff);
                color: #fff; font-size: 12px; font-weight: 600;
                display: flex; align-items: center; justify-content: center;
                cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.3);
                user-select: none; transition: transform .15s ease;
            }
            #ttc-chatgpt-fab:hover { transform: scale(1.05); }
            #ttc-chatgpt-toast {
                position: fixed; left: 50%; top: 60px; transform: translate(-50%, -8px);
                z-index: 2147483647; background: rgba(0,0,0,.78); color: #fff;
                padding: 8px 16px; border-radius: 6px; font-size: 13px;
                opacity: 0; transition: opacity .2s ease, transform .2s ease;
                pointer-events: none;
            }
            #ttc-chatgpt-toast.show { opacity: 1; transform: translate(-50%, 0); }
        `;
        const style = document.createElement('style');
        style.textContent = css;
        (document.head || document.documentElement).appendChild(style);
    }

    function buildUI() {
        addStyles();
        const fab = $el('div', { id: 'ttc-chatgpt-fab' }, '→TTC');
        fab.addEventListener('click', () => sendToDaemon(buildPayload()));
        document.body.appendChild(fab);
    }

    function configure() {
        const daemonUrl = prompt('TTC Daemon 地址', config.daemonUrl || DEFAULT_DAEMON_URL);
        if (daemonUrl === null) return;
        const apiToken = prompt('TTC API Token（服务器部署时填写；本地可留空）', config.apiToken || '');
        if (apiToken === null) return;
        config.daemonUrl = daemonUrl.trim() || DEFAULT_DAEMON_URL;
        config.apiToken = apiToken.trim();
        saveConfig(config);
        showToast('TTC 设置已保存');
    }

    function init() {
        if (window.__ttcChatgptReaderLoaded) return;
        window.__ttcChatgptReaderLoaded = true;

        const run = () => {
            buildUI();
            if (typeof GM_registerMenuCommand !== 'undefined') {
                GM_registerMenuCommand('发送 ChatGPT 对话到 TTC', () => sendToDaemon(buildPayload()));
                GM_registerMenuCommand('TTC 设置服务器地址/Token', configure);
            }
            if (config.autoSend) {
                // 等待页面渲染完成
                setTimeout(() => {
                    log('Auto-send triggered');
                    sendToDaemon(buildPayload(), true);
                }, 4500);
            }
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', run);
        } else {
            run();
        }
    }

    init();
})();
