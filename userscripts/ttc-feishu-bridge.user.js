// ==UserScript==
// @name         TTC-Feishu Bridge
// @name:zh-CN   TTC 飞书桥接
// @namespace    http://ttc.ai/
// @version      0.1.0
// @description  Extract Feishu/Lark docx/wiki/chat/sheet content and send to TTC Daemon.
// @description:zh-CN 提取飞书文档/Wiki/聊天/表格内容并推送到 TTC Daemon。
// @author       TTC
// @match        *://*.feishu.cn/*
// @match        *://*.larksuite.com/*
// @match        *://*.larkoffice.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @connect      *
// @homepageURL  https://github.com/BlueSkyXN/feishu-toolkit
// @license      GPL-3.0-only
// ==/UserScript==

(function () {
    'use strict';

    const SCRIPT_NAME = 'TTC-Feishu Bridge';
    const DEFAULT_DAEMON_URL = 'http://127.0.0.1:8766';
    const CONFIG_KEY = 'ttc_feishu_bridge_config';

    // ------------------------------------------------------------------
    // 配置
    // ------------------------------------------------------------------
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
            // 降级到 fetch（可能受 CORS 限制，Tampermonkey 下通常不会走到这里）
            fetch(opts.url, {
                method: opts.method || 'GET',
                headers: opts.headers,
                body: opts.data,
            })
            .then(r => r.text().then(body => opts.onload && opts.onload({ status: r.status, responseText: body })))
            .catch(e => opts.onerror && opts.onerror(e));
        },
    };

    function loadConfig() {
        const def = { daemonUrl: DEFAULT_DAEMON_URL, apiToken: '', autoSend: false, debug: false };
        return Object.assign({}, def, GM.get(CONFIG_KEY, {}));
    }
    function saveConfig(cfg) { GM.set(CONFIG_KEY, cfg); }
    let config = loadConfig();

    function log(...args) {
        if (config.debug) console.log(`%c[${SCRIPT_NAME}]`, 'color:#00cec9;font-weight:bold', ...args);
    }

    // ------------------------------------------------------------------
    // 工具函数
    // ------------------------------------------------------------------
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

    function showToast(text, duration = 2000) {
        let t = document.getElementById('ttc-feishu-toast');
        if (!t) {
            t = $el('div', { id: 'ttc-feishu-toast' });
            document.body.appendChild(t);
        }
        t.textContent = text;
        t.classList.add('show');
        setTimeout(() => t.classList.remove('show'), duration);
    }

    function detectPageType() {
        const host = location.hostname;
        const path = location.pathname;
        if (/\/docx\//.test(path)) return 'docx';
        if (/\/wiki\//.test(path)) return 'wiki';
        if (/\/sheets\//.test(path)) return 'sheet';
        if (/\/minutes\//.test(path) || /\/vc\//.test(path)) return 'minutes';
        if (/\/messenger\//.test(path) || /\/chat\//.test(path) || /\/message\//.test(path)) return 'chat';
        if (/\/base\//.test(path) || /\/bitable\//.test(path)) return 'base';
        return 'unknown';
    }

    function extractTitle() {
        // 飞书文档常把标题放在 h1 或 document.title
        const h1 = document.querySelector('h1');
        if (h1 && h1.innerText.trim()) return h1.innerText.trim();
        const titleEl = document.querySelector('[class*="title"], [class*="doc-title"]');
        if (titleEl && titleEl.innerText.trim()) return titleEl.innerText.trim();
        return document.title.trim();
    }

    function findMainContentElement() {
        // 优先尝试飞书常见容器选择器
        const selectors = [
            '[class*="docx-page"]',
            '[class*="docx-page-container"]',
            '[class*="document-content"]',
            '[class*="wiki-content"]',
            '[class*="sheet-content"]',
            '[class*="chat-messages"]',
            '[class*="message-list"]',
            '[class*="minutes-content"]',
            '[role="main"]',
            'main',
            'article',
        ];
        for (const s of selectors) {
            const el = document.querySelector(s);
            if (el && el.innerText.trim().length > 100) return el;
        }
        // 启发式：找文本量最大的 div/section/article
        let best = null;
        let bestLen = 0;
        const candidates = document.querySelectorAll('div, section, article');
        for (const el of candidates) {
            if (el.closest('header, nav, aside, footer, #ttc-feishu-fab, #ttc-feishu-panel')) continue;
            const text = el.innerText?.trim() || '';
            if (text.length > bestLen && text.length > 200) {
                bestLen = text.length;
                best = el;
            }
        }
        return best;
    }

    function extractContent() {
        const main = findMainContentElement();
        if (main) return main.innerText.trim();
        return document.body.innerText.trim();
    }

    function extractChatMessages() {
        // 聊天页尽量按消息块提取，保留发言结构
        const msgSelectors = [
            '[class*="message-content"]',
            '[class*="message-text"]',
            '[class*="chat-message"]',
            '[data-testid*="message"]',
        ];
        for (const s of msgSelectors) {
            const msgs = Array.from(document.querySelectorAll(s)).map(el => el.innerText.trim()).filter(Boolean);
            if (msgs.length >= 3) return msgs.join('\n---\n');
        }
        return null;
    }

    function looksLikeJD(text) {
        const keywords = ['JD', '职位', '招聘', '岗位职责', '任职要求', '薪资', '简历', '候选人', 'hc', 'headcount'];
        const lower = text.toLowerCase();
        return keywords.some(k => lower.includes(k.toLowerCase()));
    }

    function buildPayload() {
        const pageType = detectPageType();
        let content = extractContent();
        const chatMessages = pageType === 'chat' ? extractChatMessages() : null;
        if (chatMessages) content = chatMessages;
        return {
            source_type: 'feishu_' + pageType,
            source_url: location.href,
            title: extractTitle(),
            raw_text: content,
            markdown: '', // Daemon 端可再转
            page_type: pageType,
            collected_at: new Date().toISOString(),
            user_agent: navigator.userAgent,
        };
    }

    // ------------------------------------------------------------------
    // 发送逻辑
    // ------------------------------------------------------------------
    function sendToDaemon(payload, silent = false) {
        const url = (config.daemonUrl || DEFAULT_DAEMON_URL).replace(/\/$/, '') + '/ingest/feishu';
        const headers = { 'Content-Type': 'application/json' };
        if (config.apiToken) headers['X-TTC-Token'] = config.apiToken;
        log('Sending to', url, payload);
        if (!silent) showToast('正在发送到 TTC...');
        GM.xhr({
            method: 'POST',
            url: url,
            headers: headers,
            data: JSON.stringify(payload),
            onload: (res) => {
                log('Response', res.status, res.responseText);
                if (res.status >= 200 && res.status < 300) {
                    if (!silent) showToast('✓ 已发送到 TTC Daemon');
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

    function sendCurrentPage(silent = false) {
        sendToDaemon(buildPayload(), silent);
    }

    // ------------------------------------------------------------------
    // UI：浮动按钮 + 设置面板
    // ------------------------------------------------------------------
    function addStyles() {
        const css = `
            #ttc-feishu-fab {
                position: fixed; right: 24px; bottom: 24px; z-index: 2147483646;
                width: 56px; height: 56px; border-radius: 50%;
                background: linear-gradient(135deg, #6c5ce7, #00cec9);
                color: #fff; font-size: 13px; font-weight: 600;
                display: flex; align-items: center; justify-content: center;
                cursor: pointer; box-shadow: 0 6px 20px rgba(0,0,0,.3);
                user-select: none; transition: transform .15s ease, box-shadow .15s ease;
            }
            #ttc-feishu-fab:hover { transform: scale(1.05); box-shadow: 0 8px 26px rgba(0,0,0,.4); }
            #ttc-feishu-panel {
                position: fixed; right: 24px; bottom: 96px; z-index: 2147483647;
                width: 320px; background: #fff; color: #1f2329; border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,.25); padding: 16px;
                font: 13px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
                display: none; flex-direction: column; gap: 12px;
            }
            #ttc-feishu-panel.show { display: flex; }
            #ttc-feishu-panel h4 { margin: 0; font-size: 14px; color: #1f2329; }
            #ttc-feishu-panel label { display: flex; align-items: center; justify-content: space-between; color: #333; }
            #ttc-feishu-panel input[type="text"], #ttc-feishu-panel input[type="password"] {
                width: 100%; padding: 6px 8px; border: 1px solid #ddd; border-radius: 6px; margin-top: 4px;
            }
            #ttc-feishu-panel .btn {
                background: #6c5ce7; color: #fff; border: 0; border-radius: 6px;
                padding: 8px 12px; cursor: pointer; font-weight: 500;
            }
            #ttc-feishu-panel .btn.secondary { background: #f2f3f5; color: #333; }
            #ttc-feishu-panel .row { display: flex; gap: 8px; }
            #ttc-feishu-toast {
                position: fixed; left: 50%; top: 60px; transform: translate(-50%, -8px);
                z-index: 2147483647; background: rgba(0,0,0,.78); color: #fff;
                padding: 8px 16px; border-radius: 6px; font-size: 13px;
                opacity: 0; transition: opacity .2s ease, transform .2s ease;
                pointer-events: none;
            }
            #ttc-feishu-toast.show { opacity: 1; transform: translate(-50%, 0); }
        `;
        const style = document.createElement('style');
        style.textContent = css;
        (document.head || document.documentElement).appendChild(style);
    }

    function buildUI() {
        addStyles();

        const fab = $el('div', { id: 'ttc-feishu-fab' }, 'TTC');
        document.body.appendChild(fab);

        const panel = $el('div', { id: 'ttc-feishu-panel' }, [
            $el('h4', {}, 'TTC 飞书桥接'),
            $el('div', {}, [
                $el('label', {}, 'Daemon 地址'),
                $el('input', { type: 'text', id: 'ttc-daemon-url', value: config.daemonUrl }),
            ]),
            $el('div', {}, [
                $el('label', {}, 'API Token（服务器部署时填写）'),
                $el('input', { type: 'password', id: 'ttc-api-token', value: config.apiToken || '' }),
            ]),
            $el('label', {}, [
                $el('span', {}, '自动识别 JD/招聘页面'),
                $el('input', { type: 'checkbox', id: 'ttc-auto-send', checked: config.autoSend }),
            ]),
            $el('label', {}, [
                $el('span', {}, '调试日志'),
                $el('input', { type: 'checkbox', id: 'ttc-debug', checked: config.debug }),
            ]),
            $el('div', { class: 'row' }, [
                $el('button', { class: 'btn', onclick: () => { sendCurrentPage(); } }, '发送当前页'),
                $el('button', { class: 'btn secondary', onclick: saveSettings }, '保存设置'),
            ]),
        ]);
        document.body.appendChild(panel);

        fab.addEventListener('click', () => {
            panel.classList.toggle('show');
        });
    }

    function saveSettings() {
        config.daemonUrl = document.getElementById('ttc-daemon-url').value.trim() || DEFAULT_DAEMON_URL;
        config.apiToken = document.getElementById('ttc-api-token').value.trim();
        config.autoSend = document.getElementById('ttc-auto-send').checked;
        config.debug = document.getElementById('ttc-debug').checked;
        saveConfig(config);
        showToast('设置已保存');
        document.getElementById('ttc-feishu-panel').classList.remove('show');
    }

    // ------------------------------------------------------------------
    // 启动
    // ------------------------------------------------------------------
    function init() {
        if (window.__ttcFeishuBridgeLoaded) return;
        window.__ttcFeishuBridgeLoaded = true;

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', run);
        } else {
            run();
        }
    }

    function run() {
        buildUI();
        log('Loaded on', detectPageType(), location.href);

        // 注册油猴菜单命令
        if (typeof GM_registerMenuCommand !== 'undefined') {
            GM_registerMenuCommand('发送当前页到 TTC', () => sendCurrentPage());
            GM_registerMenuCommand('TTC 设置', () => {
                document.getElementById('ttc-feishu-panel').classList.toggle('show');
            });
        }

        // 自动发送：页面加载后若看起来像 JD/招聘且开启自动发送
        if (config.autoSend) {
            setTimeout(() => {
                const payload = buildPayload();
                if (looksLikeJD(payload.raw_text)) {
                    log('Auto-send triggered');
                    sendToDaemon(payload, true);
                }
            }, 3500);
        }
    }

    init();
})();
