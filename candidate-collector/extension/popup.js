const statusBox = document.getElementById('status');
const debugBox = document.getElementById('debug');
const batchButton = document.getElementById('batch');

function send(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, response => {
      if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError));
      if (!response || !response.ok) return reject(new Error((response && response.error) || '操作失败'));
      resolve(response);
    });
  });
}

function showState(state) {
  if (!state || (!state.running && !state.total)) {
    statusBox.textContent = (state && state.message) || '空闲';
    batchButton.disabled = false;
    return;
  }
  const prefix = state.running ? '自动阅读中' : '本批已结束';
  statusBox.textContent = prefix + '：' + (state.done || 0) + '/' + (state.total || 0) +
    (state.current ? ' · ' + state.current : '') +
    (state.message ? ' · ' + state.message : '');
  batchButton.disabled = Boolean(state.running);
}

document.getElementById('capture').addEventListener('click', async () => {
  statusBox.textContent = '正在读取当前页面...';
  debugBox.textContent = '';
  try {
    const response = await send({type: 'captureCurrent'});
    statusBox.textContent = '已收藏：' + response.candidate.name + '（' + response.candidate.score + '分）';
  } catch (error) {
    statusBox.textContent = '失败：' + error.message;
  }
});

document.getElementById('testLinks').addEventListener('click', async () => {
  statusBox.textContent = '正在识别当前列表的候选人链接...';
  debugBox.textContent = '';
  try {
    const limit = Math.max(1, Math.min(10, Number(document.getElementById('limit').value) || 5));
    const response = await send({type: 'testLinks', limit});
    statusBox.textContent = '识别到 ' + response.links.length + ' 个候选人链接';
    debugBox.textContent = response.links.map((l, i) => (i + 1) + '. ' + l.label + '\n' + l.url).join('\n\n');
  } catch (error) {
    statusBox.textContent = '识别失败：' + error.message;
  }
});

document.getElementById('batch').addEventListener('click', async () => {
  statusBox.textContent = '正在识别当前列表的候选人链接...';
  debugBox.textContent = '';
  try {
    const limit = Math.max(1, Math.min(10, Number(document.getElementById('limit').value) || 5));
    const delaySeconds = Math.max(8, Math.min(30, Number(document.getElementById('delay').value) || 12));
    const response = await send({type: 'startBatch', limit, delaySeconds});
    showState(response.state);
  } catch (error) {
    statusBox.textContent = '无法启动：' + error.message;
  }
});

document.getElementById('gmail').addEventListener('click', async () => {
  statusBox.textContent = '正在识别 Gmail 当前列表中的简历邮件...';
  debugBox.textContent = '';
  try {
    const limit = Math.max(1, Math.min(10, Number(document.getElementById('limit').value) || 5));
    const response = await send({type: 'startGmailBatch', limit});
    statusBox.textContent = response.message;
  } catch (error) {
    statusBox.textContent = 'Gmail 自动阅读失败：' + error.message;
  }
});

document.getElementById('stop').addEventListener('click', async () => {
  try {
    const response = await send({type: 'stopBatch'});
    showState(response.state);
  } catch (error) {
    statusBox.textContent = '停止失败：' + error.message;
  }
});

async function refresh() {
  try {
    const response = await send({type: 'getStatus'});
    showState(response.state);
  } catch (error) {
    statusBox.textContent = '状态读取失败：' + error.message;
  }
}

refresh();
setInterval(refresh, 1200);
