import React, { useState, useEffect } from 'react';
import {
  Card, List, Typography, Tag, Badge, Space, Button, Empty, Spin, message, Tooltip,
  Tabs, Avatar, Flex, Divider,
} from 'antd';
import {
  BellOutlined, CheckCircleOutlined, ThunderboltOutlined,
  TeamOutlined, SolutionOutlined, FileTextOutlined,
  DeleteOutlined, ReloadOutlined, MessageOutlined,
  InfoCircleOutlined, WarningOutlined,
} from '@ant-design/icons';
import { api } from '../api';

const { Text, Title } = Typography;

const typeConfig = {
  match: { color: '#722ed1', icon: <ThunderboltOutlined />, label: '匹配通知' },
  note: { color: '#1677ff', icon: <MessageOutlined />, label: '备注提醒' },
  system: { color: '#8c8c8c', icon: <InfoCircleOutlined />, label: '系统通知' },
  collab: { color: '#52c41a', icon: <TeamOutlined />, label: '协作提醒' },
};

export default function Messages({ navigate }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [unread, setUnread] = useState(0);
  const [filter, setFilter] = useState('all');

  const loadMessages = async () => {
    setLoading(true);
    try {
      const data = await api.request('/messages?limit=100');
      setMessages(data || []);
      const un = await api.request('/messages/unread');
      setUnread(un?.count || 0);
    } catch (e) {
      message.error('加载消息失败');
    }
    setLoading(false);
  };

  useEffect(() => { loadMessages(); }, []);

  const handleRead = async (id) => {
    try {
      await api.request(`/messages/${id}/read`, { method: 'PUT' });
      setMessages(prev => prev.map(m => m.id === id ? { ...m, is_read: 1 } : m));
      setUnread(prev => Math.max(0, prev - 1));
    } catch (e) {
      message.error('标记失败');
    }
  };

  const handleMarkAllRead = async () => {
    if (messages.length === 0) return;
    for (const m of messages.filter(m => !m.is_read)) {
      await api.request(`/messages/${m.id}/read`, { method: 'PUT' }).catch(() => {});
    }
    setMessages(prev => prev.map(m => ({ ...m, is_read: 1 })));
    setUnread(0);
    message.success('全部标记已读');
  };

  const handleJump = (item) => {
    if (item.related_type === 'candidate' && item.related_id) {
      navigate('candidates');
    } else if (item.related_type === 'job' && item.related_id) {
      navigate('jobs');
    } else if (item.related_type === 'match' && item.related_id) {
      navigate('match');
    }
  };

  const filtered = filter === 'all' 
    ? messages 
    : filter === 'unread' 
      ? messages.filter(m => !m.is_read)
      : messages.filter(m => m.message_type === filter);

  const typeColors = { match: 'purple', note: 'blue', system: 'default', collab: 'green' };

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      {/* Header */}
      <Card style={{ borderRadius: 10, marginBottom: 14 }} bodyStyle={{ padding: '16px 20px' }}>
        <Flex align="center" justify="space-between">
          <Space>
            <BellOutlined style={{ fontSize: 20, color: '#1677ff' }} />
            <Title level={4} style={{ margin: 0, fontWeight: 700 }}>消息通知</Title>
            {unread > 0 && <Badge count={unread} style={{ backgroundColor: '#ff4d4f' }} />}
          </Space>
          <Space>
            {unread > 0 && (
              <Button size="small" icon={<CheckCircleOutlined />} onClick={handleMarkAllRead}>
                全部已读
              </Button>
            )}
            <Button size="small" icon={<ReloadOutlined />} onClick={loadMessages}>
              刷新
            </Button>
          </Space>
        </Flex>
      </Card>

      {/* Filter Tabs */}
      <Card style={{ borderRadius: 10, marginBottom: 14 }} bodyStyle={{ padding: '8px 16px' }}>
        <Tabs
          activeKey={filter}
          onChange={setFilter}
          size="small"
          items={[
            { key: 'all', label: <span>全部 {messages.length > 0 && `(${messages.length})`}</span> },
            { key: 'unread', label: <span>未读 {unread > 0 && <Badge count={unread} size="small" />}</span> },
            { key: 'match', label: '匹配通知' },
            { key: 'system', label: '系统通知' },
            { key: 'note', label: '备注提醒' },
          ]}
        />
      </Card>

      {/* Message List */}
      <Card style={{ borderRadius: 10 }} bodyStyle={{ padding: 0 }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 60 }}><Spin /><div style={{ marginTop: 12, color: '#999' }}>加载中...</div></div>
        ) : filtered.length === 0 ? (
          <Empty description={filter === 'all' ? '暂无消息' : '该分类暂无消息'} style={{ padding: 60 }} />
        ) : (
          <List
            dataSource={filtered}
            renderItem={(item) => {
              const cfg = typeConfig[item.message_type] || typeConfig.system;
              const isUnread = !item.is_read;
              return (
                <List.Item
                  style={{
                    padding: '14px 20px',
                    cursor: 'pointer',
                    background: isUnread ? '#f6f8ff' : 'transparent',
                    borderLeft: isUnread ? '3px solid #1677ff' : '3px solid transparent',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = '#fafafa'}
                  onMouseLeave={e => e.currentTarget.style.background = isUnread ? '#f6f8ff' : 'transparent'}
                  onClick={() => {
                    if (isUnread) handleRead(item.id);
                    if (item.related_id) handleJump(item);
                  }}
                  actions={[
                    <Space key="actions" onClick={e => e.stopPropagation()}>
                      {item.related_id && (
                        <Button type="link" size="small" onClick={() => handleJump(item)}>
                          查看详情
                        </Button>
                      )}
                      {isUnread && (
                        <Tooltip title="标记已读">
                          <Button type="text" size="small" icon={<CheckCircleOutlined />}
                            onClick={() => handleRead(item.id)} />
                        </Tooltip>
                      )}
                    </Space>,
                  ]}
                >
                  <List.Item.Meta
                    avatar={
                      <Avatar size={36} style={{ background: cfg.color + '20', color: cfg.color }}>
                        {cfg.icon}
                      </Avatar>
                    }
                    title={
                      <Space>
                        <Text strong={isUnread} style={{ fontSize: 13 }}>{item.title}</Text>
                        <Tag color={typeColors[item.message_type] || 'default'} style={{ fontSize: 9, lineHeight: '16px' }}>
                          {cfg.label}
                        </Tag>
                        {isUnread && <Badge status="processing" color="#1677ff" />}
                      </Space>
                    }
                    description={
                      <div>
                        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 2 }}>
                          {item.content || '暂无详细内容'}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 10, color: '#bbb' }}>
                          {item.created_at ? new Date(item.created_at + 'Z').toLocaleString('zh-CN') : ''}
                        </Text>
                      </div>
                    }
                  />
                </List.Item>
              );
            }}
          />
        )}
      </Card>
    </div>
  );
}
