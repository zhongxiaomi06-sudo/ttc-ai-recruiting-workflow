import React from 'react';
import { Button, Card, Result } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('TalentMatch ErrorBoundary:', error, info);
    try {
      fetch('/api/tracking/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity_type: 'system',
          entity_id: 'frontend',
          event_type: 'crash',
          detail: { error: String(error).slice(0, 500), stack: info?.componentStack?.slice(0, 500) || '' },
        }),
      }).catch(() => {});
    } catch {}
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: '#f5f5f5', padding: 24 }}>
          <Card style={{ maxWidth: 480, borderRadius: 10, textAlign: 'center' }}>
            <Result
              status="error"
              title="页面出现异常"
              subTitle={this.state.error?.message || '请尝试刷新页面'}
              extra={[
                <Button
                  key="reload"
                  type="primary"
                  icon={<ReloadOutlined />}
                  onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
                >
                  刷新页面
                </Button>,
                <Button key="home" onClick={() => window.location.href = '/dashboard'}>
                  返回首页
                </Button>,
              ]}
            />
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}
