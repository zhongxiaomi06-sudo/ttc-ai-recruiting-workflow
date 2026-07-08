import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert, Avatar, Badge, Button, Card, Col, Descriptions, Drawer, Flex, Form,
  Input, List, Modal, Row, Select, Space, Statistic, Table, Tag, Typography,
  message,
} from 'antd';
import {
  ApartmentOutlined, CheckCircleOutlined, ClockCircleOutlined, FileTextOutlined,
  LinkOutlined, PhoneOutlined, ReloadOutlined, ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { api } from '../api';

const { Text, Title, Paragraph } = Typography;
const { TextArea } = Input;

function parseMaybeJson(value, fallback = {}) {
  if (!value) return fallback;
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function stateColor(state) {
  const map = {
    created: 'blue',
    jd_parsed: 'cyan',
    sourcing: 'gold',
    scored: 'purple',
    human_pending: 'orange',
    problem_pending: 'red',
    feedback: 'green',
    closed: 'default',
  };
  return map[state] || 'default';
}

function taskColor(type) {
  if (type === 'call') return 'blue';
  if (['jd_clarify', 'source_help', 'runtime_error', 'read_failed'].includes(type)) return 'red';
  return 'gold';
}

export default function TTCWorkflow() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null);
  const [missions, setMissions] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [calls, setCalls] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [taskDrawerOpen, setTaskDrawerOpen] = useState(false);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [token, setToken] = useState(localStorage.getItem('ttc_workflow_token') || '');
  const [form] = Form.useForm();
  const [completeForm] = Form.useForm();

  const loadData = async () => {
    setLoading(true);
    try {
      const [healthData, missionData, taskData, callData] = await Promise.all([
        api.ttcHealth().catch((e) => ({ ok: false, error: e.message || 'TTC 子系统不可用' })),
        api.ttcMissions(100).catch(() => ({ items: [] })),
        api.ttcHumanTasks('', 100).catch(() => ({ items: [] })),
        api.ttcCallList('', 100).catch(() => ({ items: [] })),
      ]);
      setHealth(healthData);
      setMissions(missionData.items || []);
      setTasks(taskData.items || []);
      setCalls(callData.items || []);
    } catch (e) {
      message.error(`加载 AI 工作流失败: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const activeMissions = useMemo(
    () => missions.filter((m) => !['closed'].includes(m.state)).length,
    [missions],
  );
  const pendingTasks = useMemo(
    () => tasks.filter((t) => ['pending', 'notified', 'opened'].includes(t.status)).length,
    [tasks],
  );
  const problemTasks = useMemo(
    () => tasks.filter((t) => t.task_type !== 'call' && ['pending', 'notified', 'opened'].includes(t.status)).length,
    [tasks],
  );

  const saveToken = () => {
    localStorage.setItem('ttc_workflow_token', token.trim());
    message.success('TTC API Token 已保存');
  };

  const ensureToken = () => {
    const saved = (localStorage.getItem('ttc_workflow_token') || token || '').trim();
    if (!saved) {
      message.warning('请先在右上角输入并保存 TTC API Token，再执行提交操作');
      return false;
    }
    return true;
  };

  const showSubmitError = (e) => {
    const msg = e?.message || String(e);
    if (e?.status === 401 || msg.includes('TTC API token')) {
      message.error('TTC API Token 缺失或错误，请重新保存后再提交');
      return;
    }
    message.error(`提交失败: ${msg}`);
  };

  const openTask = (task) => {
    setSelectedTask(task);
    setTaskDrawerOpen(true);
    completeForm.resetFields();
  };

  const submitTask = async () => {
    if (!selectedTask) return;
    if (!ensureToken()) return;
    try {
      const values = await completeForm.validateFields();
      await api.ttcCompleteTask(selectedTask.id, values);
      message.success('任务反馈已提交');
      setTaskDrawerOpen(false);
      setSelectedTask(null);
      loadData();
    } catch (e) {
      showSubmitError(e);
    }
  };

  const submitIngest = async () => {
    if (!ensureToken()) return;
    try {
      const values = await form.validateFields();
      if (values.input_type === 'url') {
        await api.ttcReadLink(values.source_url);
      } else {
        await api.ttcIngestJD({
          source_type: 'manual_jd',
          source_url: values.source_url || 'manual://talentmatch-workflow',
          title: values.title || '手工 JD',
          raw_text: values.raw_text,
        });
      }
      message.success('已提交到 TTC read_jobs');
      setIngestOpen(false);
      form.resetFields();
      loadData();
    } catch (e) {
      showSubmitError(e);
    }
  };

  const missionColumns = [
    {
      title: 'Mission',
      dataIndex: 'id',
      width: 190,
      render: (id, row) => {
        const jd = parseMaybeJson(row.jd_fields, row.jd_fields || {});
        return (
          <Flex vertical>
            <Text strong style={{ fontSize: 12 }}>{id}</Text>
            <Text type="secondary" style={{ fontSize: 11 }}>{jd.position || jd.title || '未命名 JD'}</Text>
          </Flex>
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'state',
      width: 120,
      render: (state) => <Tag color={stateColor(state)}>{state}</Tag>,
    },
    {
      title: '候选人',
      dataIndex: 'candidate_ids',
      width: 90,
      render: (ids) => (Array.isArray(ids) ? ids.length : parseMaybeJson(ids, []).length),
    },
    {
      title: '电话任务',
      dataIndex: 'call_list_ids',
      width: 90,
      render: (ids) => (Array.isArray(ids) ? ids.length : parseMaybeJson(ids, []).length),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      render: (v) => <Text type="secondary" style={{ fontSize: 11 }}>{v || '-'}</Text>,
    },
  ];

  const taskColumns = [
    {
      title: '任务',
      dataIndex: 'id',
      width: 180,
      render: (id, row) => (
        <Flex vertical>
          <Text strong style={{ fontSize: 12 }}>{id}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>{row.mission_id || '-'}</Text>
        </Flex>
      ),
    },
    {
      title: '类型',
      dataIndex: 'task_type',
      width: 120,
      render: (type) => <Tag color={taskColor(type)}>{type}</Tag>,
    },
    {
      title: '角色',
      dataIndex: 'role',
      width: 120,
      render: (role) => <Text style={{ fontSize: 12 }}>{role || '-'}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status) => <Badge status={status === 'completed' ? 'success' : 'processing'} text={status} />,
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_, row) => (
        <Button size="small" type="primary" ghost onClick={() => openTask(row)}>
          处理
        </Button>
      ),
    },
  ];

  const taskPayload = parseMaybeJson(selectedTask?.payload, {});

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      <Alert
        type={health?.ok ? 'success' : 'warning'}
        showIcon
        style={{ borderRadius: 8, marginBottom: 14 }}
        message={
          <Space>
            <ApartmentOutlined />
            <span>方案四 AI 工作流子系统</span>
            <Tag color={health?.ok ? 'green' : 'gold'}>{health?.ok ? '已连接' : '待连接'}</Tag>
            <Text type="secondary" style={{ fontSize: 12 }}>/api/ttc/*</Text>
          </Space>
        }
      />

      <Card style={{ borderRadius: 10, marginBottom: 14, background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)' }} bodyStyle={{ padding: '20px 24px' }}>
        <Row justify="space-between" align="middle" gutter={[16, 16]}>
          <Col>
            <Title level={4} style={{ color: '#fff', margin: 0 }}>AI 猎头工作流</Title>
            <Text style={{ color: 'rgba(255,255,255,0.82)', fontSize: 12 }}>
              read_jobs → artifact → Mission → phone task → feedback
            </Text>
          </Col>
          <Col>
            <Space>
              <Input.Password
                placeholder="TTC API Token"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                style={{ width: 220 }}
              />
              <Button ghost onClick={saveToken}>保存 Token</Button>
              <Button ghost icon={<ReloadOutlined />} loading={loading} onClick={loadData}>刷新</Button>
              <Button type="default" icon={<FileTextOutlined />} onClick={() => setIngestOpen(true)}>提交 JD</Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Row gutter={[12, 12]} style={{ marginBottom: 14 }}>
        <Col xs={12} md={6}>
          <Card style={{ borderRadius: 10 }}>
            <Statistic title="Mission 总数" value={missions.length} prefix={<ThunderboltOutlined />} valueStyle={{ color: '#1677ff' }} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card style={{ borderRadius: 10 }}>
            <Statistic title="进行中" value={activeMissions} prefix={<ClockCircleOutlined />} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card style={{ borderRadius: 10 }}>
            <Statistic title="待办任务" value={pendingTasks} prefix={<PhoneOutlined />} valueStyle={{ color: '#722ed1' }} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card style={{ borderRadius: 10 }}>
            <Statistic title="异常任务" value={problemTasks} prefix={<WarningOutlined />} valueStyle={{ color: '#ff4d4f' }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[14, 14]}>
        <Col xs={24} lg={15}>
          <Card title="Mission 状态机" style={{ borderRadius: 10 }} bodyStyle={{ padding: 0 }}>
            <Table
              rowKey="id"
              loading={loading}
              columns={missionColumns}
              dataSource={missions}
              size="small"
              pagination={{ pageSize: 8 }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={9}>
          <Card title="电话清单 Top 5" style={{ borderRadius: 10 }} bodyStyle={{ padding: '8px 16px' }}>
            <List
              dataSource={calls.slice(0, 5)}
              locale={{ emptyText: '暂无电话清单' }}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<Avatar style={{ background: '#e6f4ff', color: '#1677ff' }}>{item.priority || item.overall_score || '-'}</Avatar>}
                    title={<Text strong style={{ fontSize: 12 }}>{item.candidate_name || item.name || item.candidate_id || '候选人'}</Text>}
                    description={<Text type="secondary" style={{ fontSize: 11 }}>{item.status || 'pending'}</Text>}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Human Task 队列" style={{ borderRadius: 10, marginTop: 14 }} bodyStyle={{ padding: 0 }}>
        <Table
          rowKey="id"
          loading={loading}
          columns={taskColumns}
          dataSource={tasks}
          size="small"
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Drawer
        title="处理 Human Task"
        open={taskDrawerOpen}
        width={520}
        onClose={() => setTaskDrawerOpen(false)}
        extra={<Button type="primary" icon={<CheckCircleOutlined />} onClick={submitTask}>提交</Button>}
      >
        {selectedTask && (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="任务 ID">{selectedTask.id}</Descriptions.Item>
              <Descriptions.Item label="类型"><Tag color={taskColor(selectedTask.task_type)}>{selectedTask.task_type}</Tag></Descriptions.Item>
              <Descriptions.Item label="Mission">{selectedTask.mission_id || '-'}</Descriptions.Item>
              <Descriptions.Item label="问题">{taskPayload.problem || '-'}</Descriptions.Item>
            </Descriptions>
            <Card size="small" title="上下文" style={{ borderRadius: 8 }}>
              <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 12, maxHeight: 220, overflow: 'auto' }}>
                {JSON.stringify(taskPayload, null, 2)}
              </Paragraph>
            </Card>
            <Form layout="vertical" form={completeForm}>
              <Form.Item name="outcome" label="处理结果" rules={[{ required: true, message: '请选择处理结果' }]}>
                <Select
                  options={[
                    { value: 'interested', label: '电话：有意向' },
                    { value: 'not_interested', label: '电话：无兴趣' },
                    { value: 'no_answer', label: '电话：未接通' },
                    { value: 'wrong_info', label: '电话：信息有误' },
                    { value: 'resolved', label: '异常：已解决' },
                    { value: 'cannot_resolve', label: '异常：无法解决' },
                  ]}
                />
              </Form.Item>
              <Form.Item name="notes" label="备注">
                <TextArea rows={4} placeholder="记录通话反馈、人工补充信息、恢复动作说明等" />
              </Form.Item>
            </Form>
          </Space>
        )}
      </Drawer>

      <Modal
        title="提交 JD / URL 到 AI 工作流"
        open={ingestOpen}
        onCancel={() => setIngestOpen(false)}
        onOk={submitIngest}
        okText="提交"
      >
        <Form layout="vertical" form={form} initialValues={{ input_type: 'jd' }}>
          <Form.Item name="input_type" label="输入类型">
            <Select options={[
              { value: 'jd', label: '粘贴 JD 文本' },
              { value: 'url', label: '读取 URL / ChatGPT 分享页' },
            ]} />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.input_type !== cur.input_type}>
            {({ getFieldValue }) => getFieldValue('input_type') === 'url' ? (
              <Form.Item name="source_url" label="URL" rules={[{ required: true, message: '请输入 URL' }]}>
                <Input prefix={<LinkOutlined />} placeholder="https://..." />
              </Form.Item>
            ) : (
              <>
                <Form.Item name="title" label="标题">
                  <Input placeholder="例如：AI 产品经理 JD" />
                </Form.Item>
                <Form.Item name="source_url" label="来源 URL">
                  <Input placeholder="可选，飞书文档或客户来源链接" />
                </Form.Item>
                <Form.Item name="raw_text" label="JD 正文" rules={[{ required: true, message: '请粘贴 JD 正文' }]}>
                  <TextArea rows={7} placeholder="岗位职责、任职要求、地点、薪资等" />
                </Form.Item>
              </>
            )}
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
