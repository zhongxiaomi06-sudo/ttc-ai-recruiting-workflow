import React, { useState, useEffect } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Tag, Typography, Space,
  Card, Row, Col, Statistic, message, Badge, Tooltip, Empty,
  Flex, Avatar, Divider, Spin, Drawer, Descriptions, List,
} from 'antd';
import {
  PlusOutlined, ThunderboltOutlined, SearchOutlined,
  TeamOutlined, CloseCircleOutlined, WarningOutlined,
  ReloadOutlined, FilterOutlined, BankOutlined,
  InfoCircleOutlined, EnvironmentOutlined, DollarOutlined,
} from '@ant-design/icons';
import { api } from '../api';
import { trackEvent } from '../hooks/useTracking';
import DataSourceTag from '../components/DataSourceTag';

const { Text } = Typography;
const { TextArea } = Input;

const statusOptions = [
  { value: 'active', label: '活跃中' },
  { value: 'closed', label: '已关闭' },
  { value: 'all', label: '全部职位' },
];

export default function Jobs({ navigate }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('active');
  const [searchText, setSearchText] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [modalOpen, setModalOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState(null);
  const [stats, setStats] = useState(null);
  const [form] = Form.useForm();

  const loadData = async (page = 1, size = 20) => {
    setLoading(true);
    try {
      // 并行加载 stats 和列表数据
      const [statsResult, listResult] = await Promise.all([
        stats ? Promise.resolve(stats) : api.request('/jobs/stats').catch(() => null),
        searchText.trim()
          ? api.request(`/jobs/search/${encodeURIComponent(searchText)}?limit=${size}`)
          : api.request(`/jobs?status=${status}&limit=${size}&offset=${(page-1) * size}`)
      ]);
      if (statsResult && !stats) {
        setStats(statsResult);
      }
      setData(listResult || []);
      if (statsResult) {
        const totalKey = status === 'all' ? 'total' : status;
        setPagination(p => ({ ...p, current: page, pageSize: size, total: statsResult[totalKey] || statsResult.total || 0 }));
      }
    } catch (e) {
      message.error(`加载失败: ${e.message || e}`);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadData(1, pagination.pageSize);
  }, [status]);

  // 搜索时回车触发
  const handleSearch = (value) => {
    setSearchText(value);
    setTimeout(() => loadData(1, pagination.pageSize), 0);
  };

  const doSearch = () => {
    loadData(1, pagination.pageSize);
  };

  const columns = [
    {
      title: '职位信息', dataIndex: 'title', key: 'title', width: 280,
      render: (v, r) => (
        <Flex vertical>
          <Text strong style={{ fontSize: 13 }}>{v || '未命名'}</Text>
          <Flex gap={4} align="center" style={{ marginTop: 2 }}>
            <BankOutlined style={{ fontSize: 10, color: '#8c8c8c' }} />
            <Text type="secondary" style={{ fontSize: 11 }}>{r.company || '-'}</Text>
          </Flex>
          {(() => {
            try {
              const skills = Array.isArray(r.required_skills) 
                ? r.required_skills 
                : JSON.parse(r.required_skills || '[]');
              if (!skills || skills.length === 0) return null;
              return (
                <Flex gap={2} wrap style={{ marginTop: 3 }}>
                  {skills.slice(0, 4).map(s => (
                    <Tag key={s} color="blue" style={{ fontSize: 9, lineHeight: '16px', padding: '0 4px' }}>{s}</Tag>
                  ))}
                </Flex>
              );
            } catch(e) { return null; }
          })()}
        </Flex>
      ),
    },
    {
      title: '薪资', dataIndex: 'salary_range', key: 'salary', width: 110,
      render: (v) => v && v !== '0-0' ? (
        <Text style={{ color: '#722ed1', fontWeight: 500, fontSize: 12 }}>{v}</Text>
      ) : <Text type="secondary" style={{ fontSize: 11 }}>-</Text>,
    },
    {
      title: '来源', dataIndex: 'source_url', key: 'source', width: 80,
      render: (v) => <DataSourceTag source={v ? 'web_crawler' : 'original'} />,
    },
    {
      title: '经验要求', dataIndex: 'min_years_experience', key: 'exp', width: 80, align: 'center',
      render: (v, r) => (
        <Text style={{ fontSize: 12 }}>
          {r.min_years_experience || 0}-{r.max_years_experience || 20}年
        </Text>
      ),
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80, align: 'center',
      render: (v) => v === 'active'
        ? <Badge status="success" text={<Text style={{ fontSize: 11 }}>活跃</Text>} />
        : <Badge status="default" text={<Text style={{ fontSize: 11 }}>关闭</Text>} />,
    },
    {
      title: '操作', key: 'action', width: 90, align: 'center',
      render: (_, r) => (
        <Tooltip title="智能匹配候选人">
          <Button type="primary" ghost size="small" icon={<ThunderboltOutlined />}
            onClick={() => { trackEvent('job', r.id, 'match_click'); navigate('match', { jobId: r.id }); }}
            style={{ borderRadius: 6 }}>
            匹配
          </Button>
        </Tooltip>
      ),
    },
  ];

  const handleCreate = async () => {
    trackEvent('job', 'new', 'create');
    try {
      const values = await form.validateFields();
      await api.createJob(values);
      message.success('职位创建成功');
      setModalOpen(false);
      form.resetFields();
      loadData();
    } catch (e) {
      if (e.message) message.error('创建失败');
    }
  };

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* Stats + Search */}
      <Row gutter={[14, 14]} style={{ marginBottom: 14 }}>
        <Col xs={24} md={8}>
          <Card size="small" style={{ borderRadius: 10, height: '100%' }} styles={{ body: { padding: '14px 16px' } }}>
            <Flex align="center" gap={12}>
              <Avatar size={40} icon={<TeamOutlined />} style={{ background: '#e6f4ff', color: '#1677ff' }} />
              <div>
                <Text type="secondary" style={{ fontSize: 10 }}>职位库总数</Text>
                <Text strong style={{ fontSize: 24, color: '#1677ff', display: 'block' }}>{stats?.total || '-'}</Text>
              </div>
            </Flex>
          </Card>
        </Col>
        <Col xs={12} md={8}>
          <Card size="small" style={{ borderRadius: 10, height: '100%' }} styles={{ body: { padding: '14px 16px' } }}>
            <Flex align="center" gap={12}>
              <Avatar size={40} icon={<WarningOutlined />} style={{ background: '#fff2f0', color: '#ff4d4f' }} />
              <div>
                <Text type="secondary" style={{ fontSize: 10 }}>公司数</Text>
                <Text strong style={{ fontSize: 24, color: '#ff4d4f', display: 'block' }}>
                  {stats ? new Set(data.map(j => j.company).filter(Boolean)).size : '-'}
                </Text>
              </div>
            </Flex>
          </Card>
        </Col>
        <Col xs={12} md={8}>
          <Card size="small" style={{ borderRadius: 10, height: '100%' }} styles={{ body: { padding: '14px 16px' } }}>
            <Flex align="center" gap={12}>
              <Input.Search
                placeholder="搜索职位/公司/技能…"
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                onSearch={handleSearch}
                enterButton
                style={{ width: '100%' }}
              />
            </Flex>
          </Card>
        </Col>
      </Row>

      {/* Toolbar */}
      <Card style={{ borderRadius: 10, marginBottom: 14 }} styles={{ body: { padding: '12px 16px' } }}>
        <Row justify="space-between" align="middle">
          <Flex gap={8} align="center">
            <Select value={status} onChange={setStatus} style={{ width: 110 }} size="small" options={statusOptions} />
            <Text type="secondary" style={{ fontSize: 11 }}>共 {pagination.total} 条</Text>
          </Flex>
          <Flex gap={8}>
            <Tooltip title="刷新">
              <Button size="small" icon={<ReloadOutlined />} onClick={() => loadData()} />
            </Tooltip>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)} style={{ borderRadius: 6 }}>
              新建职位
            </Button>
          </Flex>
        </Row>
      </Card>

      {/* Table */}
      <Card style={{ borderRadius: 10 }} styles={{ body: { padding: 0 } }}>
        <Table
          dataSource={data}
          columns={columns}
          rowKey={r => r.id}
          loading={loading}
          onRow={(record) => ({
            onClick: () => { setSelectedJob(record); setDetailOpen(true); },
            style: { cursor: 'pointer' },
          })}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50', '100'],
            showTotal: (t) => `共 ${t} 个职位`,
            onChange: (page, size) => loadData(page, size),
          }}
          size="middle"
          locale={{ emptyText: <Empty description="暂无职位数据" /> }}
          scroll={{ x: 700 }}
        />
      </Card>

      {/* Create modal */}
      <Modal title={<><PlusOutlined /> 新建职位</>} open={modalOpen}
        onCancel={() => setModalOpen(false)} onOk={handleCreate} okText="保存" width={560}>
        <Form form={form} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="title" label="职位名称" rules={[{ required: true }]}>
            <Input placeholder="eg. AI 算法工程师" style={{ borderRadius: 6 }} />
          </Form.Item>
          <Form.Item name="company" label="公司名称">
            <Input placeholder="eg. XX科技有限公司" style={{ borderRadius: 6 }} />
          </Form.Item>
          <Form.Item name="salary_range" label="薪资范围">
            <Input placeholder="eg. 40-70K·16薪" style={{ borderRadius: 6 }} />
          </Form.Item>
          <Form.Item name="description" label="职位描述">
            <TextArea rows={5} placeholder="职位描述、职责要求…" style={{ borderRadius: 6 }} />
          </Form.Item>
        </Form>

      {/* 职位详情 Drawer */}
      <Drawer
        title={selectedJob ? <><InfoCircleOutlined /> {selectedJob.title}</> : ''}
        placement="right"
        width={520}
        onClose={() => { setDetailOpen(false); setSelectedJob(null); }}
        open={detailOpen}
        extra={
          <Space>
            <Button type="primary" ghost size="small" icon={<ThunderboltOutlined />}
              onClick={() => { setDetailOpen(false); if(selectedJob) navigate('match', { jobId: selectedJob.id }); }}>
              匹配候选人
            </Button>
          </Space>
        }
      >
        {selectedJob && (
          <>
            <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label="公司" span={2}>
                <BankOutlined style={{ marginRight: 4 }} />{selectedJob.company || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="薪资" span={2}>
                <DollarOutlined style={{ marginRight: 4, color: '#722ed1' }} />
                <Text strong style={{ color: '#722ed1' }}>{selectedJob.salary_range || '-'}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="经验要求" span={2}>
                {selectedJob.min_years_experience || 0} - {selectedJob.max_years_experience || 20} 年
              </Descriptions.Item>
              <Descriptions.Item label="地点">{selectedJob.location || '-'}</Descriptions.Item>
              <Descriptions.Item label="状态">
                {selectedJob.status === 'active'
                  ? <Badge status="success" text="活跃中" />
                  : <Badge status="default" text="已关闭" />}
              </Descriptions.Item>
              <Descriptions.Item label="行业" span={2}>{selectedJob.industry || '-'}</Descriptions.Item>
              <Descriptions.Item label="学历要求" span={2}>{selectedJob.education || '-'}</Descriptions.Item>
            </Descriptions>

            <Divider orientation="left" style={{ fontSize: 12, color: '#8c8c8c' }}>职位描述</Divider>
            <div style={{ background: '#fafafa', borderRadius: 6, padding: 12, marginBottom: 16 }}>
              <Text style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{selectedJob.description || '暂无描述'}</Text>
            </div>

            {(() => {
              try {
                const skills = Array.isArray(selectedJob.required_skills)
                  ? selectedJob.required_skills
                  : JSON.parse(selectedJob.required_skills || '[]');
                if (!skills || skills.length === 0) return null;
                return (
                  <>
                    <Divider orientation="left" style={{ fontSize: 12, color: '#8c8c8c' }}>技能要求</Divider>
                    <Flex gap={4} wrap style={{ marginBottom: 16 }}>
                      {skills.map(s => <Tag key={s} color="blue">{s}</Tag>)}
                    </Flex>
                  </>
                );
              } catch(e) { return null; }
            })()}

            {(() => {
              try {
                const pref = Array.isArray(selectedJob.preferred_skills)
                  ? selectedJob.preferred_skills
                  : JSON.parse(selectedJob.preferred_skills || '[]');
                if (!pref || pref.length === 0) return null;
                return (
                  <>
                    <Divider orientation="left" style={{ fontSize: 12, color: '#8c8c8c' }}>优先技能</Divider>
                    <Flex gap={4} wrap style={{ marginBottom: 16 }}>
                      {pref.map(s => <Tag key={s} color="green">{s}</Tag>)}
                    </Flex>
                  </>
                );
              } catch(e) { return null; }
            })()}

            <Divider orientation="left" style={{ fontSize: 12, color: '#8c8c8c' }}>元信息</Divider>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="ID">{selectedJob.id}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{selectedJob.created_at}</Descriptions.Item>
              <Descriptions.Item label="来源">
                {selectedJob.source_url ? <Tag color="orange">爬取</Tag> : <Tag>手动创建</Tag>}
              </Descriptions.Item>
            </Descriptions>
          </>
        )}
      </Drawer>

      </Modal>
    </div>
  );
}
