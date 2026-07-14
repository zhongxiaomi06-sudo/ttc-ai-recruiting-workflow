const statusBox = document.getElementById('status');
const lastBox = document.getElementById('last');

function send(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, response => {
      if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
      resolve(response || {ok: false, error: '无响应'});
    });
  });
}

async function refresh() {
  try {
    const response = await send({type: 'getStatus'});
    const state = response.state || {};
    statusBox.textContent = state.message || '空闲';
    if (state.current) {
      lastBox.innerHTML = '<span class="ok">最近处理：</span>' + state.current;
    }
  } catch (error) {
    statusBox.textContent = '状态读取失败：' + error.message;
  }
}

send({type: 'ping'})
  .then(() => refresh())
  .catch(error => {
    statusBox.textContent = '后台未启动：' + error.message;
  });

setInterval(refresh, 1500);
