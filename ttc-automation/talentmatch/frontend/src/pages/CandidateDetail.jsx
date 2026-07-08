import React, { useState, useEffect } from 'react';
import {
  Row, Col, Card, Tag, Typography, Space, Spin, Empty, Button,
  Descriptions, Divider, Timeline, Input, message, Progress,
} from 'antd';
import {
  ArrowLeftOutlined, UserOutlined, BankOutlined,
  BookOutlined, ToolOutlined, ThunderboltOutlined,
  EnvironmentOutlined, CalendarOutlined, TrophyOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { api } from '../api';

const { Text } = Typography;

const PRESET_TAGS = ['2C产品', '2B产品', 'Agent', 'AIGC', '大模型', '传统AI'];

export default function CandidateDetail({ params, navigate }) {
  const [candidate, setCandidate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newTag, setNewTag] = useState('');

  const id = params?.id;

  useEffect(() => {
    if (id) {
      api.getCandidate(id).then(d => {
        setCandidate(d);
        setLoading(false);
      }).catch(() => {
        message.error('加载候选人失败');
        setLoading(false);
      });
    } else {
      setLoading(false);
    }
  }, [id]);

  const parseJsonField = (val) => {
    if (!val) return [];
    if (Array.isArray(val)) return val;
    try { return JSON.parse(val); } catch { return []; }
  };

  const currentTags = parseJsonField(candidate?.industry_tags);

  const addTag = async (tag) => {
    if (!tag || !candidate) return;
    const newTags = [...new Set([...currentTags, tag])];
    try {
      await api.updateCandidate(candidate.id, { industry_tags: JSON.stringify(newTags) });
      setCandidate({ ...candidate, industry_tags: JSON.stringify(newTags) });
      message.success('标签已更新');
    } catch { message.error('更新失败'); }
  };

  const removeTag = async (tag) => {
    if (!candidate) return;
    const newTags = currentTags.filter(t => t !== tag);
    try {
      await api.updateCandidate(candidate.id, { industry_tags: JSON.stringify(newTags) });
      setCandidate({ ...candidate, industry_tags: JSON.stringify(newTags) });
    } catch { message.error('更新失败'); }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;
  if (!candidate) return <Empty description="候选人不存在" />;

  const skills = parseJsonField(candidate.skills);
  const education = parseJsonField(candidate.education);
  const workExp = parseJsonField(candidate.work_experience);
  const highlights = parseJsonField(candidate.highlights);
  const ats = candidate.ats_score || 0;

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => navigate('candidates')}
        style={{ padding: 0, marginBottom: 12, fontSize: 13 }}>返回人才库</Button>

      {/* Basic info card */}
      <Card style={{ borderRadius: 10, marginBottom: 12 }}>
        <Row gutter={[16, 16]} align="middle">
          <Col>
            <div style={{
              width: 56, height: 56, borderRadius: '50%',
              background: '#e6f4ff', display: 'flex', alignItems: 'center',
              justifyContent: 'center', fontSize: 22, fontWeight: 700, color: '#1677ff',
            }}>{(candidate.name || '?')[0]}</div>
          </Col>
          <Col flex="auto">
            <Space align="center" style={{ marginBottom: 2 }}>
              <span style={{ fontSize: 18, fontWeight: 700 }}>{candidate.name}</span>
              {candidate.role_type && <Tag color="blue" style={{ fontSize: 10 }}>{candidate.role_type}</Tag>}
            </Space>
            <div>
              <Text type="secondary">{candidate.current_role || ''}</Text>
              {candidate.current_company && <Text type="secondary"> @ {candidate.current_company}</Text>}
            </div>
          </Col>
          <Col>
            <Progress type="circle" percent={Math.round(ats)} size={60}
              strokeColor={ats >= 80 ? '#52c41a' : ats >= 60 ? '#1677ff' : ats >= 40 ? '#faad14' : '#ff4d4f'}
              format={p => <span style={{ fontSize: 12, fontWeight: 700 }}>{p}</span>} />
          </Col>
        </Row>
      </Card>

      <Row gutter={[12, 12]}>
        <Col xs={24} md={14}>
          <Card size="small" style={{ borderRadius: 8, marginBottom: 12 }} bodyStyle={{ padding: '12px 16px' }}>
            <Descriptions column={2} size="small">
              <Descriptions.Item label={<><TrophyOutlined /> 工作经验</>}>{candidate.years_experience || 0}年</Descriptions.Item>
              <Descriptions.Item label={<><BankOutlined /> 公司</>} span={2}>{candidate.current_company || '-'}</Descriptions.Item>
              <Descriptions.Item label="岗位" span={2}>{candidate.current_role || '-'}</Descriptions.Item>
              <Descriptions.Item label={<><EnvironmentOutlined /> 地点</>}>{candidate.location || '-'}</Descriptions.Item>
              <Descriptions.Item label="上传人">{candidate.owner_id || '-'}</Descriptions.Item>
              <Descriptions.Item label="来源">{candidate.source || 'web'}</Descriptions.Item>
              <Descriptions.Item label="邮箱" span={2}>{candidate.email || '-'}</Descriptions.Item>
              <Descriptions.Item label="电话">{candidate.phone || '-'}</Descriptions.Item>
              <Descriptions.Item label="薪资期望">{candidate.salary_expected || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>

          {workExp.length > 0 && (
            <Card size="small" title={<Space><BankOutlined />工作经历</Space>}
              style={{ borderRadius: 8, marginBottom: 12 }} bodyStyle={{ padding: '8px 16px' }}>
              <Timeline items={workExp.map((w, i) => ({
                children: (
                  <div key={i}>
                    <Text strong style={{ fontSize: 12 }}>{w.company || w.position || '?'}</Text>
                    <div><Text style={{ fontSize: 11 }}>{w.position || ''}</Text></div>
                    <Text type="secondary" style={{ fontSize: 10 }}>
                      {w.start_date || ''} - {w.end_date || '至今'} {w.duration ? `(${w.duration})` : ''}
                    </Text>
                    {w.description && <div><Text style={{ fontSize: 11 }}>{w.description}</Text></div>}
                  </div>
                ),
              }))} />
            </Card>
          )}
        </Col>

        <Col xs={24} md={10}>
          <Card size="small" title={<Space><ToolOutlined />技能</Space>}
            style={{ borderRadius: 8, marginBottom: 12 }} bodyStyle={{ padding: '10px 14px' }}>
            {skills.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {skills.map((s, i) => (
                  <Tag key={i} style={{ fontSize: 11, borderRadius: 4, padding: '1px 8px' }}>{s}</Tag>
                ))}
              </div>
            ) : <Text type="secondary">暂无技能数据</Text>}
          </Card>

          <Card size="small" title={<Space><BookOutlined />教育背景</Space>}
            style={{ borderRadius: 8, marginBottom: 12 }} bodyStyle={{ padding: '10px 14px' }}>
            {education.length > 0 ? (
              <Timeline items={education.map((e, i) => ({
                children: <Text key={i} style={{ fontSize: 12 }}>{typeof e === 'string' ? e : `${e.school || ''} ${e.degree || ''} ${e.major || ''}`}</Text>,
              }))} />
            ) : <Text type="secondary">暂无教育背景</Text>}
          </Card>

          {candidate.summary && (
            <Card size="small" title={<Space><ThunderboltOutlined />AI 画像摘要</Space>}
              style={{ borderRadius: 8, marginBottom: 12 }} bodyStyle={{ padding: '10px 14px' }}>
              <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{candidate.summary}</Text>
              {highlights.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text strong style={{ fontSize: 11 }}>亮点</Text>
                  {highlights.map((h, i) => (
                    <div key={i}><Text style={{ fontSize: 11, color: '#52c41a' }}>▲ {typeof h === 'string' ? h : h.text || ''}</Text></div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* P1.10: Tag selector */}
          <Card size="small" title="标注标签" style={{ borderRadius: 8 }} bodyStyle={{ padding: '10px 14px' }}>
            <Space wrap style={{ marginBottom: 8 }}>
              {currentTags.map((tag, i) => (
                <Tag key={i} closable onClose={() => removeTag(tag)}
                  color="blue" style={{ fontSize: 11, borderRadius: 4 }}>{tag}</Tag>
              ))}
              {currentTags.length === 0 && <Text type="secondary" style={{ fontSize: 11 }}>暂无标签</Text>}
            </Space>
            <Space.Compact style={{ width: '100%' }}>
              <Input size="small" placeholder="自定义标签..." value={newTag}
                onChange={e => setNewTag(e.target.value)}
                onPressEnter={() => { if (newTag.trim()) { addTag(newTag.trim()); setNewTag(''); }}}
                style={{ borderRadius: 6 }} />
              <Button size="small" type="primary"
                onClick={() => { if (newTag.trim()) { addTag(newTag.trim()); setNewTag(''); }}}>添加</Button>
            </Space.Compact>
            <div style={{ marginTop: 6 }}>
              <Text type="secondary" style={{ fontSize: 10 }}>预设: </Text>
              <Space size={4} wrap>
                {PRESET_TAGS.filter(t => !currentTags.includes(t)).map(t => (
                  <Button key={t} size="small" type="dashed" style={{ fontSize: 10, borderRadius: 4 }}
                    onClick={() => addTag(t)}>{t}</Button>
                ))}
              </Space>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
