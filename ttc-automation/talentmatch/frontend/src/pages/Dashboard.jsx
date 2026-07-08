import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Statistic, Typography, Space, Tag, Button, Avatar, message, Alert, Spin,
} from 'antd';
import {
  TeamOutlined, SolutionOutlined, ThunderboltOutlined,
  CheckCircleOutlined, ReloadOutlined, FileTextOutlined,
  AimOutlined, ArrowUpOutlined,
} from '@ant-design/icons';
import { api } from '../api';


const { Text, Title } = Typography;

export default function Dashboard({ navigate }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);

  const loadStats = async () => {
    setLoading(true);
    try {
      const data = await api.getStats();
      setStats(data);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (e) {
      message.error(`加载统计数据失败: ${e.message || e}`);
    }
    setLoading(false);
  };

  useEffect(() => { loadStats(); }, []);

  const KpiCard = ({ title, value, icon, color, suffix = '', children, onClick }) => (
    <Card style={{ borderRadius: 10 }} hoverable bodyStyle={{ padding: '16px 20px', cursor: onClick ? 'pointer' : 'default' }}
      onClick={onClick}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Text type="secondary" style={{ fontSize: 11 }}>{title}</Text>
          <div style={{ fontSize: 26, fontWeight: 700, color: '#262626', marginTop: 4 }}>
            {value ?? '-'}{suffix && <Text style={{ fontSize: 14, color: '#8c8c8c', fontWeight: 400 }}> {suffix}</Text>}
          </div>
          {children}
        </div>
        <Avatar size={44} style={{ background: color + '18', color, fontSize: 20 }}>{icon}</Avatar>
      </Space>
    </Card>
  );

  return (
    <div>
      {/* 数据来源横幅 */}
      <Alert
        message={
          <Space>
            <AimOutlined />
            <span>系统展示 <Text strong>10,007</Text> 条公开招聘数据，来自新加坡 MyCareersFuture 真实职位</span>
            <Tag color="blue" style={{ fontSize: 10 }}>已验证</Tag>
          </Space>
        }
        type="info"
        showIcon={false}
        style={{ borderRadius: 8, marginBottom: 14, background: '#e6f4ff', border: '1px solid #91caff' }}
      />

      {/* 欢迎横幅 */}
      <Card style={{ borderRadius: 10, marginBottom: 14, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }} bodyStyle={{ padding: '20px 24px' }}>
        <Row align="middle" justify="space-between">
          <Col>
            <Title level={4} style={{ color: '#fff', margin: 0, fontWeight: 700 }}>
              猎头智能匹配系统
            </Title>
            <Space style={{ marginTop: 4 }}>
              <Text style={{ color: 'rgba(255,255,255,0.8)', fontSize: 12 }}>
                Hybrid Engine · 规则+ML混合评分 · 公开招聘数据
              </Text>
              <Tag color="green" style={{ fontSize: 9 }}>实时</Tag>
            </Space>
          </Col>
          <Col>
            <Space>
              <Button ghost size="small" icon={<ReloadOutlined />} onClick={loadStats} loading={loading}>刷新</Button>
              {lastRefresh && <Text style={{ color: 'rgba(255,255,255,0.6)', fontSize: 10 }}>{lastRefresh}</Text>}
            </Space>
          </Col>
        </Row>
      </Card>

      {/* KPI — 标注真实数据 */}
      <Row gutter={[12, 12]}>
        <Col xs={12} sm={12} md={6}>
          <KpiCard title="人才库" value={stats?.candidates?.toLocaleString() || 0} icon={<TeamOutlined />} color="#1677ff"
            onClick={() => navigate('candidates')}>
            <Tag color="blue" style={{ fontSize: 9, marginTop: 4 }}>公开招聘</Tag>
          </KpiCard>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <KpiCard title="活跃职位" value={stats?.active_jobs?.toLocaleString() || 0} icon={<SolutionOutlined />} color="#52c41a"
            onClick={() => navigate('jobs')}>
            <Tag color="green" style={{ fontSize: 9, marginTop: 4 }}>真实JD</Tag>
          </KpiCard>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <KpiCard title="历史匹配" value={stats?.matches || 0} icon={<ThunderboltOutlined />} color="#722ed1"
            onClick={() => navigate('match')}>
            <Tag color="purple" style={{ fontSize: 9, marginTop: 4 }}>ML评分</Tag>
          </KpiCard>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <KpiCard title="匹配反馈" value={stats?.feedback || 0} icon={<CheckCircleOutlined />} color="#faad14"
            onClick={() => navigate('stats')}>
            <Tag color="gold" style={{ fontSize: 9, marginTop: 4 }}>待收集</Tag>
          </KpiCard>
        </Col>
      </Row>

      {/* 快速操作 */}
      <Row gutter={12} style={{ marginTop: 14 }}>
        <Col xs={24} md={16}>
          <Card
            title={<Space>快速操作 <Tag color="blue" style={{ fontSize: 9 }}>真实数据</Tag></Space>}
            style={{ borderRadius: 10 }}
            bodyStyle={{ padding: '16px 20px' }}
          >
            <Row gutter={[10, 10]}>
              {[
                { key: 'batch', icon: <FileTextOutlined />, label: '批量导入简历', color: '#1677ff', desc: '上传公司内部真实简历 PDF' },
                { key: 'match', icon: <ThunderboltOutlined />, label: '智能匹配', color: '#722ed1', desc: '输入 JD → ML+规则混合评分' },
                { key: 'candidates', icon: <TeamOutlined />, label: '真实人才库', color: '#52c41a', desc: `${(stats?.candidates || 0).toLocaleString()} 条真实候选人` },
                { key: 'jobs', icon: <SolutionOutlined />, label: '真实职位库', color: '#faad14', desc: '19,158 个真实岗位描述' },
              ].map(item => (
                <Col xs={12} key={item.key}>
                  <Card hoverable size="small" style={{ borderRadius: 8, borderLeft: `3px solid ${item.color}` }}
                    onClick={() => navigate(item.key)} bodyStyle={{ padding: '10px 12px', cursor: 'pointer' }}>
                    <Space>
                      <Avatar size={28} style={{ background: item.color + '18', color: item.color, fontSize: 14 }}>{item.icon}</Avatar>
                      <div>
                        <Text strong style={{ fontSize: 12, display: 'block' }}>{item.label}</Text>
                        <Text type="secondary" style={{ fontSize: 10 }}>{item.desc}</Text>
                      </div>
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title={<Space>数据构成 <Tag color="blue" style={{ fontSize: 9 }}>明细</Tag></Space>} style={{ borderRadius: 10 }} bodyStyle={{ padding: '12px 16px' }}>
            <div style={{ marginBottom: 10 }}>
              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <Text style={{ fontSize: 11, cursor: 'pointer', color: '#1677ff' }} onClick={() => navigate('candidates')}>公开招聘候选人</Text>
                <Text strong style={{ fontSize: 12, color: '#1677ff' }}>10,007</Text>
              </Space>
            </div>
            <div style={{ marginBottom: 10 }}>
              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <Text style={{ fontSize: 11, cursor: 'pointer', color: '#52c41a' }} onClick={() => navigate('jobs')}>真实岗位描述</Text>
                <Text strong style={{ fontSize: 12, color: '#52c41a' }}>19,158</Text>
              </Space>
            </div>

          </Card>
        </Col>
      </Row>
    </div>
  );
}
