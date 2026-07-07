const API = 'http://127.0.0.1:8765/api/capture';
const LOCAL_IMPORT_API = 'http://127.0.0.1:8765/api/import-local-download';
const SUPPORTED = [
  'zhipin.com', 'liepin.com', 'maimai.cn',
  'linkedin.com', '51job.com', 'zhaopin.com'
];
let batchPromise = null;

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const getState = () => chrome.storage.local.get('batch').then(data => data.batch || {
  running: false, queue: [], total: 0, done: 0, errors: 0, current: '', message: '空闲'
});
const setState = state => chrome.storage.local.set({batch: state}).then(() => state);

function supportedHost(url) {
  try {
    const host = new URL(url).hostname;
    return SUPPORTED.some(domain => host === domain || host.endsWith('.' + domain));
  } catch {
    return false;
  }
}

function waitForTab(tabId, timeoutMs = 25000) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error('页面加载超时'));
    }, timeoutMs);
    function listener(id, info) {
      if (id === tabId && info.status === 'complete') {
        clearTimeout(timeout);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId).then(tab => {
      if (tab.status === 'complete') {
        clearTimeout(timeout);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    }).catch(() => {});
  });
}

async function readTab(tabId) {
  const results = await chrome.scripting.executeScript({
    target: {tabId},
    func: () => {
      const text = document.body ? document.body.innerText : '';
      const blockedWords = [
        '安全验证', '请输入验证码', '访问过于频繁', '操作过于频繁',
        '异常访问', '请完成验证', '登录后查看', '账号登录'
      ];

      // BOSS 在线简历结构化提取：按“个人优势/工作经历/项目经历/教育经历/技能专长”分节，
      // 减少导航栏、聊天按钮等噪声，提高后端解析准确率。
      function extractBossSections() {
        const headings = ['个人优势', '工作经历', '项目经历', '教育经历', '技能专长', '求职期望'];
        const allText = [];
        const sections = [];
        const addSection = (heading, lines) => {
          if (!heading || !lines.length) return;
          sections.push({heading, text: lines.join('\n')});
        };

        // 1. 顶部基础信息（姓名、年龄、城市、经验、学历、求职状态）
        const basic = [];
        const h1 = document.querySelector('h1');
        if (h1) basic.push(h1.innerText.trim());
        const infoEls = document.querySelectorAll(
          '.info-label, .base-info, .job-info, [class*="info"] .text, [class*="base"] .text, .name-box .label'
        );
        for (const el of infoEls) {
          const t = (el.innerText || '').trim();
          if (t && t.length <= 80 && !basic.includes(t)) basic.push(t);
        }
        // 兜底：把 body 前 500 字里包含年龄/岁/经验的短文本也抓进来
        const bodyStart = text.split('\n').slice(0, 60);
        for (const line of bodyStart) {
          const t = line.trim();
          if (/\d+岁/.test(t) || /\d+年经验/.test(t) || /本科|硕士|博士/.test(t)) {
            if (!basic.includes(t)) basic.push(t);
          }
        }
        if (basic.length) {
          sections.push({heading: '基础信息', text: basic.slice(0, 12).join('\n')});
        }

        // 2. 遍历 DOM 找分节标题，按下一个标题之前的文本聚合
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
        let currentHeading = '';
        let currentLines = [];
        const pushCurrent = () => {
          if (currentHeading && currentLines.length) {
            addSection(currentHeading, currentLines);
          }
          currentHeading = '';
          currentLines = [];
        };
        while (walker.nextNode()) {
          const el = walker.currentNode;
          if (!el.innerText) continue;
          const t = el.innerText.trim();
          if (!t || t.length > 3000) continue;
          // 识别节标题：文本精确匹配或靠近 icon 的短标题
          const isHeading = headings.includes(t) || headings.some(h => t.startsWith(h + ' '));
          if (isHeading && t.length <= 20) {
            pushCurrent();
            currentHeading = t.replace(/\s+/g, '');
            continue;
          }
          if (currentHeading) {
            // 过滤明显是 UI 控件的行
            if (/^(展开|收起|查看全部|更多|编辑|删除|举报|分享|收藏|投递|立即沟通|聊一聊|发简历)$/.test(t)) continue;
            if (t.length >= 8 && !currentLines.includes(t)) currentLines.push(t);
          }
        }
        pushCurrent();

        // 3. 如果没找到任何分节，回退到整页文本
        if (sections.length <= 1) return {sections: [{heading: '全文', text}]};
        return {sections};
      }

      const isBoss = /zhipin\.com/.test(location.hostname) && /geek|jobhunter|candidate|resume/i.test(location.href);
      const structured = isBoss ? extractBossSections() : null;

      return {
        url: location.href,
        title: document.title,
        heading: (document.querySelector('h1') && document.querySelector('h1').innerText) ||
          (document.querySelector('[class*=name]') && document.querySelector('[class*=name]').innerText) || '',
        text,
        structured_data: structured,
        captured_at: new Date().toISOString(),
        source_type: 'authorized_batch_browser',
        blocked: blockedWords.find(word => text.includes(word)) || ''
      };
    }
  });
  return results[0].result;
}

async function saveCapture(payload) {
  const response = await fetch(API, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || '本地入库失败');
  return data.candidate;
}

async function captureCurrent() {
  const tabs = await chrome.tabs.query({active: true, currentWindow: true});
  const tab = tabs[0];
  if (!tab || !tab.id || !/^https?:/.test(tab.url || '')) throw new Error('当前不是可收藏网页');
  // 手动收藏时拦截明显的 BOSS 后台/列表页，避免误入库
  if (/zhipin\.com/.test(new URL(tab.url).hostname)) {
    const managementPaths = /\/chat\/|\/manage\/|\/tools\/|\/prop\/|\/vip\/|\/data\/|\/job_list\/| ka=action/;
    if (managementPaths.test(tab.url)) {
      throw new Error('当前是 BOSS 后台或列表导航页，请打开单个候选人简历页再收藏');
    }
  }
  const payload = await readTab(tab.id);
  if (payload.blocked) throw new Error('页面要求人工处理：' + payload.blocked);
  if (!payload.text || payload.text.length < 10) throw new Error('当前页面没有足够可见文本');
  payload.source_type = 'authorized_visible_page';
  return saveCapture(payload);
}

async function autoScrollList(tabId, maxRounds = 6) {
  // 在 BOSS/猎聘/脉脉列表页自动向下滚动，触发懒加载更多候选人卡片。
  await chrome.scripting.executeScript({
    target: {tabId},
    args: [maxRounds],
    func: async max => {
      const sleep = ms => new Promise(r => setTimeout(r, ms));
      const getScrollable = () => {
        const candidates = [
          document.querySelector('.job-recommend-result'),
          document.querySelector('.recommend-list'),
          document.querySelector('[class*="search-list"]'),
          document.querySelector('[class*="candidate-list"]'),
          document.querySelector('main'),
          document.documentElement
        ];
        return candidates.find(el => el && el.scrollHeight > el.clientHeight) || document.documentElement;
      };
      const el = getScrollable();
      for (let i = 0; i < max; i++) {
        const before = el.scrollHeight;
        el.scrollTo({top: el.scrollHeight, behavior: 'smooth'});
        await sleep(1200);
        if (el.scrollHeight === before) break;
      }
      return {scrolled: true};
    }
  });
}

async function findCandidateLinks(tabId, limit) {
  // BOSS 列表页优先用 BOSS 特有的 geek/jobhunter 链接识别，识别不到再回退通用规则。
  const results = await chrome.scripting.executeScript({
    target: {tabId},
    args: [limit],
    func: maxItems => {
      const isBoss = /zhipin\.com/.test(location.hostname);
      const current = location.href.split('#')[0];
      const seen = new Map();

      const add = (url, label, score) => {
        if (!url || url.split('#')[0] === current) return;
        const clean = url.split('#')[0];
        const old = seen.get(clean);
        if (!old || score > old.score) seen.set(clean, {url: clean, label: label.slice(0, 80), score});
      };

      // BOSS 特有：geek/jobhunter 详情页，排除管理/聊天/工具等后台链接
      if (isBoss) {
        const bossNegative = /(\/chat\/|\/message\/|\/manage\/|\/tools\/|\/prop\/|\/vip\/|\/data\/|\/company\/|\/job_detail\/)/i;
        for (const a of document.querySelectorAll('a[href*="/geek/"], a[href*="/jobhunter/"]')) {
          const href = a.href ? a.href.split('#')[0] : '';
          if (!href || bossNegative.test(href)) continue;
          // 进一步要求链接路径里 geek/jobhunter 后面跟的是 id 或数字，不是 manage 等动作
          const pathMatch = href.match(/\/(geek|jobhunter)\/([^/]+)/);
          if (!pathMatch) continue;
          const segment = pathMatch[2];
          if (/^(manage|recommend|tools|prop|data|vip|setting|help)$/i.test(segment)) continue;
          const text = (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim();
          const card = a.closest('[class*="card"], [class*="item"], [class*="geek"], [class*="recommend"], li');
          const cardText = card ? (card.innerText || '').replace(/\s+/g, ' ').trim() : '';
          let score = 10;
          if (/\d+岁/.test(cardText || text)) score += 3;
          if (/\d+年/.test(cardText || text)) score += 3;
          if (/(本科|硕士|博士)/.test(cardText || text)) score += 2;
          add(href, text || cardText.slice(0, 60), score);
        }
      }

      // 通用回退
      const positive = /(geek|candidate|resume|talent|recommend|jobhunter|profile|user)/i;
      const negative = /(login|register|privacy|help|about|company|job\/detail|chat|message|setting|job_list)/i;
      const evidence = /(\d+\s*岁|\d+\s*年|本科|硕士|博士|咨询|战略|品牌|产品|渠道)/;
      for (const a of document.querySelectorAll('a[href]')) {
        if (isBoss && seen.has(a.href.split('#')[0])) continue;
        const href = a.href ? a.href.split('#')[0] : '';
        const text = (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim();
        if (!href || href === current || !href.startsWith(location.origin) || negative.test(href)) continue;
        let score = 0;
        if (positive.test(href)) score += 5;
        if (evidence.test(text)) score += 3;
        if (text.length >= 2 && text.length <= 160) score += 1;
        if (a.closest('[class*=candidate],[class*=resume],[class*=geek],[class*=talent],[class*=card],[class*=item]')) score += 3;
        if (score < 4) continue;
        add(href, text, score);
      }
      return Array.from(seen.values()).sort((a, b) => b.score - a.score).slice(0, maxItems);
    }
  });
  return results[0].result || [];
}

async function runBatch() {
  while (true) {
    let state = await getState();
    if (!state.running || !state.queue.length) {
      if (state.running) {
        state = Object.assign({}, state, {
          running: false,
          current: '',
          message: '完成，失败 ' + (state.errors || 0) + ' 条'
        });
        await setState(state);
      }
      return;
    }
    const item = state.queue[0];
    state = Object.assign({}, state, {current: item.label || item.url, message: '打开页面'});
    await setState(state);
    let tab;
    try {
      tab = await chrome.tabs.create({url: item.url, active: false});
      await waitForTab(tab.id);
      await sleep(2500);
      const payload = await readTab(tab.id);
      if (payload.blocked) {
        await chrome.tabs.update(tab.id, {active: true});
        await setState(Object.assign({}, state, {
          running: false,
          message: '已暂停，需要人工处理：' + payload.blocked
        }));
        return;
      }
      if (!payload.text || payload.text.length < 80) throw new Error('页面可见内容不足');
      const candidate = await saveCapture(payload);
      const latest = await getState();
      state = Object.assign({}, latest, {
        queue: latest.queue.slice(1),
        done: latest.done + 1,
        current: candidate.name,
        message: '已收藏 ' + candidate.name + '（' + candidate.score + '分）'
      });
      await setState(state);
      await chrome.tabs.remove(tab.id);
    } catch (error) {
      if (tab && tab.id) await chrome.tabs.remove(tab.id).catch(() => {});
      const latest = await getState();
      state = Object.assign({}, latest, {
        queue: latest.queue.slice(1),
        errors: (latest.errors || 0) + 1,
        current: item.label || item.url,
        message: '跳过：' + error.message
      });
      await setState(state);
    }
    const latest = await getState();
    if (!latest.running) return;
    const jitter = Math.floor(Math.random() * 4000);
    await sleep(latest.delaySeconds * 1000 + jitter);
  }
}

async function startBatch(limit, delaySeconds) {
  const old = await getState();
  if (old.running) throw new Error('已有批量任务正在运行');
  const tabs = await chrome.tabs.query({active: true, currentWindow: true});
  const tab = tabs[0];
  if (!tab || !tab.id || !supportedHost(tab.url || '')) {
    throw new Error('请先打开受支持招聘网站的候选人列表页');
  }
  const state1 = await setState({
    running: true,
    queue: [],
    total: 0,
    done: 0,
    errors: 0,
    current: '',
    message: '正在滚动加载候选人...',
    delaySeconds
  });
  await autoScrollList(tab.id, 6);
  const links = await findCandidateLinks(tab.id, limit);
  if (!links.length) {
    await setState(Object.assign({}, state1, {running: false, message: '当前页面未识别到候选人链接'}));
    throw new Error('当前页面未识别到候选人链接；请滚动让候选人卡片加载后重试');
  }
  const state = await setState({
    running: true,
    queue: links,
    total: links.length,
    done: 0,
    errors: 0,
    current: '',
    message: '已发现 ' + links.length + ' 个候选人',
    delaySeconds
  });
  batchPromise = runBatch().finally(() => { batchPromise = null; });
  return state;
}

async function testCandidateLinks(limit) {
  const tabs = await chrome.tabs.query({active: true, currentWindow: true});
  const tab = tabs[0];
  if (!tab || !tab.id || !supportedHost(tab.url || '')) {
    throw new Error('请先打开受支持招聘网站的候选人列表页');
  }
  const links = await findCandidateLinks(tab.id, limit);
  return links;
}

async function startGmailBatch(limit) {
  const tabs = await chrome.tabs.query({active: true, currentWindow: true});
  const tab = tabs[0];
  if (!tab || !tab.id || !/^https:\/\/mail\.google\.com\//.test(tab.url || '')) {
    throw new Error('请先在当前标签页打开并登录 Gmail');
  }
  await chrome.storage.local.set({
    gmailDownloadWindowUntil: Date.now() + 15 * 60 * 1000
  });
  const results = await chrome.scripting.executeScript({
    target: {tabId: tab.id},
    args: [Math.max(1, Math.min(10, limit))],
    func: async maxItems => {
      window.__TTC_GMAIL_STOP = false;
      const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
      const waitFor = async (test, timeout = 12000) => {
        const start = Date.now();
        while (Date.now() - start < timeout) {
          const value = test();
          if (value) return value;
          await sleep(300);
        }
        return null;
      };
      const keywords = /(简历|应聘|候选人|求职|resume|\bcv\b|curriculum)/i;
      const rowKey = row => row.getAttribute('data-legacy-thread-id') ||
        row.getAttribute('data-thread-id') || row.id || '';
      const rowSubject = row => {
        const subject = row.querySelector('.bog,.bqe,[data-thread-id] [role=link]');
        return (subject && subject.textContent || row.innerText || '').replace(/\s+/g, ' ').trim();
      };
      const initialRows = Array.from(document.querySelectorAll('tr.zA'));
      const targets = initialRows
        .map(row => ({key: rowKey(row), subject: rowSubject(row)}))
        .filter(item => keywords.test(item.subject))
        .slice(0, maxItems);
      if (!targets.length) {
        return {ok: false, message: '当前 Gmail 列表未找到包含简历关键词的邮件'};
      }
      let opened = 0;
      let downloads = 0;
      let noAttachment = 0;
      for (const target of targets) {
        if (window.__TTC_GMAIL_STOP) break;
        const rows = Array.from(document.querySelectorAll('tr.zA'));
        const row = rows.find(item => (target.key && rowKey(item) === target.key) ||
          rowSubject(item) === target.subject);
        if (!row) continue;
        row.click();
        const messageView = await waitFor(() => document.querySelector('.a3s,.adn'));
        if (!messageView) continue;
        opened += 1;
        await sleep(1200);
        const selectors = [
          '.aQH .aQw', '.aZo .aQw', '[download_url]',
          '[aria-label*="下载"]', '[aria-label*="Download"]',
          '[data-tooltip*="下载"]', '[data-tooltip*="Download"]'
        ];
        const buttons = Array.from(new Set(
          selectors.flatMap(selector => Array.from(document.querySelectorAll(selector)))
        )).filter(element => {
          const rect = element.getBoundingClientRect();
          const label = (element.getAttribute('aria-label') ||
            element.getAttribute('data-tooltip') || element.textContent || '').trim();
          return rect.width > 0 && rect.height > 0 &&
            !/(全部下载到云端硬盘|Save all to Drive)/i.test(label);
        }).slice(0, 12);
        if (!buttons.length) {
          noAttachment += 1;
        } else {
          for (const button of buttons) {
            button.click();
            downloads += 1;
            await sleep(800);
          }
        }
        await sleep(1200);
        const back = document.querySelector(
          '[aria-label*="返回收件箱"],[aria-label*="Back to Inbox"],' +
          '[data-tooltip*="返回收件箱"],[data-tooltip*="Back to Inbox"]'
        );
        if (back) back.click(); else history.back();
        await waitFor(() => document.querySelector('tr.zA'));
        await sleep(900);
      }
      return {
        ok: true,
        message: '已阅读 ' + opened + ' 封邮件，触发 ' + downloads +
          ' 个附件下载，无附件 ' + noAttachment + ' 封'
      };
    }
  });
  const result = results[0].result;
  if (!result || !result.ok) throw new Error((result && result.message) || 'Gmail 页面自动化失败');
  return result;
}

chrome.downloads.onChanged.addListener(async delta => {
  if (!delta.state || delta.state.current !== 'complete') return;
  const data = await chrome.storage.local.get('gmailDownloadWindowUntil');
  if (!data.gmailDownloadWindowUntil || Date.now() > data.gmailDownloadWindowUntil) return;
  const items = await chrome.downloads.search({id: delta.id});
  const item = items[0];
  if (!item || !/\.(pdf|doc|docx)$/i.test(item.filename || '')) return;
  try {
    await fetch(LOCAL_IMPORT_API, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        path: item.filename,
        source_url: item.referrer || item.finalUrl || 'https://mail.google.com/'
      })
    });
  } catch (_error) {
    // 本地服务状态会显示导入失败；不影响浏览器下载本身。
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    if (message.type === 'captureCurrent') {
      const candidate = await captureCurrent();
      return {ok: true, candidate};
    }
    if (message.type === 'startBatch') {
      const state = await startBatch(message.limit || 5, message.delaySeconds || 12);
      return {ok: true, state};
    }
    if (message.type === 'testLinks') {
      const links = await testCandidateLinks(message.limit || 5);
      return {ok: true, links};
    }
    if (message.type === 'startGmailBatch') {
      const result = await startGmailBatch(message.limit || 5);
      return {ok: true, message: result.message};
    }
    if (message.type === 'stopBatch') {
      const state = await getState();
      const gmailTabs = await chrome.tabs.query({url: 'https://mail.google.com/*'});
      for (const tab of gmailTabs) {
        if (!tab.id) continue;
        await chrome.scripting.executeScript({
          target: {tabId: tab.id},
          func: () => { window.__TTC_GMAIL_STOP = true; }
        }).catch(() => {});
      }
      return {ok: true, state: await setState(Object.assign({}, state, {
        running: false,
        message: '已请求停止'
      }))};
    }
    if (message.type === 'getStatus') return {ok: true, state: await getState()};
    return {ok: false, error: '未知操作'};
  })().then(sendResponse).catch(error => sendResponse({ok: false, error: error.message}));
  return true;
});
