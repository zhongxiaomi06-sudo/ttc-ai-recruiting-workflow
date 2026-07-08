import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import { initSentry, Sentry } from './monitoring/sentry';

initSentry();

// TalentMatch · 猎头智能匹配系统
// 基于 Ant Design v6 设计语言的企业级 UI
const theme = {
  token: {
    colorPrimary: '#1677ff',
    colorSuccess: '#52c41a',
    colorWarning: '#faad14',
    colorError: '#ff4d4f',
    colorInfo: '#1677ff',
    borderRadius: 6,
    fontSize: 13,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif",
    wireframe: false,
  },
  components: {
    Table: {
      headerBg: '#fafafa',
      headerColor: '#262626',
      rowHoverBg: '#e6f4ff',
      padding: 12,
      cellFontSize: 13,
    },
    Card: {
      paddingLG: 16,
    },
    Menu: {
      itemBg: 'transparent',
      subMenuItemBg: 'transparent',
      itemHeight: 42,
    },
    Layout: {
      headerBg: '#fff',
      bodyBg: '#f5f5f5',
    },
  },
};

ReactDOM.createRoot(document.getElementById('root')).render(
  <ConfigProvider locale={zhCN} theme={theme}>
    <Sentry.ErrorBoundary fallback={<div style={{ padding: 24 }}>页面加载异常，请刷新后重试。</div>}>
      <App />
    </Sentry.ErrorBoundary>
  </ConfigProvider>
);
