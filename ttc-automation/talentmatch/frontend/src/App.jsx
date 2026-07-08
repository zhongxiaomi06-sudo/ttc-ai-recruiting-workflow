import React, { useState, useEffect } from 'react';
import { message, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import Login, { getAuthToken, getAuthUser, saveAuth, clearAuth } from './pages/Login';
import Dashboard from './pages/Dashboard';
import Candidates from './pages/Candidates';
import Jobs from './pages/Jobs';
import Match from './pages/Match';
import Messages from './pages/Messages';
import Batch from './pages/Batch';
import Stats from './pages/Stats';
import CandidateDetail from './pages/CandidateDetail';
import TTCWorkflow from './pages/TTCWorkflow';
import { api } from './api';
import { initTracking } from './hooks/useTracking';

const pages = {
  dashboard: Dashboard,
  candidates: Candidates,
  jobs: Jobs,
  match: Match,
  messages: Messages,
  batch: Batch,
  stats: Stats,
  candidateDetail: CandidateDetail,
  ttcWorkflow: TTCWorkflow,
};

export default function App() {
  const [page, setPage] = useState('dashboard');
  const [pageParams, setPageParams] = useState({});
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fatalError, setFatalError] = useState(null);

  useEffect(() => {
    // 全局错误捕获 — 防止白屏
    window.onerror = (msg, src, lineno, colno, err) => {
      console.error('Global error:', msg, src, lineno);
      setFatalError(err || String(msg));
      return true;
    };
    window.onunhandledrejection = (evt) => {
      console.error('Unhandled rejection:', evt.reason);
      setFatalError(evt.reason || String(evt));
      return true;
    };

    const token = getAuthToken();
    const savedUser = getAuthUser();
    if (token && savedUser?.username) {
      api.setAuthToken(token);
      setAuthenticated(true);
      setUser(savedUser);
      message.success(`欢迎回来，${savedUser.display_name || savedUser.username}`);
    }
    initTracking();
    setLoading(false);
    return () => {
      window.onerror = null;
      window.onunhandledrejection = null;
    };
  }, []);

  const handleLoginSuccess = (userData) => {
    api.setAuthToken(userData.token);
    setAuthenticated(true);
    setUser(userData);
  };

  const handleLogout = () => {
    clearAuth();
    setAuthenticated(false);
    setUser(null);
    message.info('已退出登录');
  };

  const handleNavigate = (key, params = {}) => {
    setPage(key);
    setPageParams(params);
  };

  // ── 致命错误保护 — 永远不会白屏 ──
  if (fatalError) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#f5f5f5' }}>
        <div style={{ textAlign: 'center', maxWidth: 400, padding: 40, background: '#fff', borderRadius: 10, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🛡️</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>系统暂时出现异常</div>
          <div style={{ fontSize: 13, color: '#8c8c8c', marginBottom: 24 }}>请刷新页面或稍后重试</div>
          <button
            onClick={() => { setFatalError(null); window.location.reload(); }}
            style={{ background: '#1677ff', color: '#fff', border: 'none', padding: '8px 24px', borderRadius: 6, cursor: 'pointer', fontSize: 14 }}
          >
            刷新页面
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#f5f5f5' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: 40, height: 40, border: '3px solid #1677ff', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 16px' }} />
          <div style={{ color: '#8c8c8c', fontSize: 13 }}>系统加载中...</div>
          <style>{'@keyframes spin { to { transform: rotate(360deg) } }'}</style>
        </div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <ErrorBoundary>
        <ConfigProvider locale={zhCN}>
          <Login onLoginSuccess={handleLoginSuccess} />
        </ConfigProvider>
      </ErrorBoundary>
    );
  }

  const PageComponent = pages[page];

  return (
    <ErrorBoundary>
      <ConfigProvider locale={zhCN}>
        <Layout currentPage={page} onNavigate={handleNavigate} user={user} onLogout={handleLogout}>
          {PageComponent ? (
            <PageComponent params={pageParams} navigate={handleNavigate} user={user} />
          ) : (
            <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>页面开发中</div>
          )}
        </Layout>
      </ConfigProvider>
    </ErrorBoundary>
  );
}
