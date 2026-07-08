import React, { useState } from 'react';
import {
  Card, Input, Button, Typography, message, Tabs, Space,
  Form, Divider,
} from 'antd';
import {
  UserOutlined, LockOutlined, TeamOutlined,
  SafetyOutlined, SendOutlined, KeyOutlined,
} from '@ant-design/icons';
import { api } from '../api';

const { Text, Title } = Typography;

const AUTH_TOKEN_KEY = 'talentmatch_auth_token';
const AUTH_USER_KEY = 'talentmatch_auth_user';

export function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getAuthUser() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_USER_KEY) || '{}');
  } catch { return {}; }
}

export function clearAuth() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
}

export function saveAuth(token, user) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
}

export default function Login({ onLoginSuccess }) {
  const [tab, setTab] = useState('login');
  const [loading, setLoading] = useState(false);
  const [pendingOpenId, setPendingOpenId] = useState('');

  const handleLogin = async (values) => {
    setLoading(true);
    try {
      const res = await api.login(values.username, values.password);
      if (!res || !res.token) {
        message.error(res?.detail || '登录失败');
        return;
      }
      saveAuth(res.token, res);
      message.success(`欢迎回来，${res.display_name || res.username}`);
      onLoginSuccess?.(res);
    } catch (e) {
      message.error(e.message || '登录失败，请检查用户名和密码');
    }
    setLoading(false);
  };

  const handleFeishuLogin = async (values) => {
    setLoading(true);
    try {
      const res = await api.request('/auth/feishu/verify-code', {
        method: 'POST',
        body: JSON.stringify({ code: values.code }),
      });
      if (res.status === 'new_user') {
        // 未绑定 — 切换到注册 tab 并预填 open_id
        message.info('飞书验证通过！请设置用户名和密码完成绑定');
        setTab('register');
        setPendingOpenId(res.open_id);
        return;
      }
      saveAuth(res.token, res);
      message.success(`飞书登录成功！欢迎 ${res.display_name}`);
      onLoginSuccess?.(res);
    } catch (e) {
      message.error(e.message || '验证失败，请检查验证码是否正确');
    }
    setLoading(false);
  };

  const handleRegister = async (values) => {
    if (values.password !== values.confirm) {
      message.error('两次密码不一致');
      return;
    }
    setLoading(true);
    try {
      let res;
      if (pendingOpenId) {
        // 飞书绑定注册
        res = await api.request('/auth/feishu/bind', {
          method: 'POST',
          body: JSON.stringify({
            username: values.username,
            password: values.password,
            open_id: pendingOpenId,
            display_name: values.display_name || values.username,
          }),
        });
        setPendingOpenId('');
      } else {
        res = await api.register(values.username, values.password, values.display_name || values.username);
      }
      if (!res || !res.token) {
        message.error(res?.detail || '注册失败');
        return;
      }
      saveAuth(res.token, res);
      message.success(`注册成功！欢迎 ${res.display_name}`);
      onLoginSuccess?.(res);
    } catch (e) {
      message.error(e.message || '注册失败，用户名可能已存在');
    }
    setLoading(false);
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: 20,
    }}>
      <Card
        style={{
          width: 420,
          maxWidth: '100%',
          borderRadius: 16,
          boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        }}
        bodyStyle={{ padding: '32px 28px' }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14,
            background: 'linear-gradient(135deg, #1677ff, #4096ff)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontWeight: 700, fontSize: 24, marginBottom: 12,
          }}>T</div>
          <Title level={4} style={{ margin: 0, fontWeight: 700 }}>
            TalentMatch
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>示范账号: zhongxiaomi / mia2026<br/>
            猎头人岗智能匹配系统
          </Text>
        </div>

        <Tabs
          activeKey={tab}
          onChange={setTab}
          centered
          items={[
            {
              key: 'login',
              label: <span><SendOutlined /> 登录</span>,
              children: (
                <Form onFinish={handleLogin} layout="vertical" size="large">
                  <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
                    <Input prefix={<UserOutlined />} placeholder="用户名" />
                  </Form.Item>
                  <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
                    <Input.Password prefix={<LockOutlined />} placeholder="密码" />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" htmlType="submit" block loading={loading}
                      style={{ borderRadius: 8, height: 44, fontSize: 15, fontWeight: 600 }}>
                      登 录
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'register',
              label: <span><TeamOutlined /> 注册</span>,
              children: (
                <Form onFinish={handleRegister} layout="vertical" size="large">
                  <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
                    <Input prefix={<UserOutlined />} placeholder="用户名（用于登录）" />
                  </Form.Item>
                  <Form.Item name="display_name">
                    <Input prefix={<SafetyOutlined />} placeholder="显示名称（选填）" />
                  </Form.Item>
                  <Form.Item name="password" rules={[{ required: true, min: 6, message: '密码至少6位' }]}>
                    <Input.Password prefix={<LockOutlined />} placeholder="密码" />
                  </Form.Item>
                  <Form.Item name="confirm" rules={[{ required: true, message: '请确认密码' }]}>
                    <Input.Password prefix={<LockOutlined />} placeholder="确认密码" />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" htmlType="submit" block loading={loading}
                      style={{ borderRadius: 8, height: 44, fontSize: 15, fontWeight: 600 }}>
                      注 册
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'feishu',
              label: <span><KeyOutlined /> 飞书</span>,
              children: (
                <div>
                  <div style={{ textAlign: 'center', padding: '20px 0 12px' }}>
                    <KeyOutlined style={{ fontSize: 40, color: '#1677ff', marginBottom: 12 }} />
                    <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>飞书验证码登录</div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      在飞书给 Bot 发送 <Text code style={{ fontSize: 11 }}>登录</Text> 获取验证码
                    </Text>
                  </div>
                  <Form onFinish={handleFeishuLogin} layout="vertical" size="large">
                    <Form.Item name="code" rules={[{ required: true, len: 4, message: '请输入4位验证码' }]}>
                      <Input prefix={<KeyOutlined />} placeholder="飞书 Bot 发送的4位验证码"
                        maxLength={4} style={{ textAlign: 'center', fontSize: 18, letterSpacing: 8 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" block loading={loading}
                        style={{ borderRadius: 8, height: 44, fontSize: 15, fontWeight: 600 }}>
                        验证并登录
                      </Button>
                    </Form.Item>
                  </Form>
                  <div style={{ textAlign: 'center', marginTop: 8 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      首次使用？验证后会自动引导注册绑定
                    </Text>
                  </div>
                </div>
              ),
            },
          ]}
        />

        <Divider style={{ margin: '16px 0 12px' }}>
          <Text type="secondary" style={{ fontSize: 11 }}>上海决胜人力资源有限公司</Text>
        </Divider>
      </Card>
    </div>
  );
}
